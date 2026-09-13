import sys,threading,unittest
from pathlib import Path
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.host import make_server,MockPolicy
from microduck_vision.httpio import post
from microduck_vision.protocol import ReplyGate,validate_observation
from test_bridge import obs

class TransportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=make_server(('127.0.0.1',0),'test-only-token',MockPolicy());cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)+'/v1/observe'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.worker.join()
 def test_full_json_roundtrip(self):
  o=obs();o['simulated']=True;r=post(self.url,o,'test-only-token');p=ReplyGate().accept(o,r,10.1);self.assertEqual(p['intent']['vx'],0)
 def test_mock_refuses_live(self):
  with self.assertRaises(HTTPError) as e:post(self.url,obs(),'test-only-token')
  self.assertEqual(e.exception.code,400)
 def test_wrong_token(self):
  with self.assertRaises(HTTPError) as e:post(self.url,obs(),'wrong')
  self.assertEqual(e.exception.code,401)
 def test_remote_plaintext_rejected_before_connect(self):
  with self.assertRaises(ValueError):post('http://192.0.2.1/v1/observe',obs(),'test')
 def test_request_replay(self):
  o=obs();o['simulated']=True;post(self.url,o,'test-only-token')
  with self.assertRaises(HTTPError) as e:post(self.url,o,'test-only-token')
  self.assertEqual(e.exception.code,400)
 def test_boolean_schema_rejected(self):
  o=obs();o['schema']=True
  with self.assertRaises(ValueError):validate_observation(o)
if __name__=='__main__':unittest.main()
