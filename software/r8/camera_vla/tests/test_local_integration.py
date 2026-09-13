import sys,threading,unittest
from pathlib import Path
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from microduck_vision.httpio import post
from microduck_vision.protocol import PROFILE,ReplyGate,submission_context
from microduck_vision.host import make_server as vision_server,MockPolicy
from microduck_interaction.executor import Arbiter
from microduck_interaction.server import make_server as local_server
from test_bridge import obs

class LocalIntegrationTests(unittest.TestCase):
 def setUp(self):
  self.token='offline-integration-token-12345678';self.clock=[10.1];self.arbiter=Arbiter(clock=lambda:self.clock[0]);self.local=local_server(self.arbiter,port=0,token=self.token);self.vision=vision_server(('127.0.0.1',0),self.token,MockPolicy());self.threads=[]
  for server in (self.local,self.vision):
   t=threading.Thread(target=server.serve_forever,daemon=True);t.start();self.threads.append(t)
  self.url='http://127.0.0.1:'+str(self.local.server_port);self.vurl='http://127.0.0.1:'+str(self.vision.server_port)
 def tearDown(self):
  for server in (self.local,self.vision):server.shutdown();server.server_close()
  for t in self.threads:t.join()
 def test_camera_host_gate_local_arbiter(self):
  o=obs();o['simulated']=True;r=post(self.vurl+'/v1/observe',o,self.token);plan=ReplyGate().accept(o,r,10.1)
  sid=post(self.url+'/v1/sessions',{'source':'vla','duration_s':1},self.token)['session_id']
  post(self.url+'/v1/intents',{'session_id':sid,'sequence':1,'robot_profile':PROFILE,'intent':plan['intent'],'vla_context':submission_context(o)},self.token)
  frame=self.arbiter.frame();self.assertEqual(len(frame['commands']),13);self.assertEqual(frame['mouth_rad'],0)
  self.clock[0]=11.2;self.assertIsNone(self.arbiter.frame())
 def test_vla_cannot_take_manual_session(self):
  post(self.url+'/v1/sessions',{'source':'manual','duration_s':1},self.token)
  with self.assertRaises(HTTPError) as e:post(self.url+'/v1/sessions',{'source':'vla','duration_s':1},self.token)
  self.assertEqual(e.exception.code,409)
if __name__=='__main__':unittest.main()
