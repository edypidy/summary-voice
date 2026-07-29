"""내레이션 전송 계층.

Telegram으로 확정됐지만(README Q5) 인터페이스 뒤에 둔다. Phase 0에서 낭독이
안 되면 전송 계층을 통째로 갈아야 한다 - 그때 Relay를 건드리지 않기 위해서다.
"""

from summary_voice.sinks.base import Sink
from summary_voice.sinks.telegram import TelegramSink

__all__ = ["Sink", "TelegramSink"]
