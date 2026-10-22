"""Official GenLayer Direct Mode with real SDK storage and mocked LLM I/O."""
import json
from pathlib import Path
import pytest

CONTRACT = str(Path(__file__).parents[2] / 'contracts/grant_overlap.py')

@pytest.fixture
def ledger(direct_vm, direct_deploy):
    direct_vm.check_pickling = True
    contract = direct_deploy(CONTRACT, 'Community lab', 'USD', sdk_version='v0.2.16')
    contract.register_cost('Microscope', 'Invoice LAB-104 supplier One, one microscope', 120000)
    return contract


def test_storage_and_reservation(ledger):
    ledger.reserve(1, 'Science fund', 70000, 'SCI-001')
    ledger.reserve(1, 'Local sponsor', 50000, 'LOCAL-001')
    data = json.loads(ledger.snapshot())
    assert len(data['costs']) == 1
    assert sum(x['amount'] for x in data['reservations']) == 120000


def test_over_cap_rollback(ledger):
    ledger.reserve(1, 'A', 120000, 'A-001')
    before = ledger.snapshot()
    with pytest.raises(Exception, match='capacity exceeded'):
        ledger.reserve(1, 'B', 1, 'B-001')
    assert ledger.snapshot() == before


def test_release_retains_history(ledger):
    ledger.reserve(1, 'A', 120000, 'A-001')
    ledger.release(1)
    ledger.reserve(1, 'B', 120000, 'B-001')
    data = json.loads(ledger.snapshot())
    assert len(data['reservations']) == 2
    assert data['reservations'][0]['active'] is False


def test_wrong_wallet_rejected(ledger, direct_vm, direct_bob):
    before = ledger.snapshot()
    with direct_vm.prank(direct_bob):
        with pytest.raises(Exception, match='registrar'):
            ledger.reserve(1, 'A', 1, 'A-001')
    assert ledger.snapshot() == before


@pytest.mark.parametrize('relation', ['SAME', 'UNCERTAIN'])
def test_duplicate_and_partial_overlap_fail_closed(ledger, direct_vm, relation):
    direct_vm.mock_llm(r'Classify whether[\s\S]*', json.dumps([{'index':0, 'relation':relation}]))
    before = ledger.snapshot()
    with pytest.raises(Exception, match='Overlapping or uncertain'):
        ledger.register_cost('Renamed microscope', 'Same LAB-104 or an unspecified partial item', 120000)
    assert ledger.snapshot() == before


def test_distinct_cost_and_validator(ledger, direct_vm):
    direct_vm.mock_llm(r'Classify whether[\s\S]*', '[{"index":0,"relation":"DISTINCT"}]')
    ledger.register_cost('Hall hire', 'Invoice H-22 hall hire, November 12', 40000)
    assert len(json.loads(ledger.snapshot())['costs']) == 2


def test_independent_validator_acceptance_and_disagreement(ledger, direct_vm):
    direct_vm.mock_llm(r'Classify whether[\s\S]*', '[{"index":0,"relation":"DISTINCT"}]')
    ledger.register_cost('Hall hire', 'Invoice H-22, November', 40000)
    assert direct_vm.run_validator() is True
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r'Classify whether[\s\S]*', '[{"index":0,"relation":"SAME"}]')
    assert direct_vm.run_validator() is False
    assert direct_vm.run_validator(leader_result='[]') is False
    assert direct_vm.run_validator(leader_error=ValueError('bad leader')) is False


@pytest.mark.parametrize('response', ['{}', '[]', '[{"index":1,"relation":"DISTINCT"}]', '[{"index":0,"relation":"ALLOW"}]'])
def test_malformed_model_output_rollback(ledger, direct_vm, response):
    direct_vm.mock_llm(r'Classify whether[\s\S]*', response)
    before = ledger.snapshot()
    with pytest.raises(Exception):
        ledger.register_cost('Other expense', 'Invoice other', 1)
    assert ledger.snapshot() == before
