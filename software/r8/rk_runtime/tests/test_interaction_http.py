import importlib.util,json,threading,time,unittest,urllib.error,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
SERVER=importlib.util.find_spec('microduck_interaction.server') is not None
PROVIDERS=importlib.util.find_spec('microduck_interaction.providers') is not None
class HttpAvailability(unittest.TestCase):
    def test_server_and_provider_adapters_exist(self):self.assertTrue(SERVER and PROVIDERS,'HTTP layer not implemented')
@unittest.skipUnless(SERVER,'pending')
class ServerTests(unittest.TestCase):
    def setUp(self):
        from microduck_interaction.server import make_server
        from microduck_interaction.executor import Arbiter
        self.a=Arbiter();self.server=make_server(self.a,port=0,token='x'*32)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.a.shutdown()
    def request(self,path,body=None,key='x'*32):
        r=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urllib.request.urlopen(r,timeout=1) as f:return json.load(f)
    def test_auth_real_http_roundtrip_and_replay_rejection(self):
        from microduck_interaction.schema import ROBOT_PROFILE
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/v1/status',key='wrong')
        self.assertEqual(e.exception.code,401)
        sid=self.request('/v1/sessions',{'source':'vla','duration_s':2})['session_id']
        body={'session_id':sid,'sequence':0,'robot_profile':ROBOT_PROFILE,'intent':{'vx':.1,'duration_s':.3}}
        from microduck_rk.motion_limits import limits_sha256
        now=time.monotonic();body['vla_context']={'capture_monotonic_s':now,'deadline_monotonic_s':now+.75,'calibration_sha256':'a'*64,'motion_limits_sha256':limits_sha256(),'motion_context':'head_home_locked'}
        self.assertTrue(self.request('/v1/intents',body)['accepted'])
        state=self.request('/v1/status');self.assertEqual(state['active_source'],'vla');self.assertEqual(state['last_sequence'],0)
        with self.assertRaises(urllib.error.HTTPError):self.request('/v1/intents',body)
        self.request('/v1/stop',{'session_id':sid});self.assertIsNone(self.a.frame())
    def test_unrecognized_intent_never_reaches_arbiter(self):
        from microduck_interaction.schema import ROBOT_PROFILE
        sid=self.request('/v1/sessions',{'source':'test','duration_s':2})['session_id']
        with self.assertRaises(urllib.error.HTTPError):self.request('/v1/intents',{'session_id':sid,'sequence':0,'robot_profile':ROBOT_PROFILE,'intent':{'duration_s':.2,'shell':'echo danger'}})
        self.assertIsNone(self.a.frame())
@unittest.skipUnless(PROVIDERS,'pending')
class ProviderTests(unittest.TestCase):
    def test_generic_llm_uses_real_http_and_validates_response(self):
        from microduck_interaction.providers import Providers
        from microduck_interaction.schema import ROBOT_PROFILE
        observed=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                observed.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                response={'robot_profile':ROBOT_PROFILE,'say':'hello','intent':{'duration_s':.2}}
                data=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def log_message(self,*a):pass
        s=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
        try:
            p=Providers(llm_url='http://127.0.0.1:'+str(s.server_port),timeout=.2)
            self.assertEqual(p.plan('hello')['say'],'hello');self.assertEqual(observed[0]['text'],'hello')
        finally:s.shutdown();s.server_close()
    def test_network_failure_does_not_fabricate_plan(self):
        from microduck_interaction.providers import Providers,ProviderError
        with self.assertRaises(ProviderError):Providers(llm_url='http://127.0.0.1:1',timeout=.1).plan('hello')
