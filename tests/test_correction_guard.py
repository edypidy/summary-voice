"""과잉 교정 가드 테스트.

이 가드가 이 모듈의 존재 이유다. 리서치에서 확인된 실패 모드는 LLM이 용어를
고치는 김에 멀쩡한 문장까지 다듬어버리는 것이다 (docs/research-stt.md).
"""

import pytest

from summary_voice.glossary.models import Glossary, Term
from summary_voice.stt.correct import Correction, correct, is_term_only_edit


@pytest.fixture
def glossary():
    return Glossary(
        project="t",
        terms=[
            Term("LoRA-XS", variants=["로라 익스에스", "로라 XS"]),
            Term("Sinkhorn", variants=["신콘", "싱크혼"]),
            Term("cross-attention", variants=["크로스 어텐션"]),
        ],
    )


class TestAcceptsRealCorrections:
    def test_term_replacement(self, glossary):
        ok, _ = is_term_only_edit("로라 익스에스가 발산해요", "LoRA-XS가 발산해요", glossary)
        assert ok

    def test_two_terms_in_one_sentence(self, glossary):
        ok, _ = is_term_only_edit(
            "신콘 정규화랑 로라 익스에스를 같이 써봤어요",
            "Sinkhorn 정규화랑 LoRA-XS를 같이 써봤어요",
            glossary,
        )
        assert ok

    def test_no_change_at_all(self, glossary):
        ok, reason = is_term_only_edit("배치 사이즈 줄여줘", "배치 사이즈 줄여줘", glossary)
        assert ok
        assert reason == "변경 없음"

    def test_tolerates_whitespace_touchup(self, glossary):
        ok, _ = is_term_only_edit("신콘 루프요", "Sinkhorn 루프요.", glossary)
        assert ok


class TestRejectsOvercorrection:
    def test_rewriting_the_sentence(self, glossary):
        # 용어는 맞게 고쳤지만 문장까지 다듬었다. 사용자가 한 말이 아니게 된다.
        ok, reason = is_term_only_edit(
            "어 그 로라 익스에스가 좀 이상한데 발산하는 것 같기도 하고",
            "LoRA-XS의 손실이 발산하는 것으로 보입니다.",
            glossary,
        )
        assert not ok
        assert "용어와 무관한" in reason

    def test_fixing_disfluency_is_rejected(self, glossary):
        # 말더듬을 지우는 것도 과잉 교정이다. 원문 그대로가 진실이다.
        ok, _ = is_term_only_edit(
            "그 그 그러니까 신콘 그거를 좀 봐야 될 것 같은데요",
            "Sinkhorn을 확인해야 할 것 같습니다",
            glossary,
        )
        assert not ok

    def test_translating_to_english_is_rejected(self, glossary):
        ok, _ = is_term_only_edit("신콘 루프가 느려요", "The Sinkhorn loop is slow", glossary)
        assert not ok

    def test_appending_explanation_is_rejected(self, glossary):
        ok, _ = is_term_only_edit(
            "신콘 루프",
            "Sinkhorn 루프 (교정: '신콘'을 'Sinkhorn'으로 바꿨습니다)",
            glossary,
        )
        assert not ok


class TestCorrectionResult:
    def test_rejected_correction_yields_original_text(self):
        c = Correction("원문입니다", "완전히 다른 문장", applied=False, reason="과잉")
        assert c.text == "원문입니다"

    def test_applied_correction_yields_corrected_text(self):
        c = Correction("신콘", "Sinkhorn", applied=True)
        assert c.text == "Sinkhorn"


class TestCorrectFallsBackSafely:
    """어떤 실패도 원문 반환으로 끝나야 한다."""

    def test_llm_failure_returns_original(self, glossary):
        class DeadClient:
            def text(self, *a, **k):
                return None  # 네트워크 오류 등으로 None

        result = correct("신콘 루프요", glossary, DeadClient())
        assert result.text == "신콘 루프요"
        assert not result.applied

    def test_empty_glossary_returns_original(self):
        class Unused:
            def text(self, *a, **k):
                raise AssertionError("용어집이 비면 호출하면 안 된다")

        result = correct("신콘 루프요", Glossary(project="t"), Unused())
        assert result.text == "신콘 루프요"

    def test_overcorrection_returns_original(self, glossary):
        class Chatty:
            def text(self, *a, **k):
                return "안녕하세요! 교정된 문장은 다음과 같습니다: Sinkhorn 루프입니다."

        result = correct("신콘 루프요", glossary, Chatty())
        assert result.text == "신콘 루프요"
        assert not result.applied

    def test_good_correction_is_applied(self, glossary):
        class Good:
            def text(self, *a, **k):
                return "Sinkhorn 루프요"

        result = correct("신콘 루프요", glossary, Good())
        assert result.text == "Sinkhorn 루프요"
        assert result.applied
