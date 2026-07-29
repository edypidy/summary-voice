"""sv-eval — 용어 재현율 평가 (README 섹션 7.3).

비교군 네 개를 같은 잣대로 잰다:

    (a) baseline    바이어싱 없는 원시 전사
    (b) layer1      디코딩 시점 바이어싱만
    (c) layer1+2    바이어싱 + LLM 교정
    (d) layer2      LLM 교정만

**(d)가 (c)와 비슷하면 레이어 1을 버린다.** 이 도구의 존재 이유가 그 판단이다.
한국어 바이어싱의 벤더 근거가 얇으므로(docs/research-stt.md), 버릴 수 있다면
벤더 의존성과 복잡도를 통째로 없앨 수 있다.

(a)와 (b)는 사람이 데이터 파일에 채워 넣는다. (c)와 (d)는 여기서 만든다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from summary_voice.glossary.models import Glossary
from summary_voice.stt.metrics import TermRecall, miss_counts, term_recall

# (d)가 (c)의 이만큼 안에 들면 레이어 1은 값어치를 못 한 것으로 본다.
LAYER1_WORTH_KEEPING = 0.02


def load_dataset(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number} JSON 파싱 실패: {exc}") from exc
    return records


def _column(records: list[dict], key: str) -> list[str] | None:
    """모든 레코드에 그 열이 채워져 있을 때만 돌려준다.

    일부만 채워진 열로 점수를 내면 비교군끼리 분모가 달라져 무의미해진다.
    """
    values = [r.get(key) for r in records]
    if any(v is None or not str(v).strip() for v in values):
        return None
    return [str(v) for v in values]


def report(results: list[TermRecall], baseline: TermRecall | None) -> None:
    print("\n용어 재현율")
    print("-" * 46)
    for result in results:
        line = f"  {result.label:<22} {result.recall:>6.1%}  ({len(result.hits)}/{result.total})"
        if baseline is not None and result is not baseline:
            delta = result.recall - baseline.recall
            line += f"  {delta:+.1%}"
        print(line)
    print("-" * 46)


def verdict(results: dict[str, TermRecall]) -> str:
    """레이어 1을 유지할지에 대한 판단."""
    c, d = results.get("(c) layer1+2"), results.get("(d) layer2")
    if c is None or d is None:
        return "판단 보류: (c)와 (d)를 모두 측정해야 레이어 1의 값어치를 알 수 있습니다."

    gain = c.recall - d.recall
    if gain <= LAYER1_WORTH_KEEPING:
        return (
            f"레이어 1을 버리세요. (c)가 (d)보다 {gain:+.1%} 나을 뿐입니다.\n"
            "  레이어 2만으로 충분하므로 STT 벤더 의존성과 복잡도를 없앨 수 있습니다."
        )
    return (
        f"레이어 1을 유지하세요. (c)가 (d)보다 {gain:+.1%} 낫습니다.\n"
        "  단, 벤더 락인과 운영 복잡도를 감수할 만한 차이인지 직접 판단하세요."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sv-eval",
        description="용어 재현율로 STT 비교군 네 개를 평가한다 (README 섹션 7.3).",
    )
    parser.add_argument(
        "-d", "--dataset", type=Path, default=Path("data/utterances.jsonl"),
        help="reference/baseline/layer1 이 담긴 JSONL",
    )
    parser.add_argument(
        "-g", "--glossary", type=Path, required=True,
        help="채점 기준 용어집 (<project>/.assistant/glossary.json)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="LLM 교정을 돌리지 않는다 ((c)/(d) 없이 (a)/(b)만 비교)",
    )
    parser.add_argument("--misses", action="store_true", help="가장 많이 놓친 용어를 함께 출력")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)

    if not args.dataset.is_file():
        print(f"데이터셋이 없습니다: {args.dataset}\n  data/README.md 를 참고하세요.", file=sys.stderr)
        return 1
    if not args.glossary.is_file():
        print(f"용어집이 없습니다: {args.glossary}\n  먼저 sv-glossary 를 실행하세요.", file=sys.stderr)
        return 1

    glossary = Glossary.load(args.glossary)
    records = load_dataset(args.dataset)
    references = _column(records, "reference")
    if references is None:
        print("모든 레코드에 reference 가 있어야 합니다.", file=sys.stderr)
        return 1

    print(f"발화 {len(records)}개, 용어집 {len(glossary)}개", file=sys.stderr)

    arms: dict[str, list[str]] = {}
    for key, label in (("baseline", "(a) baseline"), ("layer1", "(b) layer1")):
        column = _column(records, key)
        if column is None:
            print(f"'{key}' 열이 비어 있어 건너뜁니다.", file=sys.stderr)
            continue
        arms[label] = column

    if not arms:
        print(
            "\n채점할 전사 결과가 없습니다.\n"
            "  녹음 후 각 레코드에 baseline / layer1 을 채워 넣으세요 (data/README.md).",
            file=sys.stderr,
        )
        return 1

    if not args.no_llm:
        from summary_voice.llm import LLMClient
        from summary_voice.stt.correct import correct_all

        client = LLMClient.from_config()
        # (c) = 레이어1 위에 교정, (d) = 베이스라인 위에 교정.
        # 같은 교정기를 쓰므로 둘의 차이가 곧 레이어 1의 기여분이다.
        if "(b) layer1" in arms:
            print("(c) 생성 중...", file=sys.stderr)
            arms["(c) layer1+2"] = correct_all(arms["(b) layer1"], glossary, client)
        if "(a) baseline" in arms:
            print("(d) 생성 중...", file=sys.stderr)
            arms["(d) layer2"] = correct_all(arms["(a) baseline"], glossary, client)

    results = {
        label: term_recall(references, hypotheses, glossary, label=label)
        for label, hypotheses in sorted(arms.items())
    }
    ordered = list(results.values())
    report(ordered, results.get("(a) baseline"))

    if args.misses:
        worst = results.get("(d) layer2") or ordered[-1]
        top = miss_counts(worst)[:10]
        if top:
            print(f"\n{worst.label} 이 놓친 용어:")
            for term, count in top:
                print(f"  {count:>3}회  {term}")
            print("\n  반복해서 놓치는 용어는 glossary.json 의 variants 를 보강하세요.")

    print(f"\n판단: {verdict(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
