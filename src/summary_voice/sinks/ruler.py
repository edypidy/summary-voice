"""Phase 0 계측: 알림 낭독이 잘리지 않는 최대 글자 수를 실측한다.

README 섹션 6.3의 `max_chars`는 잠정 200자다. Phase 0 합격 기준이 "낭독이
잘리지 않는 최대 글자 수를 실측했을 것"이므로, 추측 대신 자를 대야 한다.

방법: 길이가 다른 메시지를 순서대로 보낸다. 각 메시지는 **끝에 신호음 문장**이
붙어 있다. 이어폰으로 들으면서 신호가 들리는 마지막 길이가 곧 실측값이다.

신호를 문장 끝에 두는 게 핵심이다. 앞에 두면 잘렸는지 알 수 없다.
"""

from __future__ import annotations

# 실제 내레이션과 비슷한 문장이어야 의미가 있다. 한국어에 영어 전문용어가
# 섞인 형태 - 사용자의 실제 발화 프로파일(README 섹션 1)과 같은 조합이다.
_FILLER = [
    "1번 에이전트가 크로스 어텐션 모듈 리팩터링을 끝냈습니다.",
    "Sinkhorn 정규화 루프에서 loss가 발산해서 스텝 수를 줄이는 중입니다.",
    "LoRA-XS 어댑터를 붙인 뒤 학습 속도가 눈에 띄게 빨라졌습니다.",
    "테스트 세 개가 실패했는데 전부 데이터 로더 쪽 문제로 보입니다.",
    "2번 에이전트는 평가 스크립트를 새로 짜고 있습니다.",
    "체크포인트 저장 경로가 겹쳐서 이전 결과를 덮어쓸 뻔했습니다.",
    "STE hard selection을 켜니까 그래디언트가 흐르지 않습니다.",
    "PEFT 설정을 바꿔서 다시 돌려보는 중입니다.",
]

# 기본 측정 구간. 200자 근처를 촘촘히 본다 - 거기가 현재 잠정값이라
# 맞는지 틀리는지가 가장 중요하다.
DEFAULT_LENGTHS = [80, 120, 160, 200, 240, 280, 340, 400, 500]


def _spoken_number(n: int) -> str:
    """길이를 귀로 구분되게 읽어준다. 숫자를 그냥 쓰면 TTS가 뭉갠다."""
    return f"{n}"


def build_probe(length: int) -> str:
    """정확히 `length`자 근처이면서 끝에 신호가 붙은 메시지를 만든다.

    신호 문장은 온전히 보존한다. 자르는 건 앞쪽 채움말이다.
    """
    sentinel = f" 여기까지 {_spoken_number(length)}자입니다."
    budget = length - len(sentinel)
    if budget <= 0:
        return sentinel.strip()

    body = ""
    i = 0
    while len(body) < budget:
        body += _FILLER[i % len(_FILLER)] + " "
        i += 1
    body = body[:budget].rstrip()
    return body + sentinel


def build_probes(lengths: list[int] | None = None) -> list[tuple[int, str]]:
    """(길이, 메시지) 목록."""
    return [(n, build_probe(n)) for n in (lengths or DEFAULT_LENGTHS)]
