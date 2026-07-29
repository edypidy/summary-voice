"""전송 계층 인터페이스."""

from __future__ import annotations

from typing import Protocol


class Sink(Protocol):
    """내레이션 한 건을 사용자 폰으로 보낸다.

    구현체는 **실패해도 예외를 밖으로 던지지 않는다.** 알림 전송이 안 된다고
    Relay가 죽으면 그 뒤 이벤트를 전부 잃는다. 실패는 False로 알린다.
    """

    def send(self, text: str) -> bool:
        """전송 성공 여부. 네트워크 오류는 삼키고 False."""
        ...
