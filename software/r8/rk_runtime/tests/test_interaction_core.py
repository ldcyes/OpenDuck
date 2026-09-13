import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

AVAILABLE = importlib.util.find_spec('microduck_interaction.schema') is not None

class ContractAvailability(unittest.TestCase):
    def test_r3_contract_is_implemented(self):
        self.assertTrue(AVAILABLE, 'R3 intent contract has not been implemented')

@unittest.skipUnless(AVAILABLE, 'contract implementation pending')
class IntentTests(unittest.TestCase):
    def test_bounded_plan_maps_exact_legacy_command_order(self):
        from microduck_interaction.schema import validate_plan, command_values, ROBOT_PROFILE
        p=validate_plan({'robot_profile':ROBOT_PROFILE,'say':'你好','intent':{'vx':.1,'head':[.05,.2,.15,.1],'body':[.01,.1,-.1],'duration_s':.5}})
        self.assertEqual(command_values(p['intent']),[.1,0.,0.,.05,.2,.15,.1,0.,0.,.01,.1,-.1,0.])
    def test_shell_joint_unknown_fields_and_nonfinite_are_rejected(self):
        from microduck_interaction.schema import validate_intent
        for bad in [{'shell':'pwd'},{'joints':[0]*15},{'vx':True},{'yaw':float('nan')},{'mouth':float('inf')},{'head':[0]*15},{'duration_s':4},{'vx':.151},{'body':[0,0,.151]}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_intent({'duration_s':.2,**bad})
    def test_wrong_robot_and_duplicate_json_keys_fail(self):
        from microduck_interaction.schema import validate_plan, strict_json
        with self.assertRaises(ValueError):validate_plan({'robot_profile':'wrong','intent':{'duration_s':.2}})
        with self.assertRaises(ValueError):strict_json('{"vx":0,"vx":1}')

@unittest.skipUnless(importlib.util.find_spec('microduck_interaction.executor'), 'executor pending')
class LeaseTests(unittest.TestCase):
    def setUp(self):
        from microduck_interaction.executor import Arbiter
        self.now=10.;self.a=Arbiter(clock=lambda:self.now)
        self.s=self.a.start_session('test',2.)['session_id']
    def test_no_session_or_intent_never_renews(self):
        self.assertIsNone(self.a.frame())
    def test_intent_expires_and_session_expiry_never_mints_lease(self):
        from microduck_interaction.schema import ROBOT_PROFILE
        self.a.submit(self.s,0,ROBOT_PROFILE,{'vx':.1,'duration_s':.2})
        self.assertEqual(self.a.frame()['commands'][0],.1)
        self.now=10.21;frame=self.a.frame()
        self.assertTrue(frame is None or frame['commands'][0]==0)
        self.now=12.01;self.assertIsNone(self.a.frame())
        with self.assertRaises(ValueError):self.a.submit(self.s,1,ROBOT_PROFILE,{'duration_s':.1})
    def test_duplicate_or_reordered_sequence_cannot_extend_motion(self):
        from microduck_interaction.schema import ROBOT_PROFILE
        self.a.submit(self.s,8,ROBOT_PROFILE,{'duration_s':.2})
        for seq in [8,7,True,-1]:
            with self.assertRaises(ValueError):self.a.submit(self.s,seq,ROBOT_PROFILE,{'duration_s':.2})
    def test_session_conflict_and_stop_invalidate_late_provider_result(self):
        from microduck_interaction.schema import ROBOT_PROFILE
        with self.assertRaises(ValueError):self.a.start_session('vla',2.)
        self.a.stop(self.s)
        self.assertIsNone(self.a.frame())
        with self.assertRaises(ValueError):self.a.submit(self.s,1,ROBOT_PROFILE,{'duration_s':.2})
    def test_single_writer_lock_and_atomic_complete_json(self):
        from microduck_interaction.executor import CommandWriter
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'command.json'
            with CommandWriter(p) as first:
                with self.assertRaises(RuntimeError):CommandWriter(p).__enter__()
                first.write({'monotonic_s':1.,'commands':[0.]*13,'mouth_rad':0.})
                self.assertEqual(json.loads(p.read_text())['mouth_rad'],0.)

if __name__=='__main__':unittest.main()
