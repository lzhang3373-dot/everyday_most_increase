from __future__ import annotations

import sys
import traceback

from sector_email.config import load_settings
from sector_email.emailer import build_error_email, build_success_email, send_email
from sector_email.market import build_sector_report, resolve_trade_date


def main() -> int:
    settings = load_settings()

    try:
        trade_date = resolve_trade_date(
            settings.target_date,
            settings.timezone,
            settings.data_delay_minutes,
        )
        report = build_sector_report(trade_date)
        subject, text, html_body = build_success_email(report)
        send_email(settings, subject, text, html_body)
        print(f"Sent sector report for {trade_date.isoformat()}.")
        return 0
    except Exception as exc:
        traceback.print_exc()
        subject, text, html_body = build_error_email(exc)
        send_email(settings, subject, text, html_body)
        print("Sent error alert email.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
