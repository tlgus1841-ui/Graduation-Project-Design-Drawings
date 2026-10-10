import pytest

from harness.verification.fsm_acceptance import (
    COOLDOWN_SEC,
    SCENARIOS,
    NaiveFSM,
    Sample,
    SpecFSM,
    evaluate,
    run_all,
)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_spec_fsm_passes_every_scenario(name):
    assert run_all(SpecFSM)[name]["pass"], run_all(SpecFSM)[name]["log"]


def test_spec_fsm_restores_only_after_full_cooldown():
    r = evaluate(SpecFSM, SCENARIOS["steady"])
    assert r.log[-1].endswith("RESTORE")
    # last attack sample at 38s, first clean sample at 40s -> RESTORE once 10 s of clean samples elapse
    assert r.recovery_sec == pytest.approx(COOLDOWN_SEC + 2.0)


def test_reattack_during_cooldown_keeps_the_block():
    r = evaluate(SpecFSM, SCENARIOS["reattack_in_cooldown"])
    assert [line.split()[-1] for line in r.log] == ["REROUTE", "ISOLATE", "RESTORE"]


def test_harness_catches_flapping_in_a_timeout_style_fsm():
    report = run_all(NaiveFSM)
    assert report["pulsing_4s"]["flaps"] > 0
    assert not report["pulsing_4s"]["pass"]
    assert not report["reattack_in_cooldown"]["pass"]


def test_calibration_window_ignores_early_attack():
    fsm = SpecFSM()
    cmds = [c for t in range(0, 14, 2) for c in fsm.step(Sample(t=t, pps=3000, bpp=64, score=-0.9))]
    assert cmds == [] and fsm.state == "CALIBRATING"
