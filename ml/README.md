# ml — 학습·평가 스크립트

노트북이 아니라 재현 가능한 스크립트로 둔다. 같은 명령이 같은 숫자를 내야 한다.

```
datasets/  원 배포처에서 내려받고 전처리한다. 이미지 자체는 저장소에 없다.
train/     학습
eval/      IoU·정밀도·재현율, 고전 CV 기준선과의 비교
export/    ONNX 변환·양자화·수치 검증
```

## 데이터 원칙

- 학습에 쓰는 것: CrackSeg9k(CC0 1.0), SDNET2018(CC BY 4.0), Özgenel(CC BY 4.0)
- 쓰지 않는 것: 비상업 한정(DeepCrack·CFD) 및 라이선스 불명(khanhha 통합본, CRACK500 직접 수급)
- 내려받은 데이터는 `data/`(gitignore)에 두고 저장소에 올리지 않는다.
- 근거와 라이선스 표는 [`../docs/00-approach.md`](../docs/00-approach.md) 3절.

## 전처리

`../shared/pipeline.json`을 읽는다. 여기 값을 코드에 다시 적지 않는다.
웹(TS) 구현과 결과가 어긋나면 조용히 성능이 떨어지므로, `../shared/fixtures/`의
골든 테스트로 양쪽을 맞춘다.
