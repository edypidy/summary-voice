"""요약 전송 계층.

Telegram으로 확정됐지만(README Q5) 인터페이스 뒤에 둔다. Phase 0에서 전송 계층의
윗단(음성 낭독)이 통째로 바뀌었다 - 그때 Relay를 건드릴 필요가 없었던 이유가 이것이다.
"""

from summary_voice.sinks.base import Sink
from summary_voice.sinks.telegram import TelegramSink

__all__ = ["Sink", "TelegramSink"]
