from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BASE_DIR = Path(__name__).parent.parent


class Settings(BaseSettings):
    db_driver: str = Field("postgresql+asyncpg", description="SQLAlchemy DB driver")
    db_user: str = Field("")  # placeholders to prevent tests from failing
    db_password: str = Field("")
    db_host: str = Field("")
    db_port: int = Field(8000)
    db_name: str = Field("")

    pages_in_summary_limit: int = Field(3, description="Max number of visited pages included in short session summary.")
    semantic_label_max_length: int = Field(150, description="Max length of the semantic label.")
    default_custom_event_templates: dict[str, str] = Field(
        {
            "product_clicked": "Selected product: {product_name}",
            "form_submitted": "Submitted {form_name} form",
        },
        description="Event templates for custom events.",
    )
    default_enrichment_rules: dict[str, str] = Field(
        {
            "nav": "navigation {base_type}",
            "product-id": "product card",
            "product-name": "product card",
            "form-id": "{base_type} in form",
        },
        description="Default ",
    )
    context_exclude_keys: set[str] = ("token", "distinct_id")

    @property
    def sqlalchemy_url(self) -> URL:
        return URL.create(
            drivername=self.db_driver,
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


SETTINGS = Settings()
