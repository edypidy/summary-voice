import pytest

from summary_voice.glossary.models import Glossary, Term
from summary_voice.stt.metrics import contains_term, miss_counts, term_recall


def glossary(*names):
    return Glossary(project="t", terms=[Term(canonical=n) for n in names])


class TestKoreanParticleAttachment:
    """README 섹션 7.3이 지목한 함정. 영어 용어 뒤에 조사가 바로 붙는다."""

    @pytest.mark.parametrize(
        "text",
        [
            "LoRA-XS가 발산해요",
            "LoRA-XS를 붙였어요",
            "LoRA-XS는 괜찮은데",
            "LoRA-XS에서 문제가 생겼어요",
            "LoRA-XS랑 비교해봐",
        ],
    )
    def test_finds_term_before_particle(self, text):
        assert contains_term(text, "LoRA-XS")

    def test_finds_term_at_sentence_end(self):
        assert contains_term("문제는 Sinkhorn", "Sinkhorn")

    def test_공백_토큰화로는_안_잡히는_경우(self):
        # 순진하게 text.split() 했으면 "LoRA-XS가"는 "LoRA-XS"와 다른 토큰이다.
        # split() 호출이 이 테스트의 요점이다. 리터럴로 바꾸면 보여주려는 게 사라진다.
        assert "LoRA-XS" not in "LoRA-XS가 발산해요".split()  # noqa: SIM905
        assert contains_term("LoRA-XS가 발산해요", "LoRA-XS")


class TestSeparatorTolerance:
    """STT는 구분자를 제멋대로 뱉는다. Deepgram 한국어는 공백을 아예 뺀다."""

    @pytest.mark.parametrize(
        "hypothesis", ["LoRA-XS 로스", "LoRA XS 로스", "lora xs 로스", "loraxs 로스", "LoRA_XS 로스"]
    )
    def test_accepts_separator_variants(self, hypothesis):
        assert contains_term(hypothesis, "LoRA-XS")

    def test_no_space_at_all(self):
        # Nova-3 한국어 띄어쓰기 회귀 시나리오 (docs/research-stt.md)
        assert contains_term("Sinkhorn정규화가발산합니다", "Sinkhorn")


class TestBoundaries:
    def test_rejects_longer_latin_identifier(self):
        # "Sinkhorn"을 "Sinkhorn2"나 "SinkhornOT"로 잘못 맞다고 하면 안 된다.
        assert not contains_term("SinkhornOT를 썼어요", "Sinkhorn")
        assert not contains_term("Sinkhorn2 결과", "Sinkhorn")

    def test_rejects_term_embedded_in_word(self):
        assert not contains_term("preSinkhorn", "Sinkhorn")

    def test_case_insensitive(self):
        assert contains_term("SINKHORN 루프", "Sinkhorn")
        assert contains_term("sinkhorn 루프", "Sinkhorn")


class TestTermRecall:
    def test_counts_only_terms_present_in_reference(self):
        # 용어집에 100개가 있어도 정답에 나온 것만 채점한다.
        g = glossary("LoRA-XS", "Sinkhorn", "PEFT")
        r = term_recall(["LoRA-XS가 발산해요"], ["로라 익스에스가 발산해요"], g, label="baseline")
        assert r.total == 1  # Sinkhorn, PEFT는 말한 적이 없다
        assert r.misses == ["LoRA-XS"]
        assert r.recall == 0.0

    def test_perfect_transcription(self):
        g = glossary("LoRA-XS", "Sinkhorn")
        r = term_recall(
            ["LoRA-XS와 Sinkhorn을 비교했어요"], ["LoRA-XS와 Sinkhorn을 비교했어요"], g
        )
        assert r.recall == 1.0
        assert r.total == 2

    def test_partial(self):
        g = glossary("LoRA-XS", "Sinkhorn")
        r = term_recall(["LoRA-XS와 Sinkhorn"], ["LoRA-XS와 신콘"], g)
        assert r.recall == 0.5
        assert r.hits == ["LoRA-XS"]
        assert r.misses == ["Sinkhorn"]

    def test_repeated_term_counted_each_utterance(self):
        # 자주 쓰는 용어를 반복해서 틀리는 건 실제로 더 나쁘다.
        g = glossary("Sinkhorn")
        r = term_recall(["Sinkhorn 하나", "Sinkhorn 둘"], ["신콘 하나", "신콘 둘"], g)
        assert r.total == 2
        assert r.recall == 0.0

    def test_empty_reference_terms_is_not_a_penalty(self):
        g = glossary("LoRA-XS")
        r = term_recall(["배치 사이즈 줄여줘"], ["배치 사이즈 줄여줘"], g)
        assert r.total == 0
        assert r.recall == 1.0

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="발화 수가 다릅니다"):
            term_recall(["a", "b"], ["a"], glossary("X"))

    def test_miss_counts_ranks_worst_terms_first(self):
        g = glossary("Sinkhorn", "PEFT")
        r = term_recall(
            ["Sinkhorn", "Sinkhorn", "PEFT"], ["신콘", "신콘", "페프트"], g
        )
        assert miss_counts(r)[0] == ("Sinkhorn", 2)


class TestReporting:
    def test_str_is_readable(self):
        g = glossary("Sinkhorn")
        assert "50.0%" in str(term_recall(["Sinkhorn", "Sinkhorn"], ["Sinkhorn", "신콘"], g, "c"))
