import unittest
from microduck_rk.power import RegenEnergy,PowerFault
class RegenTests(unittest.TestCase):
 def sample(self,t,current,volts=10.):return {'monotonic_s':t,'brake':{'bus_V':volts,'current_A':current}}
 def test_exact_event_limit_and_duplicate_samples(self):
  e=RegenEnergy();e.observe(self.sample(0,10));e.observe(self.sample(.1,10));e.observe(self.sample(.1,10));self.assertAlmostEqual(e.snapshot(.1)['event_J'],10)
  with self.assertRaisesRegex(PowerFault,'event'):e.observe(self.sample(.2,10))
 def test_idle_end_and_rolling_window_not_reset_by_event(self):
  e=RegenEnergy();e.observe(self.sample(0,1));e.observe(self.sample(.1,1));e.observe(self.sample(.2,0))
  for i in range(3,14):e.observe(self.sample(i/10,0))
  s=e.snapshot(1.3);self.assertFalse(s['event_active']);self.assertAlmostEqual(s['event_J'],0);self.assertAlmostEqual(s['rolling30_J'],2)
  e.observe(self.sample(1.4,1));self.assertTrue(e.snapshot(1.4)['event_active']);self.assertGreater(e.snapshot(1.4)['rolling30_J'],2)
 def test_rolling_limit_across_multiple_small_events(self):
  e=RegenEnergy();t=0.;e.observe(self.sample(t,0))
  with self.assertRaisesRegex(PowerFault,'rolling'):
   for event in range(6):
    for j in range(15):t+=.1;e.observe(self.sample(t,1))
    for j in range(12):t+=.1;e.observe(self.sample(t,0))
 def test_partial_expiry_integrates_only_overlap(self):
  e=RegenEnergy();e.observe(self.sample(0,1));e.observe(self.sample(.1,1));e.observe(self.sample(.2,0))
  for j in range(3,301):e.observe(self.sample(j/10,0))
  self.assertAlmostEqual(e.snapshot(30.05)['rolling30_J'],1.5,places=7)
  self.assertAlmostEqual(e.snapshot(30.21)['rolling30_J'],0)
 def test_invalid_missing_reverse_and_gaps_rejected(self):
  for sample in [{'monotonic_s':0},self.sample(0,float('nan')),self.sample(0,-.03)]:
   with self.assertRaises(PowerFault):RegenEnergy().observe(sample)
  e=RegenEnergy();e.observe(self.sample(1,0))
  for sample in [self.sample(.9,0),self.sample(1.101,0)]:
   with self.assertRaises(PowerFault):e.observe(sample)
 def test_uses_actual_brake_channel_sample_time(self):
  e=RegenEnergy();a=self.sample(0,10);a['brake']['monotonic_s']=.01;e.observe(a)
  b=self.sample(.05,10);b['brake']['monotonic_s']=.11;e.observe(b)
  self.assertAlmostEqual(e.snapshot(.11)['event_J'],10)
 def test_small_negative_zero_offset_has_no_negative_energy(self):
  e=RegenEnergy();e.observe(self.sample(0,-.01,-.05));e.observe(self.sample(.1,-.01,-.05));self.assertEqual(e.snapshot(.1)['rolling30_J'],0)
if __name__=='__main__':unittest.main()
