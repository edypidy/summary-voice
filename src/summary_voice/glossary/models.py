"""용어집 자료구조와 직렬화.

용어집은 두 곳에서 쓰인다:
  - STT 레이어 1/2: 오인식된 전문용어 교정 (섹션 7.2)
  - 내레이션: 긴 식별자를 귀로 듣기 좋게 바꾸기 (섹션 6.3)
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# 프로젝트당 상한. README 섹션 7.1: 100개 이하로 유지되어야
# 대부분의 STT 바이어싱 API 제한 안에 들어가고 정확도도 더 높다.
MAX_TERMS = 100


def _uppercase_score(name: str) -> int:
    """정식 표기 후보끼리 비교할 때 쓰는 점수. 대문자가 많을수록 높다."""
    return sum(c.isupper() for c in name)


@dataclass
class Term:
    """용어집 한 항목.

    canonical: 정식 표기. 교정 결과로 쓰이는 문자열.
    variants:  STT가 뱉을 법한 오인식/표기 변형. 교정의 검색 키.
    spoken:    내레이션에서 읽을 한국어 표현. 없으면 canonical을 그대로 읽는다.
    sources:   어디서 추출됐는지 ("python:class", "config", "tex", "git", "docs").
               출처가 여러 개면 그만큼 프로젝트 고유 용어일 가능성이 높다.
    count:     레포 전체 등장 횟수. 랭킹에 쓴다.
    """

    canonical: str
    variants: list[str] = field(default_factory=list)
    spoken: str | None = None
    sources: list[str] = field(default_factory=list)
    count: int = 1

    @property
    def salience(self) -> float:
        """랭킹 점수. 출처 다양성을 빈도보다 강하게 본다.

        `train` 같은 흔한 함수명은 python에서만 100번 나오고,
        `LoRA-XS` 같은 고유 용어는 python·tex·git·docs 네 곳에서 나온다.
        후자가 우리가 원하는 것이다.
        """
        # 빈도는 로그로 눌러서 흔한 이름이 순위를 독식하지 못하게 한다.
        from math import log

        return len(set(self.sources)) * 10.0 + log(self.count + 1)

    def to_dict(self) -> dict:
        d: dict = {"canonical": self.canonical, "variants": sorted(set(self.variants))}
        if self.spoken:
            d["spoken"] = self.spoken
        d["sources"] = sorted(set(self.sources))
        d["count"] = self.count
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Term:
        return cls(
            canonical=d["canonical"],
            variants=list(d.get("variants", [])),
            spoken=d.get("spoken"),
            sources=list(d.get("sources", [])),
            count=int(d.get("count", 1)),
        )


@dataclass
class Glossary:
    project: str
    terms: list[Term] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self):
        return iter(self.terms)

    def top(self, n: int = MAX_TERMS) -> Glossary:
        """살리언스 상위 n개만 남긴 새 용어집."""
        ranked = sorted(self.terms, key=lambda t: (-t.salience, t.canonical.lower()))
        return Glossary(project=self.project, terms=ranked[:n])

    def canonical_terms(self) -> list[str]:
        """STT 바이어싱(레이어 1)에 넘길 문자열 목록."""
        return [t.canonical for t in self.terms]

    def lookup(self, text: str) -> Term | None:
        """canonical 또는 variant와 대소문자 무시하고 일치하는 항목."""
        key = text.strip().lower()
        for t in self.terms:
            if t.canonical.lower() == key or any(v.lower() == key for v in t.variants):
                return t
        return None

    def merge(self, others: Iterable[Term]) -> None:
        """추출기 결과를 합친다. canonical이 같으면 출처·빈도·변형을 누적."""
        index = {t.canonical.lower(): t for t in self.terms}
        for other in others:
            existing = index.get(other.canonical.lower())
            if existing is None:
                self.terms.append(other)
                index[other.canonical.lower()] = other
                continue
            existing.count += other.count
            existing.sources.extend(other.sources)
            existing.variants.extend(other.variants)
            existing.spoken = existing.spoken or other.spoken
            # 같은 용어의 표기가 여럿이면 대문자가 많은 쪽을 정식 표기로 삼는다.
            # `fid.py`의 "fid"보다 문서의 "FID", "unet"보다 "UNet"이 맞는 표기다.
            if _uppercase_score(other.canonical) > _uppercase_score(existing.canonical):
                existing.variants.append(existing.canonical)
                existing.canonical = other.canonical
            existing.variants = [v for v in existing.variants if v != existing.canonical]

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "term_count": len(self.terms),
            "terms": [t.to_dict() for t in self.terms],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 원자적 쓰기. Relay가 동시에 읽고 있어도 반쯤 쓰인 파일을 보지 않게.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Glossary:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            project=data.get("project", ""),
            terms=[Term.from_dict(t) for t in data.get("terms", [])],
        )
