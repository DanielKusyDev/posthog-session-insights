from datetime import timedelta
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from app.models import ActionType, EventType, Severity
from app.services.pattern_detection import EventFilter, PatternRule, SessionFilter

BASE_DIR = Path(__name__).parent.parent


class Settings(BaseSettings):
    db_driver: str = Field("postgresql+asyncpg", description="SQLAlchemy DB driver")
    db_user: str = Field("")
    db_password: str = Field("")
    db_host: str = Field("")
    db_port: int = Field("")
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


PATTERN_RULES: list[PatternRule] = [  # These should definitely come from the database
    # High-severity patterns (conversion blockers)
    PatternRule(
        code="checkout_abandoned",
        description="Started checkout but didn't complete order within 30 minutes",
        severity=Severity.high,
        filter=EventFilter(semantic_contains="checkout"),
        min_count=1,
        negative_filter=EventFilter(semantic_contains="order"),
        negative_time_window=timedelta(minutes=30),
    ),
    PatternRule(
        code="payment_failure_frustration",
        description="Multiple rage clicks on payment page indicating payment issues",
        severity=Severity.high,
        filter=EventFilter(
            action_type=ActionType.rage_click,
            page_path_prefix="/payment",
        ),
        min_count=2,
    ),
    PatternRule(
        code="signup_abandonment",
        description="Started signup process but didn't complete",
        severity=Severity.high,
        filter=EventFilter(semantic_contains="signup"),
        min_count=1,
        negative_filter=EventFilter(semantic_contains="account created"),
        negative_time_window=timedelta(minutes=15),
    ),
    # Medium-severity patterns (friction indicators)
    PatternRule(
        code="billing_hesitation",
        description="Visited billing page multiple times without completing upgrade",
        severity=Severity.medium,
        filter=EventFilter(
            event_type=EventType.pageview,
            page_path_prefix="/billing",
        ),
        min_count=3,
        negative_filter=EventFilter(semantic_contains="upgrade"),
    ),
    PatternRule(
        code="form_struggle",
        description="Multiple form interactions suggesting difficulty completing form",
        severity=Severity.medium,
        filter=EventFilter(
            event_type=EventType.click,
            page_path_prefix="/contact",
        ),
        min_count=8,
        time_window=timedelta(minutes=5),
    ),
    PatternRule(
        code="price_comparison_loop",
        description="Repeatedly viewing pricing page without taking action",
        severity=Severity.medium,
        filter=EventFilter(
            event_type=EventType.pageview,
            page_path_prefix="/pricing",
        ),
        min_count=4,
        negative_filter=EventFilter(semantic_contains="checkout"),
    ),
    # Low-severity patterns (engagement insights)
    PatternRule(
        code="quick_bounce",
        description="Very short session with minimal engagement",
        severity=Severity.low,
        session_filter=SessionFilter(
            max_duration_seconds=30,
            max_events=3,
        ),
    ),
    PatternRule(
        code="power_user_session",
        description="Extended session with high engagement",
        severity=Severity.low,
        session_filter=SessionFilter(
            min_duration_seconds=600,
            min_events=20,
        ),
    ),
    PatternRule(
        code="feature_exploration",
        description="Visited many different pages in quick succession",
        severity=Severity.low,
        filter=EventFilter(event_type=EventType.pageview),
        min_count=8,
        time_window=timedelta(minutes=10),
    ),
    PatternRule(
        code="product_comparison",
        description="Viewed multiple products without purchasing",
        severity=Severity.low,
        filter=EventFilter(semantic_contains="product"),
        min_count=5,
        negative_filter=EventFilter(semantic_contains="purchase"),
    ),
]


CONTEXT_EXCLUDE_KEYS = ("token", "distinct_id")
