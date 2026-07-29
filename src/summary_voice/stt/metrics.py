"""용어 재현율 (README 섹션 7.3).

전체 WER이 아니라 **용어집 항목이 정확히 전사되었는가**를 잰다. 이유:
"LoRA-XS 로스가 발산해요"에서 조사 하나 틀린 건 알아들을 수 있지만
"LoRA-XS"가 "로라 익스에스"로 나오면 그 문장은 쓸모가 없다.

한국어 매칭의 두 함정을 정면으로 다룬다:

1. **조사 교착**: "LoRA-XS가", "Sinkhorn을" 처럼 영어 용어 뒤에 조사가 바로
   붙는다. 공백 토큰화로는 절대 안 잡힌다. 그래서 라틴 문자 경계로 찾는다.
   한글은 라틴 문자가 아니므로 "LoRA-XS가"에서 "LoRA-XS" 뒤 경계가 성립한다.

2. **띄어쓰기 변동**: STT는 "LoRA XS", "LoRA-XS", "loraxs"를 오간다.
   Deepgram Nova-3 한국어는 아예 공백을 안 넣는 회귀 이슈도 있다
   (docs/research-stt.md). 용어 내부 구분자는 있으나 없으나 같게 본다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from summary_voice.glossary.models import Glossary
from summary_voice.glossary.variants import split_identifier

# 용어 내부에서 무시할 구분자. STT마다 다르게 뱉으므로 있으나 없으나 같게 본다.
_INNER = r"[\s_\-]*"


def term_pattern(term: str) -> re.Pattern[str]:
    """용어를 찾는 정규식.

    양쪽 경계는 "라틴 영숫자가 아닌 것"이다. 한글 조사는 라틴 문자가 아니므로
    "LoRA-XS가"에서 매칭이 성립하고, "LoRA-XSv2" 같은 다른 식별자와는 구분된다.
    """
    parts = split_identifier(term) or [term]
    body = _INNER.join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def contains_term(text: str, term: str) -> bool:
    return term_pattern(term).search(text) is not None


@dataclass
class TermRecall:
    """한 비교군의 채점 결과."""

    label: str
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.hits) + len(self.misses)

    @property
    def recall(self) -> float:
        """정답 전사에 등장한 용어 중 몇 개를 맞췄는가.

        정답에 용어가 하나도 없으면 1.0. 틀릴 게 없었으므로 감점 사유가 아니다.
        """
        return len(self.hits) / self.total if self.total else 1.0

    def __str__(self) -> str:
        return f"{self.label}: {self.recall:.1%} ({len(self.hits)}/{self.total})"


def term_recall(
    references: list[str],
    hypotheses: list[str],
    glossary: Glossary,
    label: str = "",
) -> TermRecall:
    """발화 묶음에 대한 용어 재현율.

    분모는 **정답 전사에 실제로 등장한 용어**다. 용어집 전체가 아니다.
    말한 적 없는 용어를 못 맞췄다고 감점하면 지표가 무의미해진다.

    같은 용어가 여러 발화에 나오면 각각을 따로 센다. 자주 쓰는 용어를
    반복해서 틀리는 것은 실제로 더 나쁘다.
    """
    if len(references) != len(hypotheses):
        raise ValueError(f"발화 수가 다릅니다: 정답 {len(references)}개, 가설 {len(hypotheses)}개")

    result = TermRecall(label=label)
    for reference, hypothesis in zip(references, hypotheses, strict=True):
        for term in glossary.canonical_terms():
            if not contains_term(reference, term):
                continue  # 이 발화에 없던 용어는 채점 대상이 아니다
            if contains_term(hypothesis, term):
                result.hits.append(term)
            else:
                result.misses.append(term)
    return result


def miss_counts(result: TermRecall) -> list[tuple[str, int]]:
    """어떤 용어를 몇 번 놓쳤는가. 많이 놓친 순.

    용어집을 손볼 근거가 된다. 특정 용어가 계속 안 잡히면 그 용어의
    `variants`나 `spoken`을 보강해야 한다는 신호다.
    """
    from collections import Counter

    return Counter(result.misses).most_common()
