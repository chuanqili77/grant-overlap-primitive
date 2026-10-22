"""Permission and activation tests with mocked GenVM and model responses."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from test_contract import gl, Harness

previous = sys.modules.get('genlayer')
sys.modules['genlayer'] = types.SimpleNamespace(gl=gl)
spec = importlib.util.spec_from_file_location('contract_v2', Path(__file__).parents[1] / 'contracts/grant_overlap_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if previous is None:
    del sys.modules['genlayer']
else:
    sys.modules['genlayer'] = previous

PROJECT = '0x' + '1' * 40
A = '0x' + 'a' * 40
B = '0x' + 'b' * 40
OUTSIDER = '0x' + '4' * 40

class MultiPartyTests(unittest.TestCase):
    def setUp(self):
        gl.message.sender_address = PROJECT
        Harness.reject = False
        Harness.response = '[{"index":0,"relation":"DISTINCT"}]'
        self.c = m.GrantOverlapV2('Workshop', 'USD', A, B)

    def call(self, sender, method, *args):
        gl.message.sender_address = sender
        return getattr(self.c, method)(*args)

    def state(self):
        return json.loads(self.c.snapshot())

    def approved(self, description='Microscope', evidence='Invoice A', cap=10000):
        self.call(PROJECT, 'propose_cost', description, evidence, cap)
        proposal_id = len(self.state()['proposals'])
        self.call(A, 'approve_cost', proposal_id)
        self.call(B, 'approve_cost', proposal_id)
        return proposal_id

    def active(self):
        proposal_id = self.approved()
        self.call(PROJECT, 'activate_cost', proposal_id)

    def fails_unchanged(self, sender, method, *args):
        before = self.c.snapshot()
        with self.assertRaises(ValueError):
            self.call(sender, method, *args)
        self.assertEqual(self.c.snapshot(), before)

    def test_members_must_be_distinct_valid_nonzero_addresses(self):
        gl.message.sender_address = PROJECT
        for first, second in [(A, A.upper().replace('0X', '0x')), (PROJECT, B), ('invalid', B), ('0x' + '0'*40, B)]:
            with self.assertRaises(ValueError):
                m.GrantOverlapV2('P', 'USD', first, second)

    def test_project_cannot_approve_or_activate_alone(self):
        self.call(PROJECT, 'propose_cost', 'Microscope', 'Invoice A', 10000)
        self.fails_unchanged(PROJECT, 'approve_cost', 1)
        self.fails_unchanged(PROJECT, 'activate_cost', 1)
        self.assertEqual(self.state()['costs'], [])

    def test_one_approval_and_repeated_signature_do_not_reach_quorum(self):
        self.call(PROJECT, 'propose_cost', 'Microscope', 'Invoice A', 10000)
        self.call(A, 'approve_cost', 1)
        self.fails_unchanged(A, 'approve_cost', 1)
        self.fails_unchanged(B, 'activate_cost', 1)

    def test_pending_proposals_cannot_receive_reservations(self):
        self.approved()
        self.fails_unchanged(A, 'reserve', 1, 100, 'a')

    def test_both_funders_can_activate_immutable_proposal(self):
        proposal_id = self.approved()
        self.call(B, 'activate_cost', proposal_id)
        s = self.state()
        self.assertEqual(s['costs'][0]['cap'], 10000)
        self.assertEqual(s['proposals'][0]['status'], 'ACTIVE')
        self.fails_unchanged(PROJECT, 'activate_cost', proposal_id)
        self.fails_unchanged(A, 'approve_cost', proposal_id)
        self.assertFalse(hasattr(self.c, 'register_cost'))

    def test_activation_compares_against_latest_active_ledger(self):
        first = self.approved('Microscope', 'Invoice A')
        second = self.approved('Optical equipment', 'Invoice A')
        self.call(PROJECT, 'activate_cost', first)
        Harness.response = '[{"index":0,"relation":"SAME"}]'
        self.fails_unchanged(B, 'activate_cost', second)
        self.assertEqual(len(self.state()['costs']), 1)
        self.assertEqual(self.state()['proposals'][1]['status'], 'PENDING')

    def test_both_signatures_cannot_override_uncertainty_or_consensus_failure(self):
        self.active()
        second = self.approved('Other expense', 'Evidence')
        Harness.response = '[{"index":0,"relation":"UNCERTAIN"}]'
        self.fails_unchanged(PROJECT, 'activate_cost', second)
        Harness.response = '[{"index":0,"relation":"DISTINCT"}]'
        Harness.reject = True
        self.fails_unchanged(A, 'activate_cost', second)

    def test_distinct_expense_activates_after_both_approvals(self):
        self.active()
        second = self.approved('Hall', 'Invoice B', 4000)
        self.call(A, 'activate_cost', second)
        self.assertEqual(len(self.state()['costs']), 2)

    def test_reservations_bind_sender_and_share_cap(self):
        self.active()
        self.call(A, 'reserve', 1, 6000, 'a')
        self.call(B, 'reserve', 1, 4000, 'b')
        self.assertEqual([x['funder'] for x in self.state()['reservations']], [A, B])
        self.fails_unchanged(B, 'reserve', 1, 1, 'over')
        self.fails_unchanged(PROJECT, 'reserve', 1, 1, 'project')

    def test_only_recorded_funder_can_release_and_history_is_preserved(self):
        self.active()
        self.call(A, 'reserve', 1, 10000, 'a')
        self.fails_unchanged(PROJECT, 'release', 1)
        self.fails_unchanged(B, 'release', 1)
        self.call(A, 'release', 1)
        self.call(B, 'reserve', 1, 10000, 'b')
        self.assertEqual(len(self.state()['reservations']), 2)
        self.assertFalse(self.state()['reservations'][0]['active'])
        self.fails_unchanged(A, 'release', 1)
        self.fails_unchanged(A, 'reserve', 1, 1, 'a')

    def test_nonparticipants_cannot_write(self):
        self.active()
        for method, args in [('propose_cost', ('X', 'Y', 1)), ('approve_cost', (1,)), ('activate_cost', (1,)), ('reserve', (1, 1, 'x')), ('release', (1,))]:
            self.fails_unchanged(OUTSIDER, method, *args)

    def test_funders_can_propose_without_project_gatekeeper(self):
        self.call(A, 'propose_cost', 'Hall', 'Invoice B', 4000)
        self.assertEqual(self.state()['proposals'][0]['proposer'], A)
        self.assertEqual(self.state()['proposals'][0]['approvals'], [])

if __name__ == '__main__':
    unittest.main()
