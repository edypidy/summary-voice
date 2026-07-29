# summary-voice

연구자가 자리를 비운 사이 Claude Code 에이전트가 뭘 하고 있는지를 **이어폰으로 듣게** 해주는 관측 레이어.

`README.md`가 전체 구현 플랜이자 스펙이다. 이 파일은 그 플랜을 코드로 옮길 때 지켜야 할 규약만 담는다.
**작업 전에 README.md를 먼저 읽을 것.** 특히 섹션 3(설계 원칙)과 섹션 10(하지 말아야 할 것).

## 확정된 결정 (README 섹션 9의 답)

| # | 질문 | 답 | 영향 |
|---|---|---|---|
| Q1 | 폰 OS | **Android** | Phase 0 경로가 iOS Announce Notifications가 아님. `docs/phase0-android.md` 참조 |
| Q2 | Claude Code 사용 형태 | **Agent SDK / 헤드리스** | 훅이 아니라 **스트림을 직접 캡처**한다. 통제력이 더 좋음 |
| Q4 | LLM 호출처 | **Anthropic API, Haiku 4.5** (`claude-haiku-4-5-20251001`) | 살리언스 판정 + 내레이션 + STT 교정 모두 |
| Q5 | 전송 채널 | **Telegram** | Slack 아님. 봇 생성이 즉시 되고 음성노트가 자연스러움 |
| Q3 | 디바운스 초기값 | 30초, 시간당 발화 상한 12회 | 실사용 하루 뒤 튜닝. `config.yaml`에서 조정 |

Q1/Q2가 바뀌면 README와 이 표를 **같이** 고칠 것. 코드에만 반영하고 문서를 놔두지 말 것.

## 하드 제약 (위반 시 리뷰에서 반려)

1. **캡처는 논블로킹.** 캡처 계층에서 LLM 호출·TTS·네트워크 I/O 금지. JSON 한 줄을 큐에 쓰고 끝낸다. 훅 경로를 쓸 경우 **항상 exit 0** (2는 블로킹 의미).
2. **관측 실패가 연구 세션을 죽이면 안 된다.** 캡처 코드의 모든 예외는 삼키고 정상 종료한다. 로그만 남긴다.
3. **Relay는 stateless.** 모든 상태는 디스크에. 강제 종료 후 재시작해도 `events.jsonl` + `last_event_offset`으로 이어져야 한다.
4. **Relay는 에이전트가 아니라 단순 API 호출.** 요약기에 툴/파일시스템 권한을 주지 않는다.
5. **전체 트랜스크립트를 매 요약마다 넣지 않는다.** `state.json` + 신규 이벤트 델타만.
6. **용어집은 프로젝트별로 스코프.** 전역 용어집을 만들지 않는다. 프로젝트당 100개 이하.

## 내레이션 규칙 (귀로 듣는 텍스트다)

- 한국어, **3문장 이하**, `config.yaml`의 `max_chars` 이하 (Phase 0 실측 전 잠정 200자)
- 코드 블록·경로·긴 식별자 금지. `hierarchical_cross_attention.py` → "크로스 어텐션 모듈"
- 숫자 최소화. loss 값 나열 금지
- 에이전트가 여럿이면 주어 명시 ("2번 에이전트가...")
- 낭독 적합성 > 텍스트 품질. 읽어서 좋은 요약과 들어서 좋은 요약은 다르다

내레이션 생성 코드를 건드렸으면 `tests/test_narration_constraints.py`가 통과하는지 확인할 것.

## 개발 순서 (역순 검증 - 뒤집지 말 것)

가장 불확실한 것이 뒤쪽(음성 UX)이라 앞쪽(파이프라인)부터 만들면 다 만들고 안 쓰게 된다.

- **Phase 0** 음성 UX 검증 (수동, 코드 거의 없음) ← 여기가 게이트
- **Phase 1** 용어집 + STT 교정 (Phase 0과 병렬 가능)
- **Phase 2** 이벤트 캡처 → 살리언스 → 내레이션 → Telegram
- **Phase 3** Injector / 양방향 (범위 외)

**Phase 0이 불합격이면 Phase 2를 만들지 말 것.** 전송 계층을 재설계해야 한다.

## 레이아웃

```
src/summary_voice/
  capture/    Agent SDK 스트림 리스너 + 훅 폴백. 논블로킹, 큐에 쓰기만
  glossary/   레포에서 용어집 자동 추출 (AST/config/tex/git log)
  stt/        레이어 1 바이어싱 + 레이어 2 LLM 교정 + term recall 평가
  relay/      디바운스 → 살리언스 판정 → 내레이션 생성
  sinks/      Telegram 전송 (인터페이스 뒤에 두어 교체 가능)
docs/         Phase 0 셋업 가이드, 리서치 노트, 결정 기록
data/         평가용 녹음 20개 + 정답 전사
```

런타임 상태는 코드 옆이 아니라 **관측 대상 프로젝트** 밑에 쌓인다:
`<target-project>/.assistant/{queue,events.jsonl,state.json,glossary.json,narrations.jsonl}`
이 디렉터리는 절대 커밋하지 않는다 (`.gitignore`에 있음).

## 명령어

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

sv-glossary <project-path>        # 용어집 추출 → .assistant/glossary.json
sv-send "테스트 문장"              # Phase 0용, Telegram에 한 줄 보내기
sv-relay <project-path>           # Relay 데몬
sv-eval                           # term recall 평가 (비교군 4개)

pytest && ruff check .
```

## 시크릿

`.env`에 두고 절대 커밋하지 않는다. `.env.example`을 참고.
`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## 검증 대상 레포

`../agent-research-poc` (의료영상 AI, 실제 사용자 레포)를 용어집 추출과 이벤트 캡처의
테스트 타깃으로 쓴다. 읽기만 한다. **이 레포를 수정하지 말 것.**

## 합격 기준 (README 섹션 8)

가장 중요한 것: 실제 연구 세션 하루를 돌렸을 때
**"이건 안 보내도 됐다" 30% 이하, "이건 알았어야 했는데 못 받았다" 0건.**
나머지 기준은 README 섹션 8 참조.
