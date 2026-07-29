"""프로젝트별 전문 용어집 자동 추출 (README 섹션 7.1).

손으로 쓰지 않는다. 레포에서 뽑는다. 전역 용어집은 만들지 않는다.
"""

from summary_voice.glossary.models import Glossary, Term

__all__ = ["Glossary", "Term"]
