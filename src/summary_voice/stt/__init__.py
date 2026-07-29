"""STT 파이프라인 (README 섹션 7.2).

    오디오 → [레이어 1: 디코딩 시점 바이어싱] → 원시 전사
          → [레이어 2: 용어집 기반 LLM 교정] → 최종 텍스트

레이어 2가 주력이다. 한국어 바이어싱의 벤더 근거가 얇기 때문
(docs/research-stt.md). 평가에서 레이어 2만으로 충분하다고 나오면
레이어 1은 버린다.
"""

from summary_voice.stt.metrics import TermRecall, term_recall

__all__ = ["TermRecall", "term_recall"]
