from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import ValidationError

from ...config.env import LLM_MODEL, env
from ...config.logger import get_logger
from ...db.catalog_jobs import CatalogJobSelect
from ..file_readers import SourceFile
from .models import JobEdges
from .prompt import SYSTEM_PROMPT, build_user_content

logger = get_logger("edge_extractors")


class EdgeExtractorStrategy(ABC):
    model: str

    @abstractmethod
    def extract(self, job: CatalogJobSelect, sources: list[SourceFile]) -> JobEdges:
        """
        Extract the edges evidenced by a job's source files.

        Args:
            job: the catalog job the sources belong to
            sources: the job's source files

        Returns:
            The job's extracted edges
        """


class LlmEdgeExtractor(EdgeExtractorStrategy):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.workspace_id = workspace_id

    @classmethod
    def from_env(cls) -> LlmEdgeExtractor:
        """
        Build an extractor from the DOCKET_LLM_* environment variables.

        DOCKET_LLM_API_KEY is optional; providers authenticated through their
        own environment variables (e.g. AWS credentials for bedrock) omit it.
        DOCKET_LLM_WORKSPACE_ID is required only by identity-linked keys.

        Args:
            None

        Returns:
            The configured extractor

        Raises:
            ValueError: if DOCKET_LLM_MODEL is not set
        """
        model = env.llm_model
        if not model:
            raise ValueError(f"{LLM_MODEL} must be set")
        return cls(
            model=model,
            api_key=env.llm_api_key,
            workspace_id=env.llm_workspace_id,
        )

    def _complete(self, messages: list[dict[str, str]]) -> str:
        """
        Run one completion against the configured model.

        Args:
            messages: the conversation so far

        Returns:
            The raw response content
        """
        from litellm import completion

        extra_headers = (
            {"anthropic-workspace-id": self.workspace_id} if self.workspace_id else None
        )
        response = completion(
            model=self.model,
            messages=messages,
            response_format=JobEdges,
            api_key=self.api_key,
            num_retries=5,
            extra_headers=extra_headers,
            thinking={"type": "adaptive"},
            max_tokens=16000,
            drop_params=True,
        )
        return response.choices[0].message.content or ""

    def extract(self, job: CatalogJobSelect, sources: list[SourceFile]) -> JobEdges:
        """
        Extract edges with one LLM call, retrying once on invalid output.

        Args:
            job: the catalog job the sources belong to
            sources: the job's source files

        Returns:
            The job's extracted edges

        Raises:
            pydantic.ValidationError: if the retry output is also invalid
        """
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {"role": "user", "content": build_user_content(job, sources)},
        ]
        content = self._complete(messages)
        try:
            return JobEdges.model_validate_json(content)
        except ValidationError as error:
            logger.warning(
                "invalid extraction for %s, retrying once: %s", job["name"], error
            )
            messages.extend(
                [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "That response failed schema validation:\n"
                            f"{error}\n"
                            "Respond again with only valid JSON for the schema."
                        ),
                    },
                ]
            )
            return JobEdges.model_validate_json(self._complete(messages))


class FixtureEdgeExtractor(EdgeExtractorStrategy):
    model = "fixture"

    def __init__(self, fixtures: dict[str, JobEdges]) -> None:
        self.fixtures = fixtures
        self.calls = 0

    def extract(self, job: CatalogJobSelect, sources: list[SourceFile]) -> JobEdges:
        """
        Return the canned extraction for a job.

        Args:
            job: the catalog job the sources belong to
            sources: the job's source files, unused

        Returns:
            The job's canned edges

        Raises:
            KeyError: if the job name has no fixture
        """
        self.calls += 1
        return self.fixtures[job["name"]]
