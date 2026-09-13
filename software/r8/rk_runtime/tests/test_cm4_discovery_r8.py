import importlib.util,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'deploy/cm4-bsp/discover.py'
spec=importlib.util.spec_from_file_location('cm4_discover',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DiscoverTests(unittest.TestCase):
 def fixture(self,t,number=17):
  root=pathlib.Path(t);dt=root/'dt';sys=root/'i2c';dt.mkdir();sys.mkdir()
  (dt/'aliases').mkdir();(dt/'aliases/microduck-sensors').write_bytes(b'/i2c@2acb0000\0')
  (dt/'compatible').write_bytes(b'microduck,r8-cm4\0radxa,cm4\0')
  node=dt/'i2c@2acb0000';node.mkdir();(node/'status').write_bytes(b'okay\0')
  dev=sys/f'i2c-{number}'/'device';dev.mkdir(parents=True);(dev/'of_node').symlink_to(node)
  return dt,sys,node
 def test_matches_node_not_alias_number(self):
  with tempfile.TemporaryDirectory() as t:
   dt,sys,node=self.fixture(t);self.assertEqual(m.find_sensor_bus(dt,sys),'/dev/i2c-17')
 def test_rejects_ambiguous_nodes(self):
  with tempfile.TemporaryDirectory() as t:
   dt,sys,node=self.fixture(t);d=sys/'i2c-8/device';d.mkdir(parents=True);(d/'of_node').symlink_to(node)
   with self.assertRaises(RuntimeError):m.find_sensor_bus(dt,sys)
 def test_rejects_disabled_wrong_board_missing_adapter(self):
  with tempfile.TemporaryDirectory() as t:
   dt,sys,node=self.fixture(t);(node/'status').write_bytes(b'disabled\0')
   with self.assertRaises(RuntimeError):m.find_sensor_bus(dt,sys)
   (node/'status').write_bytes(b'okay\0');(dt/'compatible').write_bytes(b'radxa,zero-3w\0')
   with self.assertRaises(RuntimeError):m.find_sensor_bus(dt,sys)
   (dt/'compatible').write_bytes(b'microduck,r8-cm4\0');(sys/'i2c-17/device/of_node').unlink()
   with self.assertRaises(RuntimeError):m.find_sensor_bus(dt,sys)
 def test_no_arbitrary_alias_outside_dt(self):
  with tempfile.TemporaryDirectory() as t:
   dt,sys,node=self.fixture(t);(dt/'aliases/microduck-sensors').write_bytes(b'/../../etc\0')
   with self.assertRaises(RuntimeError):m.find_sensor_bus(dt,sys)
if __name__=='__main__':unittest.main()
