"""Telegram adapter: translates Telegram updates into GuideEngine calls. No business logic here."""

import logging

import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from travel_guide.config import get_settings
from travel_guide.engine import GuideEngine, InMemorySessionStore

log = logging.getLogger(__name__)

WELCOME = (
    "שלום! אני המדריך המקומי שלך 🧭\n"
    "לאן אתה נוסע? כתוב לי עיר או אתר, ואבנה לך תוכנית.\n\n"
    "Hi! Tell me where you're going and I'll plan it for you."
)
TELEGRAM_MAX_LEN = 4096


def split_message(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Split on paragraph boundaries so long plans fit Telegram's message limit."""
    chunks: list[str] = []
    current = ""
    for para in text.split("\n"):
        candidate = f"{current}\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(para) > limit:
            chunks.append(para[:limit])
            para = para[limit:]
        current = para
    if current:
        chunks.append(current)
    return chunks


def build_app() -> Application:
    settings = get_settings()
    engine = GuideEngine(
        client=anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
        sessions=InMemorySessionStore(),
        model=settings.claude_model,
        effort=settings.claude_effort,
        max_tokens=settings.max_tokens,
        history_limit=settings.history_limit,
    )

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        engine.reset(str(update.effective_user.id))
        await update.message.reply_text(WELCOME)

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.chat.send_action(ChatAction.TYPING)
        answer = await engine.reply(str(update.effective_user.id), update.message.text)
        for chunk in split_message(answer):
            await update.message.reply_text(chunk)

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler(["start", "new"], start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # Polling for local development; step 4 switches to a webhook for hosting.
    build_app().run_polling()


if __name__ == "__main__":
    main()
