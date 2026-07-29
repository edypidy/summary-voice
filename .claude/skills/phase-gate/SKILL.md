---
name: phase-gate
description: Check the PoC phase gate before building the event capture, salience, relay, or narration pipeline. Use when asked to build Phase 2 work (hooks, transcript capture, Relay daemon, salience judging, narration generation, state.json, events.jsonl) or when asked "what should I work on next" in this project.
---

# Phase gate

이 프로젝트는 **역순 검증**으로 설계됐다 (README 섹션 4). 가장 불확실한 것이
뒤쪽(음성 UX)인데, 앞쪽(훅·파이프라인)이 만들기 재밌어서 거기부터 하면
**다 만들고 나서 안 쓰게 된다.** 이걸 막는 게 이 스킬의 존재 이유다.

## 순서

| Phase | 내용 | 상태 판별 |
|---|---|---|
| 0 | 이어폰 낭독 UX 검증 (수동) | `config.yaml`의 `narration.max_chars`가 실측값인가 |
| 1 | 용어집 + STT 교정 | `sv-glossary`, `sv-eval` 동작 |
| 2 | 이벤트 캡처 → 살리언스 → 내레이션 → Telegram | **Phase 0 통과 후에만** |
| 3 | Injector, 양방향 | 범위 외 |

## Phase 2 요청을 받았을 때 할 일

1. **Phase 0 통과 여부를 확인한다.** 다음을 순서대로 본다:
   - `docs/phase0-android.md` 하단에 합격/불합격 기록이 있는가
   - `config.yaml`의 `narration.max_chars`가 아직 `200`이고 "잠정값" 주석이 붙어 있는가
     → 붙어 있으면 **실측하지 않은 것이다**
   - `git log --oneline | grep -i phase0` 로 실측 커밋이 있는가

2. **통과 기록이 없으면 Phase 2를 시작하지 말고** 사용자에게 알린다:
   > Phase 0을 아직 통과하지 않았습니다. README 섹션 4는 여기서 멈추라고
   > 명시합니다. Phase 0이 불합격이면 전송 계층을 재설계해야 하므로 지금
   > 만드는 Relay·살리언스·내레이션이 통째로 버려집니다.
   >
   > 지금 필요한 건 코드가 아니라 30분입니다:
   > `docs/phase0-android.md`를 따라 텔레그램 봇을 만들고 `sv-send --ruler`로
   > 낭독 최대 글자 수를 실측하세요.
   >
   > 그래도 Phase 2를 먼저 진행할까요?

   사용자가 명시적으로 "그래도 진행해"라고 하면 진행한다. 막는 게 아니라
   **비용을 알려주는 것**이 목적이다.

3. **통과했으면** `config.yaml`의 실측 `max_chars`를 내레이션 제약에 반영한 뒤 진행한다.

## Phase 2를 진행할 때 지켜야 할 것

`CLAUDE.md`의 하드 제약을 먼저 읽을 것. 특히:

- 캡처는 **논블로킹**. LLM 호출·네트워크 I/O 금지. 큐에 JSON 한 줄 쓰고 끝
- 캡처의 모든 예외는 삼킨다. 관측이 연구 세션을 죽이면 안 된다
- Relay는 stateless. 강제 종료 후 재시작해도 `last_event_offset`으로 이어져야 한다
- 전체 트랜스크립트를 매 요약마다 넣지 않는다. `state.json` + 델타만
- 살리언스는 2단계: 규칙 기반 1차 필터 → LLM boolean 판정 → true일 때만 내레이션 생성.
  한 번에 하면 비용이 몇 배가 된다

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

`type=thinking` 블록은 **내레이션에 쓰지 않는다.** 잡음이고, 사용자가 들을 내용이 아니다.

스키마는 문서화되지 않았고 바뀔 수 있다. 파싱은 방어적으로 쓰고,
모르는 `type`은 조용히 건너뛴다.
