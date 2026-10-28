"""Turn the model's light Markdown into Telegram HTML, so **bold** renders instead of showing asterisks."""

import html
import re

BOLD = re.compile(r"\*\*([^\n*]+?)\*\*|__([^\n_]+?)__")
HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
BULLET = re.compile(r"^(\s*)[-*]\s+", re.MULTILINE)


def to_telegram_html(text: str) -> str:
    out = html.escape(text, quote=False)
    out = HEADING.sub(r"<b>\1</b>", out)
    out = BULLET.sub(r"\1• ", out)
    out = BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", out)
    # Nested bold inside a heading would produce <b><b>; collapse it.
    return out.replace("<b><b>", "<b>").replace("</b></b>", "</b>")
