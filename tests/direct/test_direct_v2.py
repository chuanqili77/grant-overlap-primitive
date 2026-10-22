"""V2 role separation with SDK storage and mocked model responses."""
import json
from pathlib import Path

import pytest

CONTRACT = str(Path(__file__).parents[2] / 'contracts/grant_overlap_v2.py')


@pytest.fixture
def ledger_v2(direct_vm, direct_deploy, direct_alice, direct_bob):
    direct_vm.check_pickling = True
    return direct_deploy(CONTRACT, 'Community lab', 'USD',
                         ('0x' + direct_alice.hex()), ('0x' + direct_bob.hex()), sdk_version='v0.2.16')


def approve_both(ledger, vm, alice, bob, proposal_id):
    for funder in [alice, bob]:
        with vm.prank(funder):
            ledger.approve_cost(proposal_id)


def activate_first(ledger, vm, alice, bob):
    ledger.propose_cost('Microscope', 'Invoice LAB-104 supplier One', 120000)
    approve_both(ledger, vm, alice, bob, 1)
    ledger.activate_cost(1)


def test_quorum_and_storage(ledger_v2, direct_vm, direct_alice, direct_bob):
    ledger = ledger_v2
    ledger.propose_cost('Microscope', 'Invoice LAB-104 supplier One', 120000)
    before = ledger.snapshot()
    with pytest.raises(Exception, match='registered funder'):
        ledger.approve_cost(1)
    assert ledger.snapshot() == before
    with direct_vm.prank(direct_alice):
        ledger.approve_cost(1)
        before = ledger.snapshot()
        with pytest.raises(Exception, match='already approved'):
            ledger.approve_cost(1)
        assert ledger.snapshot() == before
    with pytest.raises(Exception, match='Both funders'):
        ledger.activate_cost(1)
    assert ledger.snapshot() == before
    with direct_vm.prank(direct_bob):
        ledger.approve_cost(1)
    ledger.activate_cost(1)
    data = json.loads(ledger.snapshot())
    assert data['schema'] == 2
    assert data['proposals'][0]['status'] == 'ACTIVE'
    assert data['costs'][0]['proposal_id'] == 1
    assert set(data['funders']) == {('0x' + direct_alice.hex()).lower(), ('0x' + direct_bob.hex()).lower()}


def test_reservation_ownership_and_rollback(ledger_v2, direct_vm, direct_alice, direct_bob):
    ledger = ledger_v2
    activate_first(ledger, direct_vm, direct_alice, direct_bob)
    with direct_vm.prank(direct_alice):
        ledger.reserve(1, 70000, 'A-001')
    before = ledger.snapshot()
    for sender in [direct_vm.sender, direct_bob]:
        with direct_vm.prank(sender):
            with pytest.raises(Exception, match='registered funder|reservation funder'):
                ledger.release(1)
    assert ledger.snapshot() == before
    with direct_vm.prank(direct_bob):
        with pytest.raises(Exception, match='capacity exceeded'):
            ledger.reserve(1, 50001, 'B-001')
        assert ledger.snapshot() == before
        ledger.reserve(1, 50000, 'B-001')
    with direct_vm.prank(direct_alice):
        ledger.release(1)
    data = json.loads(ledger.snapshot())
    assert data['reservations'][0]['funder'] == ('0x' + direct_alice.hex()).lower()
    assert data['reservations'][0]['active'] is False
    assert data['reservations'][1]['active'] is True


@pytest.mark.parametrize('response', [
    '[{"index":0,"relation":"SAME"}]',
    '[{"index":0,"relation":"UNCERTAIN"}]',
    '{}', '[]', '[{"index":1,"relation":"DISTINCT"}]',
])
def test_pending_duplicate_cannot_bypass_latest_state(
        ledger_v2, direct_vm, direct_alice, direct_bob, response):
    ledger = ledger_v2
    for title in ['Microscope', 'Renamed microscope']:
        ledger.propose_cost(title, 'Invoice LAB-104 supplier One', 120000)
    for proposal_id in [1, 2]:
        approve_both(ledger, direct_vm, direct_alice, direct_bob, proposal_id)
    ledger.activate_cost(1)
    direct_vm.mock_llm(r'Classify whether[\s\S]*', response)
    before = ledger.snapshot()
    with pytest.raises(Exception):
        ledger.activate_cost(2)
    assert ledger.snapshot() == before


def test_distinct_cost_and_independent_validator(
        ledger_v2, direct_vm, direct_alice, direct_bob):
    ledger = ledger_v2
    activate_first(ledger, direct_vm, direct_alice, direct_bob)
    ledger.propose_cost('Hall hire', 'Invoice H-22 November 12', 40000)
    approve_both(ledger, direct_vm, direct_alice, direct_bob, 2)
    direct_vm.mock_llm(r'Classify whether[\s\S]*', '[{"index":0,"relation":"DISTINCT"}]')
    ledger.activate_cost(2)
    assert len(json.loads(ledger.snapshot())['costs']) == 2
    assert direct_vm.run_validator() is True
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r'Classify whether[\s\S]*', '[{"index":0,"relation":"SAME"}]')
    assert direct_vm.run_validator() is False
    assert direct_vm.run_validator(leader_result='[]') is False


def test_outsider_cannot_propose(ledger_v2, direct_vm, direct_charlie):
    before = ledger_v2.snapshot()
    with direct_vm.prank(direct_charlie):
        with pytest.raises(Exception, match='project participants'):
            ledger_v2.propose_cost('Other expense', 'Invoice OTHER-1', 100)
    assert ledger_v2.snapshot() == before
