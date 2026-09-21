from ml.pipeline_config import load


def test_shared_config_is_readable_and_has_contract_keys():
    cfg = load()
    assert cfg["version"] == 1
    assert cfg["input"]["tile"] > 0
    assert len(cfg["normalize"]["mean"]) == 3
    # 기준 패치 정의는 웹 구현과 공유되는 계약이다.
    assert len(cfg["calibration"]["patch"]["swatches"]) == 6
