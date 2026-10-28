"""The guide engine: channel-agnostic. Telegram today, web app later, same engine."""

import json
import logging
from dataclasses import dataclass, field

import anthropic

from travel_guide.engine.prompts import MAX_OPTION_LEN, MAX_OPTIONS, REPLY_SCHEMA, SYSTEM_PROMPT
from travel_guide.engine.sessions import SessionStore

log = logging.getLogger(__name__)

FALLBACK_REPLY = "מצטער, משהו השתבש אצלי. נסה שוב בעוד רגע."


@dataclass
class GuideReply:
    text: str
    # Short suggested answers; each adapter renders them its own way (Telegram keyboard, web chips).
    options: list[str] = field(default_factory=list)


class GuideEngine:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        sessions: SessionStore,
        model: str,
        effort: str = "low",
        max_tokens: int = 8000,
        history_limit: int = 20,
    ) -> None:
        self._client = client
        self._sessions = sessions
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._history_limit = history_limit

    def reset(self, user_id: str) -> None:
        self._sessions.reset(user_id)

    async def reply(self, user_id: str, text: str) -> GuideReply:
        messages = self._sessions.get(user_id)
        messages.append({"role": "user", "content": text})

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=self._trim(messages),
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": REPLY_SCHEMA},
                },
                cache_control={"type": "ephemeral"},
            )
        except anthropic.RateLimitError:
            log.warning("Rate limited for user %s", user_id)
            return GuideReply("יש עומס כרגע. נסה שוב בעוד דקה.")
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return GuideReply(FALLBACK_REPLY)
        except anthropic.APIConnectionError:
            log.exception("Claude API connection error")
            return GuideReply(FALLBACK_REPLY)

        if response.stop_reason == "refusal":
            return GuideReply("אני לא יכול לעזור עם זה. אשמח לעזור בתכנון הטיול.")
        if response.stop_reason == "max_tokens":
            log.warning("Reply cut at max_tokens for user %s", user_id)
            return GuideReply(FALLBACK_REPLY)

        result = self._parse(response)
        if result is None:
            return GuideReply(FALLBACK_REPLY)

        # History keeps plain text so the conversation reads naturally to the model.
        messages.append({"role": "assistant", "content": result.text})
        self._sessions.save(user_id, messages)
        return result

    @staticmethod
    def _parse(response) -> GuideReply | None:
        raw = "".join(b.text for b in response.content if b.type == "text")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.error("Reply is not valid JSON: %.200s", raw)
            return None
        text = data.get("reply", "").strip()
        if not text:
            return None
        options = [o.strip()[:MAX_OPTION_LEN] for o in data.get("options", []) if o.strip()]
        return GuideReply(text, options[:MAX_OPTIONS])

    def _trim(self, messages: list[dict]) -> list[dict]:
        trimmed = messages[-self._history_limit :]
        # The API requires the first message to be from the user.
        while trimmed and trimmed[0]["role"] != "user":
            trimmed = trimmed[1:]
        return trimmed
