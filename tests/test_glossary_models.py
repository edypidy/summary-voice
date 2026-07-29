from summary_voice.glossary.models import Glossary, Term


def make(canonical, sources, count=1):
    return Term(canonical=canonical, sources=list(sources), count=count)


class TestMerge:
    def test_accumulates_sources_and_counts(self):
        g = Glossary(project="p", terms=[make("DDPM", ["docs"], 3)])
        g.merge([make("DDPM", ["git"], 2)])
        assert len(g) == 1
        assert set(g.terms[0].sources) == {"docs", "git"}
        assert g.terms[0].count == 5

    def test_case_insensitive_dedup(self):
        g = Glossary(project="p", terms=[make("fid", ["python:module"])])
        g.merge([make("FID", ["docs"])])
        assert len(g) == 1

    def test_prefers_more_uppercase_as_canonical(self):
        # `fid.py`의 "fid"보다 문서의 "FID"가 정식 표기다.
        g = Glossary(project="p", terms=[make("fid", ["python:module"])])
        g.merge([make("FID", ["docs"])])
        assert g.terms[0].canonical == "FID"
        assert "fid" in g.terms[0].variants

    def test_does_not_downgrade_canonical(self):
        g = Glossary(project="p", terms=[make("UNet", ["python:class"])])
        g.merge([make("unet", ["config"])])
        assert g.terms[0].canonical == "UNet"

    def test_canonical_never_appears_in_its_own_variants(self):
        g = Glossary(project="p", terms=[make("fid", ["python:module"])])
        g.merge([make("FID", ["docs"])])
        assert g.terms[0].canonical not in g.terms[0].variants


class TestRanking:
    def test_source_diversity_beats_raw_frequency(self):
        # `train`은 한 소스에서 500번, `LoRA-XS`는 네 소스에서 3번.
        # 프로젝트를 식별해주는 건 후자다.
        common = make("train_step", ["python:function"], count=500)
        distinctive = make("LoRA-XS", ["docs", "git", "tex", "python:class"], count=3)
        g = Glossary(project="p", terms=[common, distinctive])
        assert g.top(1).terms[0].canonical == "LoRA-XS"

    def test_top_respects_limit(self):
        g = Glossary(project="p", terms=[make(f"Term{i}", ["docs"]) for i in range(50)])
        assert len(g.top(10)) == 10

    def test_top_is_stable_for_ties(self):
        g = Glossary(project="p", terms=[make("Beta", ["docs"]), make("Alpha", ["docs"])])
        assert [t.canonical for t in g.top(2)] == ["Alpha", "Beta"]


class TestLookup:
    def test_matches_variant_case_insensitively(self):
        g = Glossary(project="p", terms=[Term("LoRA-XS", variants=["로라 XS", "lora xs"])])
        assert g.lookup("LORA XS").canonical == "LoRA-XS"
        assert g.lookup("로라 XS").canonical == "LoRA-XS"

    def test_returns_none_when_absent(self):
        assert Glossary(project="p").lookup("Sinkhorn") is None


class TestRoundTrip:
    def test_save_load_preserves_terms(self, tmp_path):
        g = Glossary(
            project="proj",
            terms=[Term("LoRA-XS", variants=["로라 XS"], spoken="로라 엑스에스", sources=["tex"])],
        )
        path = tmp_path / "glossary.json"
        g.save(path)
        loaded = Glossary.load(path)
        assert loaded.project == "proj"
        assert loaded.terms[0].canonical == "LoRA-XS"
        assert loaded.terms[0].spoken == "로라 엑스에스"
        assert "로라 XS" in loaded.terms[0].variants

    def test_save_leaves_no_temp_file(self, tmp_path):
        path = tmp_path / "glossary.json"
        Glossary(project="p").save(path)
        assert list(tmp_path.iterdir()) == [path]
