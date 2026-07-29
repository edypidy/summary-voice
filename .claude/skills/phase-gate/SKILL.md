---
name: phase-gate
description: Check the PoC phase gate and the transcript capture schema before building relay, salience, summary, or bidirectional/injector work in summary-voice. Use when asked to build the capture pipeline, the Relay daemon, salience judging, summary generation, or a way to send instructions back to an agent - and when asked "what should I work on next" in this project.
---

# Phase gate

이 프로젝트는 **역순 검증**으로 설계됐다 (README 섹션 4). 가장 불확실한 것이
뒤쪽(사람이 실제로 쓰는가)인데, 앞쪽(파이프라인)이 만들기 재밌어서 거기부터 하면
**다 만들고 나서 안 쓰게 된다.** 이걸 막는 게 이 스킬의 존재 이유다.

**이 원칙은 이미 한 번 값을 했다.** Phase 0이 음성 UX를 탈락시켰고
(`docs/phase0-result.md`), 그때 버려진 건 아직 안 만든 파이프라인이었다.
순서를 뒤집었으면 내레이션 생성기·용어집·STT 교정을 다 만든 뒤에 버렸을 것이다.

## 순서

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 전송 UX 검증 (수동) | ✅ 완료. 텍스트 합격 / **음성 불합격** |
| 1 | 이벤트 캡처 → 살리언스 → 요약 → Telegram | **현재 단계** |
| 2 | 양방향 (지시 전달, Injector) | Phase 1 합격 후에만 |
| - | 음성 (TTS/STT/용어집) | 범위 외. Phase 0에서 탈락 |

## 양방향(Phase 2) 요청을 받았을 때

"텔레그램에서 답장해서 에이전트에게 지시를 보내고 싶다"는 요청이 오면:

1. **Phase 1 합격 여부를 확인한다:**
   - `docs/` 에 Phase 1 결과 기록이 있는가
   - `<target-project>/.assistant/narrations.jsonl` 에 실사용 이력이 쌓였는가
   - README 섹션 8의 5번 기준("안 보내도 됐다" 30% 이하)을 실제로 재봤는가

2. **기록이 없으면 시작하지 말고** 사용자에게 알린다:
   > Phase 1을 아직 하루 써보지 않았습니다. **받는 요약이 시시하면 답장할 일도
   > 없습니다.** 그리고 하루 써보면 "여기서 답장하고 싶다"는 지점이 어디인지
   > 알게 되는데, 그 지점을 모르고 주입 경로부터 만들면 안 쓰는 기능이 됩니다.
   >
   > 그래도 먼저 진행할까요?

   사용자가 명시적으로 "그래도 진행해"라고 하면 진행한다. 막는 게 아니라
   **비용을 알려주는 것**이 목적이다.

## 음성 요청을 받았을 때

TTS·STT·용어집·term recall 관련 요청이 오면 **먼저 `docs/phase0-result.md`를
읽고 그 판정을 사용자에게 알린다.** 코드는 커밋 `5c58d8d`에 그대로 있으므로
되살리는 건 쉽다. 어려운 건 그 판정을 뒤집는 것이다 - 문제는 코드 품질이 아니라
**듣기가 읽기보다 나을 게 없었다**는 것이었다.

## Phase 1을 진행할 때 지켜야 할 것

`CLAUDE.md`의 하드 제약을 먼저 읽을 것. 특히:

- 캡처는 **논블로킹**. LLM 호출·네트워크 I/O 금지. 큐에 JSON 한 줄 쓰고 끝
- 캡처의 모든 예외는 삼킨다. 관측이 연구 세션을 죽이면 안 된다
- Relay는 stateless. 강제 종료 후 재시작해도 `last_event_offset`으로 이어져야 한다
- 전체 트랜스크립트를 매 요약마다 넣지 않는다. `state.json` + 델타만
- 살리언스는 2단계: 규칙 기반 1차 필터 → LLM boolean 판정 → true일 때만 요약 생성

**요약 문체는 낭독이 아니라 읽기 기준이다** (README 섹션 6.3, 개정됨).
식별자·경로·줄 번호·숫자를 **넣는다**. 예전 규칙("코드·경로 금지", "3문장 이하",
"숫자 최소화")은 폐기됐으니 그걸 따르지 말 것.

## 캡처 소스 (실측 완료)

사용자는 Agent SDK / 헤드리스로 쓴다 (README Q2). 훅 대신 트랜스크립트를 읽는다.
`~/.claude/projects/<slugified-cwd>/<session-id>.jsonl`의 실제 구조:

| 신호 | 어디서 |
|---|---|
| 턴 종료 (= 마일스톤, 주 트리거) | `type=assistant` 이고 `message.stop_reason == "end_turn"` |
| 턴 진행 중 | `message.stop_reason == "tool_use"` |
| 서브에이전트 작업 | 최상위 `isSidechain == true` |
| 어떤 툴을 썼나 | `message.content[]` 중 `type=tool_use` → `.name`, `.input` |
| 툴 결과 / 실패 | `type=user` 레코드의 `toolUseResult` → `stdout`, `stderr`, `interrupted` |
| 세션·경로 | 최상위 `sessionId`, `cwd`, `gitBranch` |
| 에이전트가 한 말 | `message.content[]` 중 `type=text` |

`type=thinking` 블록은 **요약에 쓰지 않는다.** 잡음이고, 사용자가 볼 내용이 아니다.

스키마는 문서화되지 않았고 바뀔 수 있다. 파싱은 방어적으로 쓰고,
모르는 `type`은 조용히 건너뛴다.

## 텔레그램에서 이미 겪은 함정

- `parse_mode`를 **아예 넣지 않는다.** `None`으로 두면 JSON에 `null`이 실려 나가고
  텔레그램이 `400 unsupported parse_mode`로 거절한다
- 봇 토큰이 URL 경로에 있다. `logging.getLogger("httpx").setLevel(WARNING)` 안 하면
  매 호출마다 시크릿이 로그에 남는다
- `getUpdates`는 최근 24시간의 **아직 소비되지 않은** 업데이트만 돌려준다.
  `--whoami`가 비어 있다고 셋업이 틀린 게 아니다
