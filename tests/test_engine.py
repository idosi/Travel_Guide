import json
from types import SimpleNamespace

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

from travel_guide.adapters.telegram_bot import build_keyboard, split_message
from travel_guide.engine import GuideEngine, GuideReply, InMemorySessionStore
from travel_guide.engine.guide import FALLBACK_REPLY


def api_response(raw: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=raw)])


class FakeMessages:
    def __init__(self, reply: str = "שלום", options: list[str] | None = None, raw: str | None = None):
        self.raw = raw if raw is not None else json.dumps({"reply": reply, "options": options or []})
        self.stop_reason = "end_turn"
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return api_response(self.raw, self.stop_reason)


def make_engine(history_limit: int = 20, **fake_kwargs):
    api = FakeMessages(**fake_kwargs)
    engine = GuideEngine(SimpleNamespace(messages=api), InMemorySessionStore(), model="test", history_limit=history_limit)
    return engine, api


async def test_reply_keeps_plain_text_history_per_user():
    engine, api = make_engine(reply="תשובה", options=["תוכנית יום"])
    await engine.reply("u1", "רומא")
    await engine.reply("u1", "תוכנית ליום")
    await engine.reply("u2", "Paris")

    assert [m["content"] for m in api.calls[1]["messages"]] == ["רומא", "תשובה", "תוכנית ליום"]
    assert [m["content"] for m in api.calls[2]["messages"]] == ["Paris"]


async def test_reply_returns_text_and_options():
    engine, _ = make_engine(reply="מה לתכנן?", options=["תוכנית יום", "מסעדות"])
    result = await engine.reply("u1", "רומא")
    assert result == GuideReply("מה לתכנן?", ["תוכנית יום", "מסעדות"])


async def test_options_are_capped_and_trimmed():
    engine, _ = make_engine(reply="x", options=["a" * 50, " ", "b", "c", "d", "e"])
    result = await engine.reply("u1", "רומא")
    assert result.options == ["a" * 30, "b", "c", "d"]


async def test_invalid_json_falls_back_without_saving_history():
    engine, api = make_engine(raw="not json")
    result = await engine.reply("u1", "רומא")
    assert result.text == FALLBACK_REPLY
    await engine.reply("u1", "שוב")
    assert [m["content"] for m in api.calls[1]["messages"]] == ["שוב"]


async def test_truncated_reply_falls_back():
    engine, api = make_engine()
    api.stop_reason = "max_tokens"
    result = await engine.reply("u1", "רומא")
    assert result.text == FALLBACK_REPLY


async def test_reset_clears_history():
    engine, api = make_engine()
    await engine.reply("u1", "רומא")
    engine.reset("u1")
    await engine.reply("u1", "לונדון")
    assert len(api.calls[1]["messages"]) == 1


async def test_trim_starts_with_user_message():
    engine, api = make_engine(history_limit=3)
    for city in ["a", "b", "c"]:
        await engine.reply("u1", city)
    sent = api.calls[-1]["messages"]
    assert sent[0]["role"] == "user"
    assert len(sent) <= 3


def test_split_message_respects_limit():
    text = "\n".join(["x" * 30] * 10)
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks) == "x" * 300


def test_keyboard_two_buttons_per_row():
    markup = build_keyboard(GuideReply("x", ["a", "b", "c"]))
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert [[b.text for b in row] for row in markup.keyboard] == [["a", "b"], ["c"]]


def test_keyboard_removed_without_options():
    assert isinstance(build_keyboard(GuideReply("x")), ReplyKeyboardRemove)
