"""sv-glossary — 레포에서 용어집을 뽑아 <project>/.assistant/glossary.json 에 쓴다."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from summary_voice.glossary.build import build
from summary_voice.glossary.models import MAX_TERMS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sv-glossary",
        description="레포에서 프로젝트 전문 용어집을 자동 추출한다.",
    )
    parser.add_argument("project", type=Path, help="대상 프로젝트 경로")
    parser.add_argument(
        "-n", "--limit", type=int, default=MAX_TERMS,
        help=f"남길 용어 수 (기본 {MAX_TERMS}). STT 바이어싱 API 제한을 고려해 정한다.",
    )
    parser.add_argument(
        "-s", "--source", action="append", dest="sources",
        choices=["python", "config", "tex", "git", "docs"],
        help="특정 소스만 사용 (반복 지정 가능). 기본은 전부.",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="출력 경로 (기본: <project>/.assistant/glossary.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 표만 출력")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
    )

    project = args.project.resolve()
    if not project.is_dir():
        print(f"경로가 없거나 디렉터리가 아님: {project}", file=sys.stderr)
        return 1

    glossary = build(project, limit=args.limit, sources=args.sources)

    width = max((len(t.canonical) for t in glossary), default=10)
    for i, term in enumerate(glossary, 1):
        print(f"{i:3d}. {term.canonical:<{width}}  {','.join(sorted(set(term.sources)))}")
    print(f"\n{len(glossary)}개 용어", file=sys.stderr)

    if args.dry_run:
        return 0

    out = args.output or project / ".assistant" / "glossary.json"
    glossary.save(out)
    print(f"→ {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
