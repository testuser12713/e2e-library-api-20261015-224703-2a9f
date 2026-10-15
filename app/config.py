"""Application configuration.

Secrets come exclusively from the environment (never from a literal in the
repository). ``LIBRARY_API_KEY`` is mandatory; ``DATABASE_URL`` is optional and
defaults to a local SQLite file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings of the library API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    library_api_key: str
    database_url: str = "sqlite:///./library.db"


settings = Settings()
