import os

AWS_REGIONS = "DOCKET_AWS_REGIONS"
LLM_API_KEY = "DOCKET_LLM_API_KEY"
LLM_MODEL = "DOCKET_LLM_MODEL"
LOG_LEVEL = "DOCKET_LOG_LEVEL"


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
    def llm_api_key(self) -> str | None:
        """
        The LLM provider api key from DOCKET_LLM_API_KEY.

        Optional; providers authenticated through their own environment
        variables (e.g. AWS credentials for bedrock) leave it unset.
        """
        return os.environ.get(LLM_API_KEY)

    @property
    def llm_model(self) -> str | None:
        """The litellm model string from DOCKET_LLM_MODEL, or None when unset."""
        return os.environ.get(LLM_MODEL)

    @property
    def log_level(self) -> str | None:
        """The upper-cased docket log level from DOCKET_LOG_LEVEL, or None when unset."""
        value = os.environ.get(LOG_LEVEL, "").upper()
        return value or None


env = Env()
