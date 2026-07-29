"""레이어 2: 용어집 기반 LLM 교정 (README 섹션 7.2).

전사문 + 프로젝트 용어집을 작은 모델에 넘겨 **오인식된 전문용어만** 고친다.

이 모듈이 진짜로 방어하는 것은 LLM이 아니라 LLM의 과잉 교정이다.
"교정해줘"라고 하면 모델은 멀쩡한 문장까지 다듬고 싶어한다. 그러면 사용자가
실제로 한 말이 아닌 게 나오고, 그건 오인식보다 나쁘다. 무슨 말을 했는지
모르는 것보다 잘못 알아들은 걸 확신하는 게 더 위험하다.

그래서 모델 출력을 그대로 믿지 않고 `is_term_only_edit`으로 검증한 뒤,
용어가 아닌 부분을 건드렸으면 **원문을 그대로 돌려준다.**
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

from summary_voice.glossary.models import Glossary
from summary_voice.llm import LLMClient
from summary_voice.stt.metrics import term_pattern

log = logging.getLogger(__name__)

SYSTEM = """\
너는 한국어 음성 전사문의 전문용어 교정기다.

입력은 한국어 문장에 영어 전문용어가 섞인 발화를 음성인식한 결과다.
음성인식기는 영어 전문용어를 자주 틀린다 ("LoRA-XS" → "로라 익스에스").

용어집을 참고해 **오인식된 전문용어만** 정식 표기로 고쳐라.

반드시 지켜라:
- 용어가 아닌 부분은 한 글자도 바꾸지 마라. 어색한 문장, 비문, 반복, 말더듬,
  조사 오류도 그대로 둬라. 다듬지 마라.
- 용어집에 없는 말을 용어집 항목으로 바꾸지 마라.
- 확신이 없으면 그냥 둬라. 잘못 고치는 것보다 안 고치는 게 낫다.
- 설명하지 마라. 교정된 문장만 출력해라."""


@dataclass
class Correction:
    original: str
    corrected: str
    applied: bool
    reason: str = ""

    @property
    def text(self) -> str:
        """실제로 쓸 문자열. 거부된 교정은 원문이다."""
        return self.corrected if self.applied else self.original


def _term_coverage(text: str, terms: list[str]) -> int:
    """`text`에서 용어집 항목이 차지하는 글자 수 (중복 구간은 한 번만).

    "이 구간에 용어가 있느냐"가 아니라 "이 구간에서 용어가 **얼마나**를
    설명하느냐"를 재야 한다. 전자로 재면 모델이 용어 하나를 끼워 넣은 채
    장광설을 덧붙여도 통과한다.
    """
    covered: set[int] = set()
    for term in terms:
        for match in term_pattern(term).finditer(text):
            covered.update(range(match.start(), match.end()))
    return len(covered)


def is_term_only_edit(original: str, corrected: str, glossary: Glossary) -> tuple[bool, str]:
    """교정이 **용어만** 건드렸는지 검사한다.

    바뀐 구간마다 "이 편집 중 용어집 항목으로 설명되는 부분이 얼마인가"를 본다.
    설명되지 않는 글자가 쌓이면 모델이 문장을 고쳐 쓴 것이다.

    공백·문장부호 수준의 자잘한 차이는 통과시킨다. 그것까지 막으면 정상 교정도
    거부된다.
    """
    if original == corrected:
        return True, "변경 없음"

    terms = glossary.canonical_terms()
    stray = 0

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, original, corrected).get_opcodes():
        if tag == "equal":
            continue
        deleted, inserted = original[i1:i2], corrected[j1:j2]
        term_chars = _term_coverage(inserted, terms)

        # 삽입 쪽: 용어로 설명되지 않는 글자가 곧 덧붙인 말이다.
        stray_insert = len(inserted) - term_chars
        # 삭제 쪽: 지워진 것은 오인식된 용어였을 것이다. 오인식은 정식 표기보다
        # 길어지기 쉬우므로("LoRA-XS" → "로라 익스에스") 넉넉히 두 배까지 인정한다.
        stray_delete = max(0, len(deleted) - term_chars * 2)

        stray += max(stray_insert, stray_delete)

    # 공백/문장부호 정도는 봐준다. 원문의 10% 또는 4자 중 큰 쪽까지.
    budget = max(4, len(original) // 10)
    if stray > budget:
        return False, f"용어와 무관한 부분을 {stray}자 고쳤습니다 (허용 {budget}자)"
    return True, "용어만 교정됨"


def _glossary_block(glossary: Glossary, limit: int = 100) -> str:
    lines = []
    for term in list(glossary)[:limit]:
        variants = ", ".join(term.variants[:6])
        lines.append(f"- {term.canonical}" + (f"  (오인식 예: {variants})" if variants else ""))
    return "\n".join(lines)


def correct(
    transcript: str,
    glossary: Glossary,
    client: LLMClient,
) -> Correction:
    """전사문 한 건을 교정한다.

    어떤 이유로든 실패하면 원문을 그대로 돌려준다. 교정 단계가 파이프라인을
    막으면 안 된다.
    """
    transcript = transcript.strip()
    if not transcript:
        return Correction(transcript, transcript, applied=False, reason="빈 입력")
    if not len(glossary):
        return Correction(transcript, transcript, applied=False, reason="용어집이 비어 있음")

    user = f"용어집:\n{_glossary_block(glossary)}\n\n전사문:\n{transcript}"
    # 교정문은 입력과 길이가 비슷하다. 넉넉하게 두 배 + 여유.
    result = client.text(SYSTEM, user, max_tokens=len(transcript) * 2 + 200)

    if result is None:
        return Correction(transcript, transcript, applied=False, reason="LLM 호출 실패")

    ok, reason = is_term_only_edit(transcript, result, glossary)
    if not ok:
        log.warning("과잉 교정을 거부했습니다: %s\n  원문: %s\n  출력: %s", reason, transcript, result)
        return Correction(transcript, result, applied=False, reason=reason)

    return Correction(transcript, result, applied=True, reason=reason)


def correct_all(
    transcripts: list[str],
    glossary: Glossary,
    client: LLMClient,
) -> list[str]:
    """여러 건을 교정한다. 평가(README 섹션 7.3)에서 비교군 (c)/(d)를 만드는 데 쓴다."""
    return [correct(t, glossary, client).text for t in transcripts]
