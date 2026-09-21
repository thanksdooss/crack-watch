# 골든 테스트 고정 데이터

여기 있는 파일은 구현이 바뀌어도 결과가 같아야 하는 기준값이다.

| 파일 | 내용 | 출처 |
| --- | --- | --- |
| `ciede2000_testdata.txt` | CIEDE2000 색차 공식 검증용 34쌍(L\*a\*b\* 두 쌍과 기대 ΔE00) | Sharma, Wu, Dalal (2005), *Color Research & Application* 30(1) — [저자 배포본](https://www.ece.rochester.edu/~gsharma/ciede2000/) |

`ciede2000_testdata.txt`는 색차 공식 구현을 검증하는 용도다. 이 34쌍은 공식의
불연속 구간(색상각 경계 등)을 일부러 노린 값들이라, 여기를 통과하면 구현 실수를
대부분 걸러낼 수 있다.
