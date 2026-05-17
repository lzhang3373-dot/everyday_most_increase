from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    mail_from: str
    mail_to: list[str]
    mail_cc: list[str]
    timezone: str
    data_delay_minutes: int
    target_date: str | None


def _split_emails(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")

    required = [
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "MAIL_FROM",
        "MAIL_TO",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return Settings(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=_get_int("SMTP_PORT", 587),
        smtp_username=os.environ["SMTP_USERNAME"],
        smtp_password=os.environ["SMTP_PASSWORD"],
        mail_from=os.environ["MAIL_FROM"],
        mail_to=_split_emails(os.environ["MAIL_TO"]),
        mail_cc=_split_emails(os.getenv("MAIL_CC")),
        timezone=os.getenv("TIMEZONE", "America/New_York"),
        data_delay_minutes=_get_int("DATA_DELAY_MINUTES", 45),
        target_date=os.getenv("TARGET_DATE") or None,
    )
