"""표기 변형 생성과 식별자 → 낭독용 문자열 변환.

두 가지를 한다:
  - `variants_of`: STT가 뱉을 법한 표기 변형. 결정적(deterministic) 규칙만.
    한글 음차("로라 XS")는 규칙으로 만들 수 없어 LLM 패스에서 채운다 (`enrich.py`).
  - `humanize`: `hierarchical_cross_attention.py` → "hierarchical cross attention".
    내레이션이 경로·긴 식별자를 읽지 않게 하는 데 쓴다 (README 섹션 6.3).
"""

from __future__ import annotations

import re

# camelCase / PascalCase 경계.
#
# 순진하게 `(?<=[a-z0-9])(?=[A-Z])`로 끊으면 대소문자가 섞인 약어가 망가진다.
# "LoRA" -> ["Lo", "RA"]. 이 프로젝트에서 가장 중요한 용어가 바로 그 형태다.
# 그래서 두 규칙 다 앞쪽 문맥을 더 요구한다:
#   1) 소문자/숫자가 **3자 이상** 이어진 뒤의 대문자에서만 끊는다.
#      "SinkhornLoss" -> Sinkhorn|Loss (o,r,n)   "LoRA" -> 안 끊음 (Lo뿐)
#   2) 대문자가 **2자 이상** 이어진 뒤 "대문자+소문자"가 오면 끊는다.
#      "OTLoss" -> OT|Loss,  "LoRAModel" -> LoRA|Model,  "UNet" -> 안 끊음
_CAMEL = re.compile(r"(?<=[a-z0-9]{3})(?=[A-Z])|(?<=[A-Z]{2})(?=[A-Z][a-z])")
_SEPARATORS = re.compile(r"[_\-./\s]+")


def split_identifier(name: str) -> list[str]:
    """식별자를 단어 단위로 쪼갠다. 확장자와 구분자는 버린다."""
    name = re.sub(r"\.(py|ya?ml|json|tex|md|toml|cfg|ini)$", "", name.strip())
    parts: list[str] = []
    for chunk in _SEPARATORS.split(name):
        if chunk:
            parts.extend(p for p in _CAMEL.split(chunk) if p)
    return parts


def humanize(name: str) -> str:
    """식별자를 귀로 듣기 좋은 공백 구분 문자열로.

    >>> humanize("hierarchical_cross_attention.py")
    'hierarchical cross attention'
    >>> humanize("SinkhornOTLoss")
    'Sinkhorn OT Loss'
    """
    parts = split_identifier(name)
    return " ".join(parts) if parts else name


def variants_of(canonical: str) -> list[str]:
    """STT 오인식 후보가 될 표기 변형들. canonical 자신은 제외.

    한글 음차는 여기서 만들지 않는다. 규칙 기반으로는 신뢰할 수 없다.
    """
    parts = split_identifier(canonical)
    if not parts:
        return []

    forms = {
        " ".join(parts),  # LoRA XS
        " ".join(parts).lower(),  # lora xs
        "-".join(parts).lower(),  # lora-xs
        "_".join(parts).lower(),  # lora_xs
        "".join(parts).lower(),  # loraxs
        canonical.lower(),  # lora-xs (원본 구분자 유지)
    }
    # 두 단어 이상일 때만 붙여쓰기 변형이 의미가 있다. 한 단어면 소문자화와 같다.
    forms.discard(canonical)
    forms.discard("")
    return sorted(forms)
