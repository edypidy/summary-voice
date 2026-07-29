"""sv-send — 텔레그램 한 줄 전송.

셋업 확인용 도구다. 실제 요약 전송은 릴레이가 `TelegramSink`를 직접 쓴다.

    sv-send --whoami              봇에게 말을 건 채팅 ID 찾기 (셋업)
    sv-send "테스트 문장"           한 줄 보내기
    echo "본문" | sv-send          stdin 으로도 받는다
"""

from __future__ import annotations

import argparse
import logging
import sys

from summary_voice.config import require_env
from summary_voice.sinks.telegram import TelegramSink, discover_chat_id


def _whoami() -> int:
    token = require_env("TELEGRAM_BOT_TOKEN", hint="@BotFather → /newbot")
    chats = discover_chat_id(token)
    if not chats:
        print(
            "이 봇에게 말을 건 채팅이 없습니다.\n"
            "  1. 텔레그램에서 봇을 찾아 대화를 열고\n"
            "  2. 아무 메시지나 한 번 보낸 뒤\n"
            "  3. 이 명령을 다시 실행하세요.\n"
            "  (getUpdates 는 최근 24시간 내의 아직 소비되지 않은 업데이트만 돌려줍니다.)",
            file=sys.stderr,
        )
        return 1
    print("TELEGRAM_CHAT_ID 후보:")
    for chat_id, name in chats:
        print(f"  {chat_id}\t{name}")
    if len(chats) == 1:
        print(f"\n.env 에 넣으세요:\n  TELEGRAM_CHAT_ID={chats[0][0]}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sv-send", description="텔레그램으로 한 줄 보낸다.")
    parser.add_argument("text", nargs="*", help="보낼 문장")
    parser.add_argument(
        "--whoami", action="store_true",
        help="봇에게 말을 건 채팅 ID를 찾는다 (TELEGRAM_CHAT_ID 셋업용)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    # httpx 는 INFO 로 요청 URL 전체를 찍는다. 텔레그램은 봇 토큰이 URL 경로에 있어서
    # 그대로 두면 매 호출마다 시크릿이 터미널과 로그에 남는다.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.whoami:
        return _whoami()

    text = " ".join(args.text).strip()
    if not text and not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    if not text:
        parser.error("보낼 문장이 없습니다. 인자로 주거나 stdin으로 파이프하세요.")

    if not TelegramSink.from_env().send(text):
        return 1
    print(f"전송됨 ({len(text)}자)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
