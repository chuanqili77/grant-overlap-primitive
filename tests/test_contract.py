"""Deterministic Python harness. Does not emulate GenVM or network consensus."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

class Return:
    def __init__(self, data): self.calldata = data

class Harness:
    response = '[]'
    reject = False
    seen = None
    @classmethod
    def run(cls, leader, validator):
        data = leader()
        cls.seen = validator
        if cls.reject or not validator(Return(data)): raise ValueError('Consensus rejected')
        return data

gl = types.SimpleNamespace(Contract=object, public=types.SimpleNamespace(write=lambda f:f, view=lambda f:f), message=types.SimpleNamespace(sender_address='alice'), nondet=types.SimpleNamespace(exec_prompt=lambda p,**kwargs:Harness.response), vm=types.SimpleNamespace(UserError=ValueError, Return=Return, run_nondet_unsafe=Harness.run))
original_genlayer = sys.modules.get('genlayer')
sys.modules['genlayer'] = types.SimpleNamespace(gl=gl)
spec = importlib.util.spec_from_file_location('contract', Path(__file__).parents[1]/'contracts/grant_overlap.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if original_genlayer is None:
    del sys.modules['genlayer']
else:
    sys.modules['genlayer'] = original_genlayer

class ContractTests(unittest.TestCase):
    def setUp(self):
        gl.message.sender_address = 'alice'
        Harness.reject = False
        Harness.response = '[{"index":0,"relation":"DISTINCT"}]'
        self.c = m.GrantOverlap('Community lab', 'USD')
        self.c.register_cost('Microscope invoice A', 'Invoice A, supplier One, one microscope', 10000)
    def state(self): return json.loads(self.c.snapshot())
    def test_split_funding(self):
        self.c.reserve(1,'Fund A',6000,'a')
        self.c.reserve(1,'Fund B',4000,'b')
        self.assertEqual(sum(x['amount'] for x in self.state()['reservations']),10000)
    def test_over_cap_atomic(self):
        self.c.reserve(1,'Fund A',6000,'a')
        before = self.c.snapshot()
        with self.assertRaises(ValueError): self.c.reserve(1,'Fund B',4001,'b')
        self.assertEqual(before,self.c.snapshot())
    def test_release_reopens_capacity(self):
        self.c.reserve(1,'Fund A',10000,'a'); self.c.release(1)
        self.c.reserve(1,'Fund B',10000,'b')
        self.assertFalse(self.state()['reservations'][0]['active'])
    def test_references_never_reused(self):
        self.c.reserve(1,'Fund A',100,'a'); self.c.release(1)
        with self.assertRaises(ValueError): self.c.reserve(1,'Fund B',100,'a')
    def test_double_release(self):
        self.c.reserve(1,'Fund A',100,'a'); self.c.release(1)
        with self.assertRaises(ValueError): self.c.release(1)
    def test_only_registrar(self):
        gl.message.sender_address='bob'
        for action in [lambda:self.c.reserve(1,'X',1,'b'),lambda:self.c.release(1),lambda:self.c.register_cost('X','Y',1)]:
            with self.assertRaises(ValueError): action()
    def test_duplicate_and_uncertain_fail_closed(self):
        for relation in ['SAME','UNCERTAIN']:
            Harness.response=json.dumps([{'index':0,'relation':relation}])
            before=self.c.snapshot()
            with self.assertRaises(ValueError): self.c.register_cost('Renamed invoice A','Invoice A',100)
            self.assertEqual(before,self.c.snapshot())
    def test_distinct_accepted(self):
        self.c.register_cost('Venue rental','Hall B, November, invoice B',2000)
        self.assertEqual(len(self.state()['costs']),2)
    def test_validator_independent(self):
        self.c.register_cost('Venue rental','Hall B invoice B',2000)
        Harness.response='[{"index":0,"relation":"SAME"}]'
        self.assertFalse(Harness.seen(Return('[{"index":0,"relation":"DISTINCT"}]')))
        self.assertFalse(Harness.seen(object()))
    def test_malformed_outputs(self):
        for raw in ['{}','[]','[{"index":2,"relation":"DISTINCT"}]','[{"index":0,"relation":"CLEAR"}]']:
            Harness.response=raw
            with self.assertRaises((ValueError,TypeError)): self.c.register_cost('X','Y',1)
    def test_consensus_rejection_atomic(self):
        Harness.reject=True
        before=self.c.snapshot()
        with self.assertRaises(ValueError):self.c.register_cost('X','Y',1)
        self.assertEqual(before,self.c.snapshot())
    def test_invalid_amounts(self):
        for n in [0,-1,True,1.5,10**12+1]:
            with self.assertRaises(ValueError):self.c.reserve(1,'F',n,'r')
    def test_unknown_ids(self):
        for n in [0,-1,2,True]:
            with self.assertRaises(ValueError):self.c.reserve(n,'F',1,'r')
    def test_text_limits(self):
        for text in ['', ' ', 'x'*901]:
            with self.assertRaises(ValueError):self.c.register_cost(text,'Evidence',1)
    def test_cost_limit(self):
        for i in range(1,24):
            Harness.response=json.dumps([{'index':j,'relation':'DISTINCT'} for j in range(i)])
            self.c.register_cost('Distinct cost '+str(i),'Invoice '+str(i),100)
        before=self.c.snapshot()
        with self.assertRaises(ValueError):self.c.register_cost('25th','Invoice 25',100)
        self.assertEqual(before,self.c.snapshot())
    def test_reservation_limit(self):
        for i in range(120):self.c.reserve(1,'Fund',1,str(i))
        before=self.c.snapshot()
        with self.assertRaises(ValueError):self.c.reserve(1,'Fund',1,'overflow')
        self.assertEqual(before,self.c.snapshot())
    def test_reference_limits_and_empty(self):
        for field in ['', ' ', 'x'*161]:
            with self.assertRaises(ValueError):self.c.reserve(1,'Fund',1,field)
            with self.assertRaises(ValueError):self.c.reserve(1,field,1,'ref')
    def test_full_vector_and_schema(self):
        for raw in ['[1]', '[{"index":true,"relation":"DISTINCT"}]', '[{"index":0,"relation":"DISTINCT","extra":true}]']:
            Harness.response=raw
            with self.assertRaises(ValueError):self.c.register_cost('X','Y',1)
    def test_supported_minor_units(self):
        with self.assertRaises(ValueError):m.GrantOverlap('P','JPY')

    def test_currency(self):
        for currency in ['usd','US','123','USDD']:
            with self.assertRaises(ValueError):m.GrantOverlap('P',currency)

if __name__ == '__main__': unittest.main()
