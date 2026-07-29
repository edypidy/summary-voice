from summary_voice.glossary.variants import humanize, split_identifier, variants_of


class TestSplitIdentifier:
    def test_snake_case(self):
        assert split_identifier("hierarchical_cross_attention") == [
            "hierarchical", "cross", "attention",
        ]

    def test_strips_known_extensions(self):
        assert split_identifier("train_lora.py") == ["train", "lora"]
        assert split_identifier("config.yaml") == ["config"]

    def test_camel_case(self):
        assert split_identifier("SinkhornLoss") == ["Sinkhorn", "Loss"]

    def test_acronym_followed_by_word(self):
        # 연속 대문자 뒤에 단어가 오면 그 경계에서 끊는다.
        assert split_identifier("LoRAModel") == ["LoRA", "Model"]
        assert split_identifier("OTLoss") == ["OT", "Loss"]

    def test_mixed_separators(self):
        assert split_identifier("LoRA-XS_v2") == ["LoRA", "XS", "v2"]


class TestHumanize:
    def test_readme_example(self):
        # README 섹션 6.3: 내레이션은 긴 식별자를 그대로 읽으면 안 된다.
        assert humanize("hierarchical_cross_attention.py") == "hierarchical cross attention"

    def test_camel_case(self):
        assert humanize("SinkhornOTLoss") == "Sinkhorn OT Loss"

    def test_leaves_plain_word_alone(self):
        assert humanize("Sinkhorn") == "Sinkhorn"

    def test_never_returns_empty(self):
        assert humanize(".py") == ".py"


class TestVariantsOf:
    def test_generates_spoken_separations(self):
        v = variants_of("LoRA-XS")
        assert "LoRA XS" in v
        assert "lora xs" in v
        assert "loraxs" in v

    def test_excludes_canonical_itself(self):
        assert "LoRA-XS" not in variants_of("LoRA-XS")

    def test_single_word_still_gives_lowercase(self):
        assert "sinkhorn" in variants_of("Sinkhorn")

    def test_empty_input_is_safe(self):
        assert variants_of("") == []
