# 평가 데이터 (README 섹션 7.3)

리더보드나 벤더 벤치마크를 믿지 말고 직접 잰다.

## utterances.jsonl

사용자가 실제로 할 법한 발화 20개. 한국어 문장 안에 영어 전문용어가 섞인 형태다.
`../agent-research-poc`에서 뽑은 실제 용어(DDPM, DDIM, UNet, FID, EMA, WGAN...)와
README 섹션 1의 용어(LoRA-XS, Sinkhorn, cross-attention, STE, PEFT)를 섞었다.

**이건 출발점일 뿐이다.** 실제로 쓰는 말투와 다르면 고쳐 쓸 것. 평가의 목적은
사용자 본인의 발화에서 용어가 얼마나 잡히는지 재는 것이지, 남의 문장으로
점수를 내는 게 아니다.

## 녹음

각 발화를 직접 읽어 녹음하고 `recordings/<id>.wav` 로 저장한다.
평소 말하듯이 읽는다. 또박또박 읽으면 실사용과 다른 결과가 나온다.

녹음 파일은 커밋하지 않는다 (`.gitignore`).

## 채점

전사 결과를 각 비교군별로 채워 넣는다:

```json
{"id": "u01", "reference": "...", "baseline": "...", "layer1": "..."}
```

- `reference` — 정답. 사람이 확인한 전사문
- `baseline` — (a) 바이어싱 없는 원시 전사
- `layer1` — (b) 디코딩 시점 바이어싱을 켠 전사

(c) 레이어1+2와 (d) 레이어2만은 `sv-eval`이 (b)와 (a)에 LLM 교정을 돌려 직접 만든다.

```bash
sv-eval --glossary ../agent-research-poc/.assistant/glossary.json
```

**(d)가 (c)와 비슷하면 레이어 1은 버린다.** 복잡도와 벤더 의존성을 줄일 기회다
(`../docs/research-stt.md` 참조 - 한국어 바이어싱의 근거가 얇다).
