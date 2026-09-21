"""docs/results/verification.json + phash.json → docs/verification.md

    python -m api.sim.render
"""

from __future__ import annotations

import json

from api.sim.verification import ROOT

KIND = {"prank_junk": "쓰레기 사진(균열·카드 없음, 흔들림)", "prank_reused": "남의 사진을 먼 곳에 재사용",
        "wrong_building": "A 벽을 찍고 B 건물 위치로 신고", "flood": "한 기기가 한 시간에 25건",
        "prank_convincing": "그럴듯한 가짜(선명·균열 보임) — 규칙 밖"}


def main() -> None:
    v = json.loads((ROOT / "docs/results/verification.json").read_text(encoding="utf-8"))
    ph = json.loads((ROOT / "docs/results/phash.json").read_text(encoding="utf-8"))
    base = next(x for x in v if x["gps_sigma_m"] == 6.0)
    pct = lambda x: f"{x * 100:.1f}%"  # noqa: E731
    L: list[str] = []
    a = L.append
    a("# 신고 검증 — 거짓·중복 신고를 얼마나 걸러 내는가\n")
    a("`python -m ml.eval.phash_study` → `python -m api.sim.verification` → `python -m api.sim.render`로 다시 만든다.\n")
    a("> **합성 신고 흐름이다.** 실제 시민 신고 데이터가 없어서, 정답 라벨을 아는 신고 흐름(정상·후속·중복·장난·위치 틀림·도배)을")
    a("> 만들어 검증 파이프라인에 흘려 넣었다. 다만 **사진 지문(지각 해시) 거리는 가정하지 않고 실제 벽 사진으로 잰 분포**에서 뽑았다.\n")
    a("## 왜 이게 제품의 본체인가\n")
    a("시민 신고 채널은 거짓·중복 신고 한 번의 물결로 죽는다. 담당자가 헛걸음을 몇 번 하면 채널 자체를 믿지 않게 된다.")
    a("그래서 규칙은 **설명 가능해야** 하고(보류하면 사유를 말할 수 있어야), **삭제하지 않고 보류**한다(오판을 사람이 되돌릴 수 있게).\n")
    a("## 1. 결과 (GPS 오차 6m, 시드 5개 평균)\n")
    a("| 항목 | 값 | 뜻 |")
    a("| --- | ---: | --- |")
    a(f"| 나쁜 신고 자동 보류 | **{pct(base['bad_held_rate'])}** | 아래 네 종류 합계 |")
    a(f"| 중복 병합 | **{pct(base['duplicate_merged_rate'])}** | 같은 사람 재전송·같은 사진 여러 명 |")
    a(f"| 정상 신고가 억울하게 보류 | **{pct(base['legit_wrongly_held_rate'])}** | 낮을수록 좋다 |")
    a(f"| 정상 신고가 잘못 병합 | {pct(base['legit_wrongly_merged_rate'])} | |")
    a(f"| 재촬영 후속 신고가 같은 지점에 묶임 | {pct(base['followup_link_rate'])} | 나머지는 새 지점 → 관리자 '지점 합치기' |")
    a(f"| 서로 다른 벽이 한 지점으로 섞임 | {base['mixed_sites']:.0f}곳 | |\n")
    a("### 나쁜 신고 종류별 보류율\n")
    a("| 종류 | 보류율 |")
    a("| --- | ---: |")
    for k, r in base["per_kind_held"].items():
        a(f"| {KIND.get(k, k)} | {pct(r)} |")
    a("")
    a("**약한 곳을 그대로 적는다.** '엉뚱한 건물' 신고는 3분의 1만 잡는다. 다시 찍은 사진은 지문이 중앙값 16비트나 달라지는데,")
    a("500m 안의 많은 후보와 비교하는 이 검사는 오탐을 막으려고 12비트로 엄격하게 둘 수밖에 없다. 그럴듯한 가짜(선명하고 균열도 보이는")
    a("사진을 엉뚱한 곳에서)는 규칙으로 정상 신고와 구별할 수 없다 — 이건 사람 검토와 신고자 이력(반려가 쌓이면 감점)이 맡는다.\n")
    a("## 2. GPS가 나빠지면\n")
    a("| GPS 오차(σ) | 나쁜 신고 보류 | 중복 병합 | 정상 억울한 보류 | 후속 신고 묶임 |")
    a("| ---: | ---: | ---: | ---: | ---: |")
    for x in v:
        a(f"| {x['gps_sigma_m']:.0f} m | {pct(x['bad_held_rate'])} | {pct(x['duplicate_merged_rate'])} | "
          f"{pct(x['legit_wrongly_held_rate'])} | {pct(x['followup_link_rate'])} |")
    a("")
    a("GPS 오차가 25m(실내·골목)로 커지면 같은 지점을 못 찾아 중복 병합과 후속 신고 묶기가 크게 떨어지고, 위치 정확도 감점으로 정상 신고의")
    a("보류가 늘어난다. 지자체 운영에서는 건물 대장(주소·동 번호)과 연결하는 게 GPS보다 확실하다 — README의 '필요한 것' 참고.\n")
    a("## 3. 사진 지문(지각 해시) 임계값을 잰 방법\n")
    a("실제 벽 사진(CrackSeg9k val·test의 건물 외벽·벽돌·민무늬 콘크리트, 종류별 60장)에 재촬영을 흉내 낸 변화 — 조명(표준 색순응 모델),")
    a("노출, 구도(이동 ±6%, 회전 ±6°, 확대 ±10%), 흐림, JPEG 재압축 — 를 주고 64비트 지각 해시의 해밍 거리를 쟀다.\n")
    a("| 벽 종류 | 같은 장면 재촬영 (중앙값 / 90%) | 같은 사진 재저장 (90%) | 서로 다른 벽 (하위 1% / 중앙값) |")
    a("| --- | ---: | ---: | ---: |")
    for g, s in ph.items():
        if g.startswith("_"):
            continue
        a(f"| {g} | {s['same_p50']:.0f} / {s['same_p90']:.0f} | {s['photo_p90']:.0f} | {s['diff_p1']:.0f} / {s['diff_p50']:.0f} |")
    a("")
    a("| 임계값 | 재촬영 묶임 | 서로 다른 벽 충돌(민무늬 콘크리트) | 쓰는 곳 |")
    a("| ---: | ---: | ---: | --- |")
    nc = ph["민무늬 콘크리트(균열 없음)"]["by_threshold"]
    for t, use in (("8", "중복(같은 사진) 판정"), ("12", "다른 위치의 같은 장면(엉뚱한 건물)"), ("18", "같은 지점 묶기(15m 안 후보끼리만)")):
        a(f"| ≤ {t} | {pct(nc[t]['link_recall'])} | {pct(nc[t]['collision'])} | {use} |")
    a("")
    a("처음엔 '같은 장면 ≤ 14'로 가정했는데, 이 측정에서 재촬영의 절반도 못 묶는다는 게 드러나 용도별로 임계값을 나눴다(docs/decisions.md).\n")
    a("## 4. 규칙 목록\n")
    a("`api/app/verify/rules.py`에 임계값, `api/app/verify/pipeline.py`에 규칙이 있다. 각 규칙은 점수에 준 영향과 사유를 남긴다.\n")
    a("| 사유 코드 | 감점 | 언제 |")
    a("| --- | ---: | --- |")
    for code, d, when in [
        ("DUPLICATE_SAME_DEVICE / _PHOTO", "병합", "같은 기기가 24시간 안에 같은 장면, 또는 누구든 2시간 안에 거의 같은 사진"),
        ("PHOTO_REUSED_ELSEWHERE", "−0.6", "거의 같은 사진이 200m 넘게 떨어진 곳으로 이미 접수됨"),
        ("SCENE_ELSEWHERE", "−0.6", "같은 장면이 15~500m 떨어진 다른 위치로 이미 접수됨"),
        ("FLOODING (+소급)", "−0.6", "한 기기가 한 시간에 6건 이상 — 직전 한 시간 신고도 보류"),
        ("NO_DETECTION", "−0.5", "검출된 균열 없음(검출기가 놓쳤을 수 있어 사람 확인)"),
        ("DEVICE_HISTORY", "−0.3", "이 기기의 검토된 신고 3건 이상 중 절반 이상 반려"),
        ("FUTURE_TIMESTAMP / IMPLAUSIBLE_WIDTH", "−0.3", "촬영 시각이 미래 / 폭 50mm 초과"),
        ("IMAGE_BLURRY / STALE_PHOTO", "−0.2", "흔들림 심함 / 30일 넘은 사진"),
        ("CALIBRATION_MISSING / GPS_IMPRECISE", "−0.15", "기준 카드 없음 / 위치 정확도 50m 초과"),
        ("CORROBORATED", "+0.1", "같은 지점에 다른 시민의 확인된 신고"),
    ]:
        a(f"| `{code}` | {d} | {when} |")
    a("\n점수 0.5 미만은 자동 보류. 보류는 삭제가 아니라 관리자 대기열이고, 모든 조치(확인·반려·되돌리기·지점 합치기)는 사유와 함께 기록된다.\n")
    a("## 한계\n")
    a("- 신고 흐름은 합성이다. 실제 시민의 행동(얼마나 자주 다시 찍는지, 장난의 형태)은 운영해 봐야 안다.")
    a("- 재촬영은 한 장의 사진을 변형해 흉내 냈다. 실제로 다른 날 다른 각도에서 찍은 쌍으로 다시 재야 한다.")
    a("- 사진 재사용 검사는 전체 신고를 훑는다. 수만 건 규모에선 BK-트리나 PostgreSQL 비트 연산 색인이 필요하다.")
    (ROOT / "docs" / "verification.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote docs/verification.md")


if __name__ == "__main__":
    main()
