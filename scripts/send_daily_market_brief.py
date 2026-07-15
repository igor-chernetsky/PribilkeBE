#!/usr/bin/env python3
"""Send today's market brief to admin Telegram. Run inside the API container."""

from pribilka.db.session import SessionLocal
from pribilka.models.enums import CountryCode
from pribilka.services.daily_market_brief import send_daily_market_brief


def main() -> None:
    db = SessionLocal()
    try:
        result = send_daily_market_brief(db, country=CountryCode.PL)
        print(result["date"], "sent=", result["sent"])
        print(result["message"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
