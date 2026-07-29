from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MT5 = PROJECT_ROOT / "indicators" / "mt5" / "SBWeeklyTemplate.mq5"
CTRADER = PROJECT_ROOT / "indicators" / "ctrader" / "SBWeeklyTemplate.cs"
MT5_INSTALLER = PROJECT_ROOT / "scripts" / "install_mt5_indicator.ps1"


def test_native_weekly_templates_cover_current_overlay_rules() -> None:
    mt5 = MT5.read_text(encoding="utf-8")
    ctrader = CTRADER.read_text(encoding="utf-8")
    required_markers = [
        "PMH",
        "PML",
        "PWH",
        "PWL",
        "Fri Close",
        "Mon High",
        "Mon Low",
        "Inside Day",
        "FGD",
        "FRD",
        "3DL",
        "3DS",
        "2CIB",
        "CIB_",
        "PDH_LINK_",
        "PDL_LINK_",
    ]

    for marker in required_markers:
        assert marker in mt5
        assert marker in ctrader


def test_native_weekly_templates_keep_current_session_defaults() -> None:
    mt5 = MT5.read_text(encoding="utf-8")
    ctrader = CTRADER.read_text(encoding="utf-8")

    assert "InpAsiaStartHourUtc = 3" in mt5
    assert "InpAsiaEndHourUtc = 6" in mt5
    assert "InpLondonStartHourUtc = 9" in mt5
    assert "InpLondonEndHourUtc = 12" in mt5
    assert "InpNewYorkStartHourUtc = 15" in mt5
    assert "InpNewYorkEndHourUtc = 18" in mt5
    assert "DefaultValue = 3" in ctrader
    assert "DefaultValue = 6" in ctrader
    assert "DefaultValue = 9" in ctrader
    assert "DefaultValue = 12" in ctrader
    assert "DefaultValue = 15" in ctrader
    assert "DefaultValue = 18" in ctrader


def test_native_weekly_templates_exclude_other_templates() -> None:
    for path in (MT5, CTRADER):
        content = path.read_text(encoding="utf-8").lower()
        assert "exponential moving average" not in content
        assert "major round number" not in content


def test_mt5_indicator_source_is_complete_and_uses_mql5_conversions() -> None:
    content = MT5.read_text(encoding="utf-8")

    assert len(content.splitlines()) > 800
    assert content.rstrip().endswith("}")
    assert "int OnCalculate(" in content
    assert "IntegerToString(ChartID())" in content
    assert "LongToString" not in content
    assert "ColorToARGB" not in content


def test_native_cib_markers_start_at_first_current_day_candle() -> None:
    mt5 = MT5.read_text(encoding="utf-8")
    ctrader = CTRADER.read_text(encoding="utf-8")

    assert "day_range.first_time" in mt5
    assert "InpCibWidthPixels = 12" in mt5
    assert "InpCibMaximumHeightPixels = 24" in mt5
    assert "OBJ_RECTANGLE_LABEL" in mt5
    assert "dayRange.FirstTime" in ctrader
    assert "CibMinimumWidthMinutes" in ctrader


def test_mt5_context_labels_are_aligned_near_the_visible_right_edge() -> None:
    content = MT5.read_text(encoding="utf-8")

    assert "InpLevelLabelRightMarginPixels = 58" in content
    assert "RightEdgeLabelTime(chart_end, price)" in content
    assert "ChartXYToTimePrice(" in content


def test_mt5_installer_verifies_the_copied_source() -> None:
    content = MT5_INSTALLER.read_text(encoding="utf-8")

    assert "Get-FileHash" in content
    assert "$sourceLines -lt 800" in content
    assert "$sourceHash -ne $destinationHash" in content
