"""R8 local interaction CLI. Default service/demo mode has no motor or ALSA access."""
import argparse
import base64
import io
import json
import math
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
import time
import wave
from .audio import DEFAULT_DEVICE,capture_push_to_talk
from .executor import Arbiter,Executor
from .providers import ProviderError,Providers,exchange
from .schema import ROBOT_PROFILE,number,strict_json,validate_plan
from .server import make_server


class LocalClient:
    def __init__(self,url=None,token=None):
        self.url=(url or os.environ.get('MICRODUCK_LOCAL_URL','http://127.0.0.1:8766')).rstrip('/')
        self.token=token if token is not None else os.environ.get('MICRODUCK_LOCAL_TOKEN','')
        if len(self.token)<24:raise ValueError('configure MICRODUCK_LOCAL_TOKEN with at least24 characters')
    def post(self,path,data):return strict_json(exchange(self.url+path,data,self.token,2.,65536)[0])
    def status(self):return strict_json(exchange(self.url+'/v1/status',None,self.token,2.,65536,method='GET')[0])
    def start(self,source):return self.post('/v1/sessions',{'source':source,'duration_s':30.})
    def stop(self,sid):return self.post('/v1/stop',{'session_id':sid})


def demo_wave():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
        # Synthetic two-call duck-like cue, no recording or model-generated speech.
        samples=[]
        for i in range(48000):
            t=i/48000;local=t%0.5
            if local<.28:
                phase=2*math.pi*(650*local-550*local*local)
                envelope=math.sin(math.pi*local/.28)**2
                value=11000*envelope*(math.sin(phase)+.3*math.sin(2*phase)+.15*math.sin(3*phase))
            else:value=0
            samples.append(round(value))
        w.writeframes(struct.pack('<'+'h'*len(samples),*samples))
    return b.getvalue()


def run_turn(client,text,providers,no_speech=False,demo=False):
    if demo and not client.status()['dry_run']:raise ValueError('offline demo refused against a live command executor')
    session=client.start('demo' if demo else 'conversation');sid=session['session_id']
    try:
        if demo:plan={'robot_profile':ROBOT_PROFILE,'say':'离线波形演示；未调用模型。','intent':{'duration_s':1.}}
        else:plan=providers.plan(text)
        plan=validate_plan(plan,session['robot_profile']);print(plan['say'])
        # Prepare speech before submitting any movement. Failure here cannot leave a partial motion plan active.
        wav=None if no_speech or not plan['say'] else (demo_wave() if demo else providers.synthesize(plan['say']))
        client.post('/v1/intents',{'session_id':sid,'sequence':0,'robot_profile':plan['robot_profile'],'intent':plan['intent']})
        duration=plan['intent']['duration_s']
        if wav:
            result=client.post('/v1/audio',{'session_id':sid,'sequence':1,'robot_profile':plan['robot_profile'],'wav_base64':base64.b64encode(wav).decode()})
            duration=max(duration,result['duration_s'])
        end=time.monotonic()+duration+.85
        while time.monotonic()<end:
            state=client.status()
            if state.get('last_audio_error'):raise RuntimeError('playback failed: '+state['last_audio_error'])
            if not state.get('executor_healthy'):raise RuntimeError('executor fault; lease renewal stopped')
            if not state.get('session_active'):raise RuntimeError('session expired before turn completed')
            time.sleep(.05)
    finally:
        try:client.stop(sid)
        except (ValueError,RuntimeError):pass


def play_file(client,path):
    raw=Path(path).read_bytes();session=client.start('audio');sid=session['session_id']
    try:
        result=client.post('/v1/audio',{'session_id':sid,'sequence':0,'robot_profile':session['robot_profile'],
                                      'wav_base64':base64.b64encode(raw).decode()})
        end=time.monotonic()+result['duration_s']+.85
        while time.monotonic()<end:
            state=client.status()
            if state.get('last_audio_error') or not state.get('executor_healthy') or not state.get('session_active'):
                raise RuntimeError('audio/session failed; lease renewal stopped')
            time.sleep(.05)
    finally:
        try:client.stop(sid)
        except (ValueError,RuntimeError):pass


def serve(args):
    number(args.gain,'playback gain',0.,.25)
    token=os.environ.get('MICRODUCK_LOCAL_TOKEN','')
    if args.live_command:
        if not args.arm_interaction or not args.calibration:raise ValueError('live command writing requires --arm-interaction and --calibration')
        if Path(args.stop_file).exists():raise RuntimeError('STOP file present')
        from microduck_rk.contract import Calibration
        cal=Calibration.load(args.calibration,motion=True);jaw=cal.joints[9]
        if not jaw['min_rad']<=args.mouth_closed<args.mouth_open<=jaw['max_rad']:
            raise ValueError('mouth closed/open must fit measured jaw range')
    context_check=None
    if args.live_command:
        from microduck_rk.motion_context import live_context_reader
        context_check=live_context_reader(args.runtime_telemetry,cal.sha256)
    arbiter=Arbiter(mouth_closed=args.mouth_closed,mouth_open=args.mouth_open,context_check=context_check)
    runner=Executor(arbiter,args.command,dry_run=not args.live_command,dry_log=args.dry_log,stop_file=args.stop_file)
    server=make_server(arbiter,port=args.port,token=token,dry_run=not args.live_command,device=args.playback_device,
                       gain=args.gain,executor=runner,audio_dry_run=not (args.live_audio or args.live_command))
    def interrupt(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    try:
        runner.start()
        print(json.dumps({'url':f'http://127.0.0.1:{args.port}','dry_run':not args.live_command,'audio_simulated':not (args.live_audio or args.live_command),'robot_profile':ROBOT_PROFILE}),flush=True)
        server.serve_forever(poll_interval=.1)
    finally:
        server.server_close();runner.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=8766)
    s.add_argument('--command',default='/tmp/microduck-r8-command.json');s.add_argument('--stop-file',default='/tmp/microduck-r8.STOP')
    s.add_argument('--dry-log');s.add_argument('--live-command',action='store_true');s.add_argument('--arm-interaction',action='store_true')
    s.add_argument('--live-audio',action='store_true',help='use ALSA even while command output remains a dry run')
    s.add_argument('--runtime-telemetry',default='/tmp/microduck-r8-state.json');s.add_argument('--calibration');s.add_argument('--mouth-closed',type=float,default=0.);s.add_argument('--mouth-open',type=float,default=.2)
    s.add_argument('--gain',type=float,default=float(os.environ.get('MICRODUCK_AUDIO_GAIN','.2')))
    s.add_argument('--playback-device',default=os.environ.get('MICRODUCK_PLAYBACK_DEVICE',DEFAULT_DEVICE))
    s=sub.add_parser('text');s.add_argument('text');s.add_argument('--no-speech',action='store_true')
    s=sub.add_parser('ptt');s.add_argument('--live-audio',action='store_true');s.add_argument('--wav',help='use an existing local WAV instead of opening ALSA')
    s.add_argument('--no-speech',action='store_true');s.add_argument('--capture-device',default=os.environ.get('MICRODUCK_CAPTURE_DEVICE',DEFAULT_DEVICE))
    s=sub.add_parser('play');s.add_argument('wav')
    sub.add_parser('demo');sub.add_parser('status')
    a=p.parse_args()
    if a.mode=='serve':return serve(a)
    client=LocalClient()
    if a.mode=='status':print(json.dumps(client.status(),ensure_ascii=False,indent=2));return
    if a.mode=='demo':return run_turn(client,'',None,demo=True)
    if a.mode=='play':return play_file(client,a.wav)
    providers=Providers()
    if a.mode=='text':return run_turn(client,a.text,providers,no_speech=a.no_speech)
    if not a.wav and not a.live_audio:raise ValueError('PTT defaults to no hardware: select --wav or explicitly allow --live-audio')
    if a.wav:text=providers.transcribe(Path(a.wav).read_bytes())
    else:
        with tempfile.TemporaryDirectory(prefix='microduck-ptt-') as d:
            recording=capture_push_to_talk(Path(d)/'speech.wav',a.capture_device)
            text=providers.transcribe(recording.read_bytes())
    print('识别：'+text);run_turn(client,text,providers,no_speech=a.no_speech)


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,KeyboardInterrupt) as exc:
        print(f'INTERACTION STOPPED: {exc}',file=sys.stderr);sys.exit(2)
