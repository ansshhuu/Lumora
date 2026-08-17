import os


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


API_KEY = os.getenv("API_KEY") or os.getenv("SECRET_KEY")
MAX_REPO_SIZE_MB = _int_env("MAX_REPO_SIZE_MB", 500)
RATE_LIMIT_PER_MINUTE = _int_env("RATE_LIMIT_PER_MINUTE", 20)
QUERY_TIMEOUT_SECONDS = _int_env("QUERY_TIMEOUT_SECONDS", 30)
