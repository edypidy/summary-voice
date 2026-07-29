"""추출기들을 돌려 하나의 용어집으로 합치고, 랭킹해서 상한만큼 남긴다."""

from __future__ import annotations

import logging
from pathlib import Path

from summary_voice.glossary.extract import EXTRACTORS
from summary_voice.glossary.models import MAX_TERMS, Glossary

log = logging.getLogger(__name__)


def build(root: Path, limit: int = MAX_TERMS, sources: list[str] | None = None) -> Glossary:
    """레포에서 용어집을 만든다.

    추출기 하나가 터져도 나머지는 계속한다. 용어집이 조금 부실한 것과
    전혀 없는 것은 큰 차이다.
    """
    root = Path(root).resolve()
    glossary = Glossary(project=root.name)

    for name, extractor in EXTRACTORS.items():
        if sources and name not in sources:
            continue
        try:
            terms = extractor(root)
        except Exception:
            log.warning("추출기 %s 실패, 건너뜀", name, exc_info=True)
            continue
        log.info("%-8s %4d개 후보", name, len(terms))
        glossary.merge(terms)

    log.info("병합 후 %d개 → 상위 %d개로 절삭", len(glossary), limit)
    return glossary.top(limit)
