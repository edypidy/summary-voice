"""Phase 0 셋업에서 실제로 터진 두 버그에 대한 회귀 테스트."""

from __future__ import annotations

import httpx
import pytest

from summary_voice import config as config_module
from summary_voice.sinks import telegram as telegram_module
from summary_voice.sinks.telegram import TelegramSink


class FakeResponse:
    def __init__(self, status_code=200, text="{}"):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def captured(monkeypatch):
    """httpx.post 를 가로채 실제로 나가는 payload 를 붙잡는다."""
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json})
        return FakeResponse()

    monkeypatch.setattr(telegram_module.httpx, "post", fake_post)
    return calls


class TestPayload:
    def test_parse_mode_key_is_absent(self, captured):
        """`"parse_mode": None` 을 실으면 텔레그램이 400 unsupported parse_mode 로 거절한다.

        JSON 에 null 이 실려 나가고, 텔레그램은 그걸 '값이 없음'이 아니라
        '모르는 파싱 모드'로 읽는다. 키를 아예 빼야 평문으로 간다.
        """
        assert TelegramSink("tok", "42").send("안녕하세요")
        assert "parse_mode" not in captured[0]["json"]

    def test_sends_text_and_chat_id(self, captured):
        TelegramSink("tok", "42").send("  내레이션  ")
        assert captured[0]["json"]["chat_id"] == "42"
        assert captured[0]["json"]["text"] == "내레이션"

    def test_empty_text_is_not_sent(self, captured):
        assert not TelegramSink("tok", "42").send("   ")
        assert captured == []


class TestNeverRaises:
    """전송 실패가 Relay 를 죽이면 안 된다 (CLAUDE.md 하드 제약 2)."""

    def test_network_error_returns_false(self, monkeypatch):
        def boom(*a, **k):
            raise httpx.ConnectError("네트워크 없음")

        monkeypatch.setattr(telegram_module.httpx, "post", boom)
        assert not TelegramSink("tok", "42").send("안녕")

    def test_http_error_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            telegram_module.httpx, "post",
            lambda *a, **k: FakeResponse(400, '{"description":"chat not found"}'),
        )
        assert not TelegramSink("tok", "42").send("안녕")

    def test_overlong_text_is_truncated_not_dropped(self, captured):
        TelegramSink("tok", "42").send("가" * 5000)
        sent = captured[0]["json"]["text"]
        assert len(sent) <= telegram_module.TELEGRAM_HARD_LIMIT
        assert sent.endswith("…")


class TestPlaceholderGuard:
    """`.env.example` 을 복사해 일부만 채우는 건 흔하다.

    자리표시자를 그대로 두면 텔레그램이 "chat not found" 를 돌려주는데,
    그건 원인을 전혀 안 알려준다. 셋업 단계에서 잡아야 한다.
    """

    def test_placeholder_value_counts_as_missing(self, monkeypatch, tmp_path):
        example = tmp_path / ".env.example"
        example.write_text("TELEGRAM_CHAT_ID=123456789\n", encoding="utf-8")
        monkeypatch.setattr(config_module, "REPO_ROOT", tmp_path)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")

        with pytest.raises(SystemExit, match="TELEGRAM_CHAT_ID"):
            config_module.require_env("TELEGRAM_CHAT_ID")

    def test_real_value_passes(self, monkeypatch, tmp_path):
        example = tmp_path / ".env.example"
        example.write_text("TELEGRAM_CHAT_ID=123456789\n", encoding="utf-8")
        monkeypatch.setattr(config_module, "REPO_ROOT", tmp_path)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")

        assert config_module.require_env("TELEGRAM_CHAT_ID") == "987654321"
