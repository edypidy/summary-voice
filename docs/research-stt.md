# STT 용어 바이어싱 리서치 (2026-07-29 조사)

README 섹션 7.2의 레이어 1(디코딩 시점 바이어싱) 벤더 선택을 위한 조사.
**핵심 질문: 바이어싱 기능이 한국어를 지원하는가.** 전사만 되는 것과 바이어싱이
되는 것은 다르다. 대부분의 벤더 문서가 이 둘을 구분해 쓰지 않는다.

## 결론

| 서비스 | 기능 | **한국어 바이어싱** | 상한 |
|---|---|---|---|
| Deepgram Nova-3 | Keyterm Prompting (`language=ko`) | **지원** (단, 근거가 블로그) | 500 토큰 ≈ 100단어 |
| Deepgram Nova-3 | Keyterm (`language=multi`) | **미지원** — multi 집합에 한국어 없음 | 500 토큰 |
| AssemblyAI Universal-3.5 Pro | `keyterms_prompt` | **미지원** — 언어 목록에 한국어 없음 | 1,000 단어 |
| AssemblyAI Universal-2 | `keyterms_prompt` | **미지원** — 영어 베타 전용 | 200 |

Deepgram이 유일한 후보다. 단, **커밋 전에 실측할 것**. 이유는 아래.

## 왜 근거가 약한가

- Deepgram의 Keyterm 문서 페이지에는 **언어별 표가 없다.** "Nova-3 모델에서
  monolingual/multilingual 모두 지원"이라고만 쓰여 있다.
- 한국어를 명시한 것은 자사 **블로그**다: "With Nova-3, Keyterm Prompting is now
  available across all 11 languages" — 이 11개에 `ko`/`ko-KR`이 포함.
  대응 체인지로그 2025-11-04.
- 즉 1차 문서 확인이 아니라 마케팅 문서 확인이다.
- `language=multi` 집합(en, es, fr, de, hi, ru, pt, ja, it, nl)에는 한국어가 없다.
  **반드시 `model=nova-3&language=ko`로 호출해야 한다.** multi 경로는 안 된다.
- 100개라는 숫자는 별도 상한이 아니라 500토큰의 근사치다. 우리 용어집 상한
  100개와 우연히 맞아떨어진다.

## 알려진 문제

- **한국어 띄어쓰기 회귀** ([Deepgram discussion #1452](https://github.com/orgs/deepgram/discussions/1452), 2025-11-05):
  Nova-3 한국어 전사가 **단어 사이 공백 없이** 나온다. Nova-2에서의 회귀.
  워드 단위 타임스탬프는 정상이라 내부 분절은 되고 있다. 2026-05-17에 Deepgram
  측이 "다음 주 수정"이라 답했으나 약 18개월 열려 있던 이슈다.
  → **용어 재현율 측정 시 공백을 정규화하고 매칭해야 한다.** 안 그러면 한국어
  성능을 실제보다 나쁘게 잰다.
- **키텀 과잉 적용** ([discussion #1233](https://github.com/orgs/deepgram/discussions/1233), 2025-05):
  키텀을 억지로 끼워 맞춘다 ("Fahad" → "Fathom"). Deepgram 측 답변: "keyterm
  prompting is contextual and model driven... does not work in the same way that
  keyword boosting works."
  → 용어집이 크면 오히려 해로울 수 있다. 100개 상한이 방어책이 된다.

## 확인 못 한 것

- **한국어 + Keyterm 조합의 독립 사용 후기가 하나도 없다.** Reddit, HN, GitHub
  어디에도. 검색 실패가 아니라 실제로 아무도 안 써본 영역으로 보인다.
- Nova-4는 **공식 문서에 존재하지 않는다.** 일부 서드파티 블로그가 WER 수치와
  함께 언급하나 Deepgram 확인 없음. 신뢰하지 말 것.
- faster-whisper `hotwords`의 한국어 동작, Google Chirp / OpenAI 계열은
  이번 조사에서 확인하지 못했다 (조사 중단).

## 이 프로젝트에 미치는 영향

README 섹션 7.3의 비교군 설계가 그대로 유효하고, 오히려 더 중요해졌다:

> (a) 베이스라인 (b) 레이어 1만 (c) 레이어 1+2 (d) 레이어 2만
> **(d)가 (c)와 비슷하면 레이어 1은 버린다.**

레이어 1의 한국어 근거가 이렇게 얇으므로 **레이어 2(용어집 기반 LLM 교정)를
주력으로 놓고 먼저 구현한다.** 레이어 1은 (b)/(c) 측정을 위해서만 붙이고,
(d)가 충분하면 벤더 의존성을 통째로 없앤다. 복잡도와 비용 모두 줄어든다.
