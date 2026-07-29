"""Telegram Bot API 전송 (README Q5).

Slack 대신 Telegram을 쓰는 이유: 봇 생성이 @BotFather 대화 한 번이면 끝나고,
답장 왕복이 자연스럽다 (Phase 2 양방향의 포석).

`sendMessage` 하나만 쓴다. 그 이상은 필요 없다.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

API = "https://api.telegram.org"

# 텔레그램 메시지 상한은 4096자지만 우리 내레이션은 200자대다.
# 이 상한에 걸릴 일이 있다면 그건 내레이션 생성 쪽 버그다.
TELEGRAM_HARD_LIMIT = 4096


class TelegramSink:
    def __init__(self, token: str, chat_id: str, timeout: float = 10.0):
        self._token = token
        self._chat_id = chat_id
        self._timeout = timeout

    def send(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if len(text) > TELEGRAM_HARD_LIMIT:
            # 자르되 보낸다. 아무것도 안 보내는 것보단 낫다.
            log.warning("내레이션이 %d자로 비정상적으로 깁니다. 잘라서 보냅니다.", len(text))
            text = text[: TELEGRAM_HARD_LIMIT - 1] + "…"

        try:
            response = httpx.post(
                f"{API}/bot{self._token}/sendMessage",
                # parse_mode 키를 아예 넣지 않는다. 그래야 평문으로 간다.
                # `"parse_mode": None` 으로 두면 JSON에 null 이 실려 나가고
                # 텔레그램이 400 "unsupported parse_mode" 로 거절한다.
                # 파싱을 켜면 안 되는 이유: 내레이션은 평문인데 언더스코어가 든
                # 식별자 하나에 400이 나서 알림을 통째로 잃는다.
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            # 전송 실패가 Relay를 죽이면 안 된다 (CLAUDE.md 하드 제약 2).
            log.error("Telegram 전송 실패: %s", exc)
            return False

        if response.status_code != 200:
            log.error("Telegram %d: %s", response.status_code, response.text[:200])
            return False
        return True

    @classmethod
    def from_env(cls) -> TelegramSink:
        from summary_voice.config import require_env

        return cls(
            token=require_env(
                "TELEGRAM_BOT_TOKEN",
                hint="@BotFather 에서 /newbot 으로 봇을 만들고 토큰을 받으세요.",
            ),
            chat_id=require_env(
                "TELEGRAM_CHAT_ID",
                hint="봇에게 아무 메시지나 보낸 뒤 `sv-send --whoami` 를 실행하세요.",
            ),
        )


def discover_chat_id(token: str, timeout: float = 10.0) -> list[tuple[str, str]]:
    """`getUpdates`로 이 봇에게 말을 건 채팅들을 찾는다.

    TELEGRAM_CHAT_ID를 손으로 알아내는 건 셋업에서 가장 자주 막히는 지점이라
    도구로 만들어 둔다. 반환값은 (chat_id, 표시이름) 목록.
    """
    try:
        response = httpx.get(f"{API}/bot{token}/getUpdates", timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("getUpdates 실패: %s", exc)
        return []

    found: dict[str, str] = {}
    for update in response.json().get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        name = chat.get("title") or " ".join(
            filter(None, [chat.get("first_name"), chat.get("last_name")])
        ) or chat.get("username") or chat.get("type", "?")
        found[str(chat_id)] = name
    return sorted(found.items())
