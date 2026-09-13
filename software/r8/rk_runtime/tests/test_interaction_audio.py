import importlib.util,io,math,struct,tempfile,time,unittest,wave
AVAILABLE=importlib.util.find_spec('microduck_interaction.audio') is not None

def wav_bytes(samples,rate=48000,width=2,channels=1):
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setnchannels(channels);w.setsampwidth(width);w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h' if width==2 else '<i',v) for v in samples))
    return b.getvalue()

class AudioAvailability(unittest.TestCase):
    def test_audio_implemented(self):self.assertTrue(AVAILABLE,'WAV playback envelope missing')
@unittest.skipUnless(AVAILABLE,'pending')
class AudioTests(unittest.TestCase):
    def test_pcm_volume_envelope_contains_silence_and_sound_at_50hz(self):
        from microduck_interaction.audio import WavData
        data=WavData.from_bytes(wav_bytes([0]*960+[20000]*960),gain=.2)
        self.assertEqual(len(data.chunks),2);self.assertEqual(data.levels[0],0.)
        self.assertGreater(data.levels[1],0.);self.assertAlmostEqual(data.duration,.04)
        self.assertLessEqual(max(struct.unpack('<'+'h'*(len(data.pcm)//2),data.pcm)),4000)
    def test_invalid_or_oversize_wav_and_gain_are_rejected(self):
        from microduck_interaction.audio import WavData
        for raw in [b'not a wav',wav_bytes([0]*100,rate=100)]:
            with self.assertRaises(ValueError):WavData.from_bytes(raw)
        with self.assertRaises(ValueError):WavData.from_bytes(wav_bytes([0]*100),gain=1.)
    def test_stale_or_stopped_playback_closes_instead_of_repeating_old_envelope(self):
        from microduck_interaction.audio import Playback,WavData
        p=Playback(WavData.from_bytes(wav_bytes([20000]*9600)),dry_run=True)
        p._level=.8;p._stamp=1.;p._started_at=1.;p._running=True
        self.assertEqual(p.level(1.1),0.)
        p.cancel();self.assertEqual(p.level(1.01),0.)
    def test_audio_owns_mouth_and_stop_discards_old_model_mouth(self):
        from microduck_interaction.executor import Arbiter
        from microduck_interaction.schema import ROBOT_PROFILE
        class Audio:
            duration=.2
            def start(self):pass
            def cancel(self):self.on=False
            def level(self,t):return .5 if self.on else 0.
            def alive(self,t):return self.on
            on=True
        now=[5.];a=Arbiter(clock=lambda:now[0]);sid=a.start_session('test',2)['session_id']
        a.submit(sid,0,ROBOT_PROFILE,{'mouth':.15,'duration_s':1.})
        p=Audio();a.attach_audio(sid,1,p)
        self.assertAlmostEqual(a.frame()['mouth_rad'],.1)
        p.on=False;self.assertEqual(a.frame()['mouth_rad'],0.)
        now[0]=7.1;self.assertIsNone(a.frame())
    def test_dry_playback_stops_at_end_of_real_wav(self):
        from microduck_interaction.audio import Playback,WavData
        p=Playback(WavData.from_bytes(wav_bytes([15000]*960)),dry_run=True)
        p.start();p.thread.join(1.)
        self.assertFalse(p.alive(time.monotonic()));self.assertEqual(p.level(time.monotonic()),0.)
