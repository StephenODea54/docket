import os

AWS_REGIONS = "DOCKET_AWS_REGIONS"
DB_PATH = "DOCKET_DB_PATH"
LLM_API_KEY = "DOCKET_LLM_API_KEY"
LLM_CONCURRENCY = "DOCKET_LLM_CONCURRENCY"
LLM_MODEL = "DOCKET_LLM_MODEL"
LLM_WORKSPACE_ID = "DOCKET_LLM_WORKSPACE_ID"
LOG_LEVEL = "DOCKET_LOG_LEVEL"
SERVE_ADAPTER = "DOCKET_SERVE_ADAPTER"
SERVE_HOST = "DOCKET_SERVE_HOST"
SERVE_PORT = "DOCKET_SERVE_PORT"


class Env:
    """
    Central accessor for every DOCKET_* environment variable.

    Values are read from os.environ on each access, so .env files loaded
    at the app edge and test monkeypatching both take effect.
    """

    @property
    def aws_regions(self) -> list[str]:
        """
        The AWS regions steampipe should scan, from DOCKET_AWS_REGIONS.

        Parsed from a comma separated list; empty means steampipe scans
        every region.
        """
        value = os.environ.get(AWS_REGIONS, "")
        return [name.strip() for name in value.split(",") if name.strip()]

    @property
    def db_path(self) -> str:
        """The sqlite database path from DOCKET_DB_PATH; defaults to docket.db."""
        return os.environ.get(DB_PATH) or "docket.db"

    @property
    def llm_api_key(self) -> str | None:
        """
        The LLM provider api key from DOCKET_LLM_API_KEY.

        Optional; providers authenticated through their own environment
        variables (e.g. AWS credentials for bedrock) leave it unset or empty.
        """
        return os.environ.get(LLM_API_KEY) or None

    @property
    def llm_concurrency(self) -> int:
        """
        Parallel extraction calls from DOCKET_LLM_CONCURRENCY; defaults to 8.

        Values that are not positive integers fall back to the default.
        """
        value = os.environ.get(LLM_CONCURRENCY, "")
        return int(value) if value.isdigit() and int(value) > 0 else 8

    @property
    def llm_model(self) -> str | None:
        """The litellm model string from DOCKET_LLM_MODEL, or None when unset."""
        return os.environ.get(LLM_MODEL)

    @property
    def llm_workspace_id(self) -> str | None:
        """
        Workspace ID from DOCKET_LLM_WORKSPACE_ID.

        Required by identity-linked API keys; workspace keys leave it unset.
        """
        return os.environ.get(LLM_WORKSPACE_ID) or None

    @property
    def log_level(self) -> str | None:
        """The upper-cased log level from DOCKET_LOG_LEVEL, or None when unset."""
        value = os.environ.get(LOG_LEVEL, "").upper()
        return value or None

    @property
    def serve_adapter(self) -> str:
        """The serve runtime adapter from DOCKET_SERVE_ADAPTER; defaults to uvicorn."""
        return os.environ.get(SERVE_ADAPTER) or "uvicorn"

    @property
    def serve_host(self) -> str:
        """The serve bind host from DOCKET_SERVE_HOST; defaults to 127.0.0.1."""
        return os.environ.get(SERVE_HOST) or "127.0.0.1"

    @property
    def serve_port(self) -> int:
        """
        The serve bind port from DOCKET_SERVE_PORT; defaults to 8000.

        Values that are not positive integers fall back to the default.
        """
        value = os.environ.get(SERVE_PORT, "")
        return int(value) if value.isdigit() and int(value) > 0 else 8000


env = Env()
