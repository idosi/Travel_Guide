# Travel_Guide

Your personal Travel Guide and Vacation helper.

בוט טלגרם שמתנהג כמו מדריך מקומי: מקבל יעד (עיר או אתר), שואל מה לתכנן, ובונה תוכנית יום עם מסעדות, אטרקציות, מקומות לילדים ועוד. עברית כברירת מחדל, אנגלית לפי המשתמש.

## Architecture

```
src/travel_guide/
  engine/      # channel-agnostic guide logic (Claude calls, prompts, sessions)
  adapters/    # Telegram today; a web app later reuses the same engine
  config.py    # settings from env / .env
```

## Run locally

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. `cp .env.example .env` and fill in the keys.
3. Install and run:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
travel-guide-telegram
```

Tests: `pytest`

## Roadmap

- [x] Step 1: project skeleton, engine separated from Telegram
- [ ] Step 2: planning conversation flow
- [ ] Step 3: Google Places tools (hours, rating, price level) with cache
- [ ] Step 4: hosting with webhook, logging, per-user rate limit
