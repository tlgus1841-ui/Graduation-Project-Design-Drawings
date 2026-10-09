"""attack_profiles.py 단위 검증 (week15 계획서)."""

import pytest

from traffic.attack_profiles import PRESETS, get_preset


@pytest.mark.parametrize("name", list(PRESETS))
def test_get_preset_returns_valid_pps_range(name):
    preset = get_preset(name)
    assert preset.name == name
    assert 0 < preset.min_pps <= preset.max_pps


def test_get_preset_unknown_name_raises():
    with pytest.raises(ValueError):
        get_preset("does-not-exist")


def test_presets_cover_attack_pps_spec_range():
    """schedule_and_milestones.md ATTACK_PPS(1,000~5,000) 범위를 벗어나지 않아야 한다."""
    for preset in PRESETS.values():
        assert 1000 <= preset.min_pps
        assert preset.max_pps <= 5000
