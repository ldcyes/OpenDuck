"""Regression gates against false sway-reduction claims; no hardware claim."""
from pathlib import Path
import sys,unittest,copy,importlib.util
sys.dont_write_bytecode=True
import numpy as np
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent

def sample_trace(deg,time_scale=1.,camera=None):
 ss=[]
 for i,angle in enumerate([-deg,0.,deg]):
  T=np.eye(4);T[:3,:3]=Rotation.from_euler('x',angle,degrees=True).as_matrix()
  ss.append(dict(time_s=i*time_scale,q_HOME_delta_deg={},base_transform_m=T.tolist(),phase='same_phase',camera_transform_m=camera))
 return {'samples':ss}

class SwayRegression(unittest.TestCase):
 def setUp(self):
  p=HERE/'sway_metrics.py';self.assertTrue(p.exists(),'Reusable world-sway implementation is not yet present')
  sp=importlib.util.spec_from_file_location('sway_metrics',p);self.m=importlib.util.module_from_spec(sp);sp.loader.exec_module(self.m)
  self.c=dict(joints=[],marker=dict(link_frame='trunk_base',HOME_point_m=[0,0,.284]),targets=dict(minimum_actual_roll_reduction_fraction=.4,minimum_actual_head_marker_Y_reduction_fraction=.3))
 def test_perfect_tracking_of_large_sway_is_not_reduction(self):
  large=sample_trace(20);imperfect_reference=sample_trace(25)
  olderr=self.m.tracking_diagnostics(large,imperfect_reference,self.c)['time_aligned']['maximum_root_orientation_error_deg'];newerr=self.m.tracking_diagnostics(large,large,self.c)['time_aligned']['maximum_root_orientation_error_deg']
  self.assertGreater(olderr,4.9);self.assertLess(newerr,1e-10)
  verdict=self.m.compare_actual(self.m.world_metrics(large,self.c),self.m.world_metrics(large,self.c),self.c)
  self.assertFalse(verdict['both_sway_targets_met']);self.assertAlmostEqual(verdict['actual_roll_reduction_fraction'],0)
 def test_camera_metadata_cannot_change_world_sway(self):
  a=sample_trace(20);C=np.eye(4);C[:3,:3]=Rotation.from_euler('zy',[80,40],degrees=True).as_matrix();C[:3,3]=[4,3,2];b=sample_trace(20,camera=C.tolist())
  self.assertEqual(self.m.world_metrics(a,self.c),self.m.world_metrics(b,self.c))
 def test_retiming_is_not_reduction_and_phase_alignment_is_separate(self):
  a=sample_trace(20);slow=sample_trace(20,time_scale=2.)
  ma=self.m.world_metrics(a,self.c);mb=self.m.world_metrics(slow,self.c)
  self.assertEqual(ma['metrics'],mb['metrics']);self.assertFalse(self.m.compare_actual(ma,mb,self.c)['both_sway_targets_met'])
  track=self.m.tracking_diagnostics(a,slow,self.c)
  self.assertGreater(track['time_aligned']['maximum_root_orientation_error_deg'],15)
  self.assertLess(track['phase_progress_aligned']['maximum_root_orientation_error_deg'],1e-9)
 def test_real_world_amplitude_reduction_meets_both_gates(self):
  a=self.m.world_metrics(sample_trace(20),self.c);b=self.m.world_metrics(sample_trace(10),self.c);v=self.m.compare_actual(a,b,self.c)
  self.assertTrue(v['both_sway_targets_met']);self.assertAlmostEqual(v['actual_roll_reduction_fraction'],.5);self.assertGreater(v['actual_head_marker_Y_reduction_fraction'],.49)
 def test_marker_home_point_uses_kinematic_link_before_world_root(self):
  self.c['joints']=[dict(joint='head_roll',parent_link='trunk_base',child_link='head',axis_trunk=[1,0,0],pivot_trunk_mm=[0,0,100])];self.c['marker']['link_frame']='head'
  tr=sample_trace(0)
  for s,q in zip(tr['samples'],[-10,0,10]):s['q_HOME_delta_deg']={'head_roll':q}
  m=self.m.world_metrics(tr,self.c)
  self.assertAlmostEqual(m['metrics']['trunk_roll_deg']['peak_to_peak'],0)
  self.assertAlmostEqual(m['metrics']['head_marker_world_Y_mm']['peak_to_peak'],2*184*np.sin(np.radians(10)),places=9)

if __name__=='__main__':unittest.main(verbosity=2)
