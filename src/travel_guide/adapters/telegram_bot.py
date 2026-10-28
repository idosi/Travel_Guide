"""Telegram adapter: translates Telegram updates into GuideEngine calls. No business logic here."""

import logging

import anthropic
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from travel_guide.adapters.telegram_format import to_telegram_html
from travel_guide.config import get_settings
from travel_guide.engine import GuideEngine, GuideReply, InMemorySessionStore

log = logging.getLogger(__name__)

WELCOME = (
    "שלום! אני המדריך המקומי שלך 🧭\n"
    "לאן אתה נוסע? כתוב לי עיר או אתר, ואבנה לך תוכנית.\n\n"
    "Hi! Tell me where you're going and I'll plan it for you."
)
TELEGRAM_MAX_LEN = 4096
# Split the raw text below the limit: HTML escaping and <b> tags make each chunk longer.
RAW_CHUNK_LEN = 3500


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


def build_keyboard(reply: GuideReply) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """Options become tappable buttons, two per row; tapping one sends its label as a message."""
    if not reply.options:
        return ReplyKeyboardRemove()
    rows = [
        [KeyboardButton(label) for label in reply.options[i : i + 2]]
        for i in range(0, len(reply.options), 2)
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def send_formatted(message, text: str, reply_markup=None) -> None:
    """Send as Telegram HTML; if Telegram rejects the markup, fall back to plain text."""
    try:
        await message.reply_text(to_telegram_html(text), parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except BadRequest as e:
        log.warning("HTML rejected by Telegram (%s); sending plain text", e)
        await message.reply_text(text, reply_markup=reply_markup)


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
        await update.message.reply_text(WELCOME, reply_markup=ReplyKeyboardRemove())

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.chat.send_action(ChatAction.TYPING)
        reply = await engine.reply(str(update.effective_user.id), update.message.text)
        chunks = split_message(reply.text, RAW_CHUNK_LEN)
        for chunk in chunks[:-1]:
            await send_formatted(update.message, chunk)
        # The keyboard rides on the last chunk so it appears under the question it answers.
        await send_formatted(update.message, chunks[-1], build_keyboard(reply))

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
