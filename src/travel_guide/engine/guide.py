"""The guide engine: channel-agnostic. Telegram today, web app later, same engine."""

import logging

import anthropic

from travel_guide.engine.prompts import SYSTEM_PROMPT
from travel_guide.engine.sessions import SessionStore

log = logging.getLogger(__name__)

FALLBACK_REPLY = "מצטער, משהו השתבש אצלי. נסה שוב בעוד רגע."


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

    async def reply(self, user_id: str, text: str) -> str:
        messages = self._sessions.get(user_id)
        messages.append({"role": "user", "content": text})

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=self._trim(messages),
                output_config={"effort": self._effort},
                cache_control={"type": "ephemeral"},
            )
        except anthropic.RateLimitError:
            log.warning("Rate limited for user %s", user_id)
            return "יש עומס כרגע. נסה שוב בעוד דקה."
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return FALLBACK_REPLY
        except anthropic.APIConnectionError:
            log.exception("Claude API connection error")
            return FALLBACK_REPLY

        if response.stop_reason == "refusal":
            return "אני לא יכול לעזור עם זה. אשמח לעזור בתכנון הטיול."

        answer = "".join(b.text for b in response.content if b.type == "text").strip()
        if not answer:
            return FALLBACK_REPLY

        messages.append({"role": "assistant", "content": answer})
        self._sessions.save(user_id, messages)
        return answer

    def _trim(self, messages: list[dict]) -> list[dict]:
        trimmed = messages[-self._history_limit :]
        # The API requires the first message to be from the user.
        while trimmed and trimmed[0]["role"] != "user":
            trimmed = trimmed[1:]
        return trimmed
