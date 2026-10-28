from types import SimpleNamespace

from travel_guide.adapters.telegram_bot import split_message
from travel_guide.engine import GuideEngine, InMemorySessionStore


class FakeMessages:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=self.text)],
        )


def make_engine(text: str = "שלום", history_limit: int = 20):
    messages = FakeMessages(text)
    client = SimpleNamespace(messages=messages)
    engine = GuideEngine(client, InMemorySessionStore(), model="test", history_limit=history_limit)
    return engine, messages


async def test_reply_keeps_history_per_user():
    engine, api = make_engine("תשובה")
    await engine.reply("u1", "רומא")
    await engine.reply("u1", "תוכנית ליום")
    await engine.reply("u2", "Paris")

    assert [m["content"] for m in api.calls[1]["messages"]] == ["רומא", "תשובה", "תוכנית ליום"]
    assert [m["content"] for m in api.calls[2]["messages"]] == ["Paris"]


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
