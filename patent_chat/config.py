from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent


def load_env_files() -> None:
    load_dotenv(ROOT / ".env.local", override=True)
    load_dotenv(ROOT / ".env", override=False)


load_env_files()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    patsnap_api_key: str = Field(default="", alias="PATSNAP_API_KEY")
    patsnap_base_url: str = Field(
        default="https://connect.patsnap.com",
        alias="PATSNAP_BASE_URL",
    )
    patsnap_search_path: str = Field(
        default="/search/patent/nested-search-patent",
        alias="PATSNAP_SEARCH_PATH",
    )
    patsnap_count_path: str = Field(
        default="/search/patent/query-search-count",
        alias="PATSNAP_COUNT_PATH",
    )
    patsnap_default_limit: int = Field(default=10, alias="PATSNAP_DEFAULT_LIMIT")


def get_settings() -> Settings:
    load_env_files()
    return Settings()
