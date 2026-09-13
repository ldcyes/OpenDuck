"""Backend contracts exercised with test doubles; no claim of model inference."""
import base64,json,os,subprocess,tempfile,threading,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import patch
from microduck_interaction.speech_gateway import SpeechBackend,make_gateway
from microduck_interaction.providers import Providers
from test_interaction_audio import wav_bytes

class Gateway(unittest.TestCase):
    def test_provider_asr_and_tts_roundtrip_through_authenticated_gateway(self):
        wav=wav_bytes([10000]*960)
        observed=[]
        class Backend:
            def execute(self,kind,body):
                observed.append((kind,body))
                return (b'{"text":"hello"}','application/json') if kind=='asr' else (wav,'audio/wav')
        server=make_gateway(Backend(),'s'*32,port=0)
        threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_port)
        try:
            p=Providers(asr_url=url+'/v1/asr',tts_url=url+'/v1/tts',timeout=1.)
            p.keys.update(asr='s'*32,tts='s'*32)
            self.assertEqual(p.transcribe(wav),'hello');self.assertEqual(p.synthesize('hello'),wav)
            self.assertEqual(observed[0][0],'asr');self.assertEqual(base64.b64decode(observed[0][1]['wav_base64']),wav)
            self.assertEqual(observed[1][1]['text'],'hello')
            req=urllib.request.Request(url+'/v1/asr',data=b'{}',headers={'Authorization':'Bearer wrong'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req,timeout=1)
            self.assertEqual(e.exception.code,401)
        finally:server.shutdown();server.server_close()
    def test_gateway_validates_wav_before_starting_real_backend(self):
        backend=SpeechBackend('/missing/model')
        with patch.object(backend,'_run_worker') as run:
            with self.assertRaises(ValueError):backend.execute('asr',{'schema':1,'audio_format':'wav','wav_base64':base64.b64encode(b'invalid').decode()})
            run.assert_not_called()
    def test_espeak_text_is_passed_as_stdin_not_shell_or_options(self):
        from microduck_interaction.speech_worker import main
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/'speech.txt';out=Path(d)/'speech.wav';text='hello; $(touch /tmp/never) --help'
            inp.write_text(text)
            with patch('sys.argv',['worker','tts',str(inp),str(out)]),patch('microduck_interaction.speech_worker.subprocess.run') as run:
                main();args,kwargs=run.call_args
                self.assertEqual(args[0][0],'espeak-ng');self.assertEqual(args[0][-1],'--stdin')
                self.assertNotIn(text,args[0]);self.assertEqual(kwargs['input'],text.encode());self.assertNotIn('shell',kwargs)
    def test_gateway_requires_installed_backend_and_local_model(self):
        with patch('microduck_interaction.speech_gateway.importlib.util.find_spec',return_value=None):
            with self.assertRaises(RuntimeError):SpeechBackend('/missing/model').check_dependencies()
    def test_audio_cannot_outlive_session_or_replay_sequence(self):
        from microduck_interaction.executor import Arbiter
        class Audio:
            duration=1.
            def start(self):raise AssertionError('invalid audio must never start')
        a=Arbiter();sid=a.start_session('test',1)['session_id']
        with self.assertRaises(ValueError):a.attach_audio(sid,0,Audio())
        self.assertIsNone(a.frame())
    def test_local_asr_model_requires_tokenizer_to_prevent_implicit_download(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'model.bin').touch()
            with patch('microduck_interaction.speech_gateway.importlib.util.find_spec',return_value=object()):
                with self.assertRaises(ValueError):SpeechBackend(d).check_dependencies()
    def test_speech_gateway_port_and_loopback_are_enforced(self):
        import inspect
        self.assertEqual(inspect.signature(make_gateway).parameters['port'].default,8768)
        with self.assertRaises(ValueError):make_gateway(object(),'s'*32,host='0.0.0.0',port=0)
    def test_timeout_kills_worker_and_real_grandchild(self):
        import sys,time
        with tempfile.TemporaryDirectory() as d:
            pidfile=Path(d)/'pid';backend=SpeechBackend('/missing/model',timeout=1.)
            code="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)"
            with self.assertRaises(subprocess.TimeoutExpired):backend._run_worker([sys.executable,'-c',code,str(pidfile)])
            pid=int(pidfile.read_text());stat=Path('/proc')/str(pid)/'stat'
            deadline=time.monotonic()+1.
            while stat.exists() and stat.read_text().split()[2]!='Z' and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z','grandchild still executing after gateway timeout')
    def test_shutdown_cancels_active_worker_group(self):
        import sys,time
        backend=SpeechBackend('/missing/model',timeout=10.);errors=[]
        def job():
            try:backend._run_worker([sys.executable,'-c','import time;time.sleep(30)'])
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=job);t.start()
        try:
            deadline=time.monotonic()+1.
            while not getattr(backend,'processes',None) and time.monotonic()<deadline:time.sleep(.01)
            backend.close();t.join(1.)
            self.assertFalse(t.is_alive());self.assertTrue(errors)
        finally:
            if hasattr(backend,'close'):backend.close()
