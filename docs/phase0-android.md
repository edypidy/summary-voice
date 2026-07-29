# Phase 0 — Android 낭독 UX 검증

README 섹션 4의 **게이트**. 이걸 통과 못 하면 Phase 2를 만들지 않는다.
사용자 폰은 Android로 확정됐다 (README Q1). README가 상정한 iOS Announce
Notifications 경로는 쓸 수 없으므로 아래 경로로 대체한다.

목표 두 가지:
1. 하루 써보고 "이거 계속 쓰겠다"는 판단이 서는가
2. **낭독이 잘리지 않는 최대 글자 수를 실측**한다 (`config.yaml`의 `narration.max_chars` 갱신)

---

## 1. 텔레그램 봇 만들기 (5분)

1. 텔레그램에서 **@BotFather** 를 찾아 `/newbot`
2. 봇 이름과 username을 정하면 토큰이 나온다
3. 레포 루트에 `.env` 생성:
   ```
   TELEGRAM_BOT_TOKEN=<받은 토큰>
   ```
4. 만든 봇과의 대화를 열고 **아무 메시지나 한 번 보낸다** (이걸 해야 봇이 채팅을 알게 된다)
5. ```bash
   sv-send --whoami
   ```
   나온 ID를 `.env`에 `TELEGRAM_CHAT_ID=...` 로 추가
6. 확인:
   ```bash
   sv-send "테스트입니다"
   ```

## 2. 낭독 켜기

경로가 두 갈래다. **A를 먼저 시도하고, Telegram이 목록에 없거나 동작하지 않으면 B로 간다.**

### A. Gemini "Announce notifications" (기본 경로, 앱 설치 불필요)

Gemini 지원 헤드폰/이어버드를 연결한 상태에서:

- Gemini 앱 → 설정 → 헤드폰 관련 항목 → **Announce notifications** 켜기
- **알림을 들을 앱을 고르는 단계에서 Telegram을 선택**한다
- Gemini에 알림 접근 권한을 준다

> **미검증**: Google 공식 문서는 예시로 Messages, WhatsApp만 든다. 앱을 고를 수
> 있다고는 쓰여 있지만 **Telegram이 목록에 나오는지는 확인하지 못했다.** 메신저가
> 아닌 앱은 제외된다는 보고도 있어, 실제로 켜 보고 안 되면 바로 B로 넘어갈 것.
>
> 또 하나: Google Assistant → Gemini 전환 과정에서 알림 낭독·음성 답장 동작이
> 바뀌고 있다. 위 메뉴 이름이 폰에서 다를 수 있다.

### B. 전용 알림 낭독 앱 (대안 경로)

읽을 앱을 직접 고르는 구조라 Telegram 지원이 확실하다. Play 스토어에서:

- **Notif: Notifications Aloud** — 온디바이스 처리, 계정 불필요
- **Notification Reader TTS Voice** — 선택한 앱만 읽음
- **Speaki - Voice Notifications** — 앱 선택 + 발신자 읽기

셋 다 알림 접근 권한이 필요하다. 하나 골라 Telegram만 켜고 나머지는 끈다.

### 공통 설정

- Telegram 앱 알림에서 해당 봇 채팅의 알림이 켜져 있고 **무음이 아닌지** 확인
- 한국어 TTS 엔진이 설치돼 있는지 확인 (설정 → 접근성 → 텍스트 음성 변환)
- 이어폰을 블루투스로 연결한 상태에서 테스트할 것. 스피커로는 의미가 없다

## 3. 최대 글자 수 실측

이게 Phase 0의 계측 항목이다. 추측하지 말고 잰다.

```bash
sv-send --ruler
```

80·120·160·200·240·280·340·400·500자 메시지를 20초 간격으로 보낸다.
각 메시지는 **"여기까지 N자입니다"로 끝난다.**

이어폰을 끼고 들으면서, **그 끝맺음이 들린 마지막 N**을 적는다.
그 값이 실측값이다. 앞부분만 들리고 끝맺음이 안 들렸다면 그 길이는 잘린 것이다.

간격이 짧아 낭독이 겹치면 `--delay 30` 처럼 늘린다.

측정 후:
```yaml
# config.yaml
narration:
  max_chars: <실측값>
```
`README.md` 섹션 6.3의 "미실측 시 잠정 200자" 문구도 같이 고친다.

## 4. 하루 사용

실제 연구 세션 중에 손으로 몇 개 보내 본다:

```bash
sv-send "2번 에이전트가 Sinkhorn OT 루프 구현을 끝냈습니다."
sv-send "학습이 loss NaN으로 멈췄습니다. 확인이 필요합니다."
```

체크할 것:
- 이어폰만 끼고 있을 때 **터미널로 돌아가지 않고** 상황이 파악되는가
- 한국어 문장 안의 영어 용어(`Sinkhorn`, `loss`)를 TTS가 알아듣게 읽는가
  - 뭉갠다면 내레이션에서 그 용어를 한글로 풀어 써야 한다. 용어집의 `spoken` 필드가 그 용도다
- 알림이 너무 잦아 성가신가 (→ `relay.debounce_seconds` 조정 근거)

## 합격 / 불합격

**합격**: 하루 뒤 "계속 쓰겠다"는 판단 + 최대 글자 수 실측 완료 → Phase 2 착수

**불합격**: 전송 계층을 재설계해야 한다. **Phase 2를 만들지 말 것.**
불합격 사유를 여기에 적어두고 대안(예: 자체 알림 앱, 워치, 다른 메신저)을 먼저 검토한다.

---

## 확인 못 한 것

정직하게 남긴다. 실제로 해 보면서 채울 것.

- Telegram이 Gemini의 Announce notifications 앱 목록에 나오는가
- Android 알림 낭독에 길이 제한이 있는가 (있다면 `--ruler`가 잡아낸다)
- Android에서 알림에 **음성으로 답장**이 되는가 (Phase 3 양방향의 전제)
- Google 한국어 TTS가 한영 코드스위칭 문장을 어떻게 읽는가

## 출처

- [Use Gemini on your headphones - Google 지원](https://support.google.com/gemini/answer/15456140?hl=en)
- [Google Assistant headphones now require 'Read my notifications' - 9to5Google, 2025-02-20](https://9to5google.com/2025/02/20/google-assistant-headphones-notifications/)
- [Notif: Notifications Aloud - Google Play](https://play.google.com/store/apps/details?id=com.app.android.notif)
- [Notification Reader TTS Voice - Google Play](https://play.google.com/store/apps/details?id=com.simple.notitts)
- [Speaki - Voice Notifications - Google Play](https://play.google.com/store/apps/details?id=com.one.speakify)
