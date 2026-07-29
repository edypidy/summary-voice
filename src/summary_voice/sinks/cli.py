"""sv-send — Phase 0용 텔레그램 전송 도구.

Phase 0은 코드가 거의 없는 수동 검증 단계다 (README 섹션 4). 이 CLI는 그
검증을 할 수 있게 해주는 최소한의 도구다:

    sv-send --whoami              봇에게 말을 건 채팅 ID 찾기 (셋업)
    sv-send "테스트 문장"           한 줄 보내기
    sv-send --ruler               낭독 최대 글자 수 실측 (Phase 0 합격 기준)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from summary_voice.config import load_dotenv, require_env
from summary_voice.sinks.ruler import DEFAULT_LENGTHS, build_probes
from summary_voice.sinks.telegram import TelegramSink, discover_chat_id


def _whoami() -> int:
    load_dotenv()
    token = require_env("TELEGRAM_BOT_TOKEN", hint="@BotFather → /newbot")
    chats = discover_chat_id(token)
    if not chats:
        print(
            "이 봇에게 말을 건 채팅이 없습니다.\n"
            "  1. 텔레그램에서 봇을 찾아 대화를 열고\n"
            "  2. 아무 메시지나 한 번 보낸 뒤\n"
            "  3. 이 명령을 다시 실행하세요.",
            file=sys.stderr,
        )
        return 1
    print("TELEGRAM_CHAT_ID 후보:")
    for chat_id, name in chats:
        print(f"  {chat_id}\t{name}")
    if len(chats) == 1:
        print(f"\n.env 에 넣으세요:\n  TELEGRAM_CHAT_ID={chats[0][0]}", file=sys.stderr)
    return 0


def _ruler(sink: TelegramSink, lengths: list[int], delay: float) -> int:
    probes = build_probes(lengths)
    print(
        "이어폰을 끼고 들으세요. 각 메시지는 '여기까지 N자입니다'로 끝납니다.\n"
        "그 끝맺음이 **들린** 마지막 N이 실측값입니다.\n"
        f"config.yaml 의 narration.max_chars 를 그 값으로 바꾸세요.\n"
        f"{len(probes)}개를 {delay}초 간격으로 보냅니다.\n",
        file=sys.stderr,
    )
    failures = 0
    for i, (n, text) in enumerate(probes):
        ok = sink.send(text)
        print(f"  [{i + 1}/{len(probes)}] {n:4d}자  {'전송됨' if ok else '실패'}", file=sys.stderr)
        failures += not ok
        # 낭독이 겹치면 어느 게 잘렸는지 알 수 없다. 앞 메시지가 다 읽힐 때까지 기다린다.
        if i < len(probes) - 1:
            time.sleep(delay)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sv-send",
        description="Phase 0 검증용 텔레그램 전송 도구.",
    )
    parser.add_argument("text", nargs="*", help="보낼 문장")
    parser.add_argument(
        "--whoami", action="store_true",
        help="봇에게 말을 건 채팅 ID를 찾는다 (TELEGRAM_CHAT_ID 셋업용)",
    )
    parser.add_argument(
        "--ruler", action="store_true",
        help="길이가 다른 메시지를 연속 전송해 낭독 최대 글자 수를 실측한다",
    )
    parser.add_argument(
        "--lengths", type=int, nargs="+", default=DEFAULT_LENGTHS,
        help=f"--ruler 로 측정할 길이 목록 (기본 {DEFAULT_LENGTHS})",
    )
    parser.add_argument(
        "--delay", type=float, default=20.0,
        help="--ruler 메시지 간 간격(초). 앞 메시지 낭독이 끝날 만큼 길어야 한다.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    if args.whoami:
        return _whoami()

    sink = TelegramSink.from_env()

    if args.ruler:
        return _ruler(sink, args.lengths, args.delay)

    text = " ".join(args.text).strip() or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    if not text:
        parser.error("보낼 문장이 없습니다. 인자로 주거나 stdin으로 파이프하세요.")

    if not sink.send(text):
        return 1
    print(f"전송됨 ({len(text)}자)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
