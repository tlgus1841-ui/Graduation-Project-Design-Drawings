"""
Unit tests for Autonomous Self-Healing Flapping FSM (Week 11).
Author: Sihyeon Park (22101489 / Tech Lead)
"""

from harness.safety.flapping_fsm import DefenseState, FlappingFSM


def test_fsm_initial_state_is_normal():
    fsm = FlappingFSM()
    assert fsm.get_state() == DefenseState.NORMAL


def test_fsm_anomaly_triggers_mitigated_state():
    transitions = []

    def log_change(prev, next_, meta):
        transitions.append((prev, next_, meta))

    fsm = FlappingFSM(cooldown_sec=10.0, on_state_change=log_change)
    fsm.trigger_anomaly(dpid=1, in_port=2, threat_info={"score": -0.85})

    assert fsm.get_state() == DefenseState.MITIGATED
    assert len(transitions) == 1
    assert transitions[0][0] == DefenseState.NORMAL
    assert transitions[0][1] == DefenseState.MITIGATED


def test_fsm_heartbeat_advances_to_cooldown_and_normal():
    transitions = []

    def log_change(prev, next_, meta):
        transitions.append((prev, next_, meta))

    fsm = FlappingFSM(cooldown_sec=10.0, on_state_change=log_change)
    t0 = 1000.0
    fsm.last_threat_time = t0
    fsm.state = DefenseState.MITIGATED

    # 1. 5 seconds later (half of cooldown) -> COOLDOWN
    fsm.evaluate_heartbeat(current_time=t0 + 5.1)
    assert fsm.get_state() == DefenseState.COOLDOWN
    assert len(transitions) == 1

    # 2. 10.1 seconds later -> NORMAL (Rollback)
    fsm.evaluate_heartbeat(current_time=t0 + 10.1)
    assert fsm.get_state() == DefenseState.NORMAL
    assert len(transitions) == 2
    assert transitions[1][1] == DefenseState.NORMAL


def test_fsm_new_threat_during_cooldown_re_triggers_mitigated():
    fsm = FlappingFSM(cooldown_sec=10.0)
    fsm.state = DefenseState.COOLDOWN

    # Threat arrives again before full recovery
    fsm.trigger_anomaly(dpid=1, in_port=2)
    assert fsm.get_state() == DefenseState.MITIGATED


def test_fsm_force_restore():
    fsm = FlappingFSM()
    fsm.trigger_anomaly(dpid=1, in_port=2)
    assert fsm.get_state() == DefenseState.MITIGATED

    fsm.force_restore()
    assert fsm.get_state() == DefenseState.NORMAL
