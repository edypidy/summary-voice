"""Anthropic API 호출 래퍼.

세 군데서 쓴다: 살리언스 판정, 내레이션 생성, STT 레이어 2 교정.
모두 Haiku 급이고, 모두 **실패해도 파이프라인을 죽이면 안 된다** (CLAUDE.md 하드 제약 2).

Relay는 Claude Code 에이전트가 아니라 단순 API 호출이다 (README 설계 원칙 4).
여기에 툴이나 파일시스템 접근을 붙이지 말 것.
"""

from __future__ import annotations

import json
import logging

import anthropic

from summary_voice.config import require_env

log = logging.getLogger(__name__)

# Haiku 4.5는 200K 컨텍스트 / 64K 출력. 우리 용도는 전부 짧다.
# 여유를 두되, 내레이션이 폭주하지 않게 호출부에서 더 조인다.
DEFAULT_MAX_TOKENS = 1024


class LLMClient:
    """실패를 삼키는 Anthropic 클라이언트.

    SDK가 429/5xx/네트워크 오류를 지수 백오프로 자동 재시도한다 (기본 2회).
    그걸 다시 감싸지 않는다. 재시도 후에도 실패하면 None을 돌려주고,
    호출부가 "이번 내레이션은 건너뛴다"를 결정한다.
    """

    def __init__(self, model: str, api_key: str | None = None, timeout: float = 30.0):
        self.model = model
        self._client = anthropic.Anthropic(
            api_key=api_key or require_env(
                "ANTHROPIC_API_KEY",
                hint="https://platform.claude.com 에서 발급받아 .env 에 넣으세요.",
            ),
            timeout=timeout,
        )

    def _call(self, **kwargs) -> anthropic.types.Message | None:
        """예외를 유형별로 구분해 로그를 남기고 None을 돌려준다.

        유형을 구분하는 이유는 사람이 로그를 보고 조치를 정할 수 있어야 해서다.
        인증 오류와 일시적 과부하는 대응이 완전히 다르다.
        """
        try:
            return self._client.messages.create(model=self.model, **kwargs)
        except anthropic.AuthenticationError:
            log.error("ANTHROPIC_API_KEY 가 올바르지 않습니다.")
        except anthropic.NotFoundError:
            log.error("모델 %r 을 찾을 수 없습니다. 별칭을 확인하세요.", self.model)
        except anthropic.RateLimitError:
            log.warning("레이트 리밋. 이번 내레이션은 건너뜁니다.")
        except anthropic.APIStatusError as exc:
            log.error("API 오류 %s: %s", exc.status_code, exc.message)
        except anthropic.APIConnectionError:
            log.warning("네트워크 오류. 이번 내레이션은 건너뜁니다.")
        return None

    def text(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str | None:
        """평문 응답. 실패하면 None."""
        response = self._call(
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if response is None:
            return None
        if response.stop_reason == "refusal":
            log.warning("모델이 응답을 거부했습니다.")
            return None
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def structured(
        self,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict | None:
        """JSON 스키마에 맞는 응답. 실패하거나 파싱이 깨지면 None.

        살리언스 판정처럼 "발화할 가치가 있는가"를 boolean으로 먼저 묻는 데 쓴다
        (README 섹션 6.2). 프리필로 JSON을 강제하지 않는다 - 최신 모델에서
        어시스턴트 프리필은 400이고, 구조화 출력이 정식 대체재다.
        """
        response = self._call(
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if response is None:
            return None
        if response.stop_reason == "refusal":
            log.warning("모델이 응답을 거부했습니다.")
            return None
        if response.stop_reason == "max_tokens":
            # 잘린 JSON은 파싱이 깨진다. 조용히 이상한 값을 쓰느니 버린다.
            log.warning("응답이 max_tokens 로 잘렸습니다.")
            return None

        raw = "".join(b.text for b in response.content if b.type == "text")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("JSON 파싱 실패: %r", raw[:200])
            return None

    @classmethod
    def from_config(cls) -> LLMClient:
        from summary_voice.config import Config

        return cls(model=Config.load().model)
