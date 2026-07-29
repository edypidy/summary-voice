"""설정 로딩. `.env` + `config.yaml` + 환경변수.

의존성을 늘리지 않으려고 python-dotenv 없이 직접 읽는다. 형식이 단순하다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """`.env`를 os.environ에 채운다. 이미 설정된 변수는 덮어쓰지 않는다.

    셸에서 명시적으로 넘긴 값이 파일보다 우선해야 한다.
    """
    path = path or REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class NarrationConfig:
    """README 섹션 6.3의 하드 제약.

    max_chars는 Phase 0에서 **실측**한 값으로 바꿔야 한다. 200은 잠정값이다.
    """

    max_chars: int = 200
    max_sentences: int = 3
    language: str = "ko"


@dataclass
class RelayConfig:
    """README 섹션 6.1. 초기값은 Q3의 답이며 실사용 하루 뒤 튜닝 대상이다."""

    debounce_seconds: int = 30
    max_narrations_per_hour: int = 12
    poll_interval_seconds: float = 2.0


@dataclass
class Config:
    narration: NarrationConfig = field(default_factory=NarrationConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    # Haiku 급을 쓴다 (README 섹션 6.1). 요약은 싸고 빨라야 한다.
    # 별칭으로 지정한다. Haiku 4.5는 effort 파라미터를 지원하지 않는다.
    model: str = "claude-haiku-4-5"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        load_dotenv()
        path = path or REPO_ROOT / "config.yaml"
        data: dict = {}
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            narration=NarrationConfig(**(data.get("narration") or {})),
            relay=RelayConfig(**(data.get("relay") or {})),
            model=data.get("model", cls.model),
        )


def require_env(name: str, hint: str = "") -> str:
    """환경변수를 읽되, 없으면 무엇을 해야 하는지 알려주고 죽는다."""
    load_dotenv()
    value = os.environ.get(name)
    if not value:
        suffix = f"\n  {hint}" if hint else ""
        raise SystemExit(f"환경변수 {name} 가 없습니다. .env.example 을 참고해 .env 에 넣으세요.{suffix}")
    return value
