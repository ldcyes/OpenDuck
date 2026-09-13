import base64,io,json,os,struct,tempfile,time,unittest,wave
from pathlib import Path
from unittest.mock import patch
from microduck_interaction.audio import WavData
from microduck_interaction.executor import Arbiter,Executor
from microduck_interaction.schema import ROBOT_PROFILE
from test_interaction_audio import wav_bytes

class Extensions(unittest.TestCase):
    def test_16k_tts_resampled_to_fixed_48k_without_duration_or_gain_increase(self):
        data=WavData.from_bytes(wav_bytes([20000]*1600,rate=16000))
        self.assertEqual(data.rate,48000);self.assertEqual(len(data.pcm),4800*2)
        self.assertAlmostEqual(data.duration,.1);self.assertEqual(len(data.levels),5)
        self.assertEqual(max(struct.unpack('<4800h',data.pcm)),4000)
    def test_dry_executor_never_writes_live_file_and_stop_file_ends_lease(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);a=Arbiter();sid=a.start_session('test',2)['session_id']
            a.submit(sid,0,ROBOT_PROFILE,{'duration_s':1.})
            e=Executor(a,p/'live.json',dry_log=p/'dry.jsonl',stop_file=p/'STOP');e.start()
            try:
                time.sleep(.04);self.assertTrue((p/'dry.jsonl').exists());self.assertFalse((p/'live.json').exists())
                (p/'STOP').touch();e.thread.join(1.)
                self.assertIsNotNone(e.error);self.assertIsNone(a.frame());self.assertFalse(e.thread.is_alive())
            finally:e.close()
    def test_new_session_does_not_inherit_old_audio_error(self):
        a=Arbiter();sid=a.start_session('old',2)['session_id'];a.audio_error='old playback failed'
        a.stop(sid);a.start_session('new',2);self.assertIsNone(a.status()['last_audio_error'])
    def test_sent_telemetry_labels_are_separate_from_measured_joints(self):
        from microduck_rk.telemetry import publish
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'
            publish(p,{'positions':[.1]*15,'velocities':[.2]*15},{'gyro':[0]*3,'gravity':[0,0,-1],'age_s':.01},'hash',ROBOT_PROFILE,True,10.,
                    {'commands':[0]*13,'mouth_rad':.02,'monotonic_s':10.01,'source_monotonic_s':9.99})
            v=json.loads(p.read_text());self.assertEqual(v['q'],[.1]*15);self.assertEqual(v['sent_mouth_rad'],.02)
            self.assertEqual(v['sent_monotonic_s'],10.01);self.assertEqual(v['monotonic_s'],10.)
    def test_chat_model_has_deterministic_bounded_generation(self):
        from microduck_interaction.providers import Providers
        result={'robot_profile':ROBOT_PROFILE,'say':'','intent':{'duration_s':.2}}
        with patch.dict(os.environ,{'MICRODUCK_LLM_PROTOCOL':'chat-completions','MICRODUCK_LLM_MODEL':'local','MICRODUCK_LLM_MAX_TOKENS':'256'}):
            with patch.object(Providers,'_call',return_value=(json.dumps({'choices':[{'message':{'content':json.dumps(result)}}]}).encode(),'application/json')) as call:
                Providers().plan('hi');payload=call.call_args.args[1]
                self.assertEqual(payload['max_tokens'],256);self.assertEqual(payload['temperature'],0.)
    def test_real_speech_gateway_module_exists(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('microduck_interaction.speech_gateway'))
    def test_legacy_command_cli_respects_executor_lock(self):
        import subprocess,sys
        from microduck_interaction.executor import CommandWriter
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'command.json'
            with CommandWriter(path):
                r=subprocess.run([sys.executable,'-m','microduck_rk','command','--path',str(path),'--seconds','.1'],capture_output=True,text=True,timeout=2.)
                self.assertNotEqual(r.returncode,0);self.assertIn('owns this command path',r.stderr);self.assertFalse(path.exists())
    def test_huge_json_integer_is_rejected_as_validation_error(self):
        from microduck_interaction.schema import validate_intent
        with self.assertRaises(ValueError):validate_intent({'duration_s':1.,'vx':10**1000})
    def test_live_service_template_rejected_before_any_device_or_server(self):
        import subprocess,sys
        env={**os.environ,'MICRODUCK_LOCAL_TOKEN':'x'*32}
        r=subprocess.run([sys.executable,'-m','microduck_interaction','serve','--live-command','--arm-interaction',
                          '--calibration','config/calibration.template.json'],env=env,capture_output=True,text=True,timeout=2.)
        self.assertNotEqual(r.returncode,0);self.assertIn('calibrat',r.stderr.lower())
