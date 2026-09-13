"""Authenticated host-side faster-whisper CPU ASR and eSpeak NG TTS gateway.

Each request uses a bounded subprocess. This intentionally avoids persistent
model state and limits concurrency toone. Load time counts against timeout.
This code is not evidence that a real ASR model or hardware has been validated.
"""
import argparse,base64,hmac,importlib.util,json,os,shutil,signal,subprocess,sys,tempfile,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .audio import MAX_WAV_BYTES,WavData
from .schema import number,object_keys,strict_json


class SpeechBackend:
    def __init__(self,model_dir,voice='cmn',language='zh',timeout=12.,threads=2):
        self.model_dir=str(Path(model_dir).resolve());self.voice=voice;self.language=language
        self.timeout=number(timeout,'worker timeout',1.,15.)
        if isinstance(threads,bool) or not isinstance(threads,int) or not 1<=threads<=8:raise ValueError('threads must be1..8')
        self.threads=threads;self.processes=set();self.process_lock=threading.Lock();self.closing=False
    @staticmethod
    def _cancel_group(proc):
        # Worker and eSpeak descendants share this dedicated POSIX process group.
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:proc.wait(timeout=1.)
        except subprocess.TimeoutExpired:raise RuntimeError('speech process group did not terminate')
    def _run_worker(self,command):
        with self.process_lock:
            if self.closing:raise RuntimeError('speech backend is shutting down')
            proc=subprocess.Popen(command,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.processes.add(proc)
        try:
            result=proc.wait(timeout=self.timeout)
            if result:raise subprocess.CalledProcessError(result,command)
        finally:
            # Also reap orphaned grandchildren after failed/normal worker exit.
            self._cancel_group(proc)
            with self.process_lock:self.processes.discard(proc)
    def close(self):
        with self.process_lock:self.closing=True;active=list(self.processes)
        for proc in active:self._cancel_group(proc)
    def check_dependencies(self):
        if importlib.util.find_spec('faster_whisper') is None:raise RuntimeError('install host requirements-speech-host.txt first')
        if any(not (Path(self.model_dir)/name).is_file() for name in ('model.bin','tokenizer.json','config.json')):
            raise ValueError('provide a complete local faster-whisper model: model.bin, tokenizer.json, config.json')
        if not shutil.which('espeak-ng'):raise RuntimeError('install espeak-ng and check espeak-ng --voices=cmn')
    def execute(self,kind,body):
        with tempfile.TemporaryDirectory(prefix='microduck-speech-') as d:
            directory=Path(d);inp=directory/('input.wav' if kind=='asr' else 'input.txt');out=directory/('result.json' if kind=='asr' else 'result.wav')
            if kind=='asr':
                object_keys(body,{'schema','audio_format','wav_base64'},'ASR request')
                raw=base64.b64decode(body['wav_base64'],validate=True);WavData.from_bytes(raw,gain=0.)
                inp.write_bytes(raw)
            else:
                object_keys(body,{'schema','audio_format','text'},'TTS request')
                text=body['text']
                if not isinstance(text,str) or not 1<=len(text)<=1000:raise ValueError('invalid speech text')
                inp.write_text(text,encoding='utf8')
            if body.get('schema')!=1 or body.get('audio_format')!='wav':raise ValueError('schema1 WAV required')
            command=[sys.executable,'-m','microduck_interaction.speech_worker',kind,str(inp),str(out),
                     '--model-dir',self.model_dir,'--voice',self.voice,'--language',self.language,'--threads',str(self.threads)]
            self._run_worker(command)
            if not out.is_file() or out.stat().st_size>MAX_WAV_BYTES:raise RuntimeError('speech backend output missing/oversize')
            raw=out.read_bytes()
            if kind=='asr':
                data=strict_json(raw);object_keys(data,{'text'},'ASR output')
                if not isinstance(data.get('text'),str) or not 1<=len(data['text'].strip())<=4000:raise ValueError('ASR output empty/invalid')
                return raw,'application/json'
            WavData.from_bytes(raw,gain=0.)
            return raw,'audio/wav'


def make_gateway(backend,token,host='127.0.0.1',port=8768):
    if not isinstance(token,str) or len(token)<24:raise ValueError('MICRODUCK_SPEECH_TOKEN must contain at least24 characters')
    if host!='127.0.0.1':raise ValueError('speech API binds127.0.0.1 only; use SSH forwarding or a TLS reverse proxy')
    busy=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):super().setup();self.connection.settimeout(2.)
        def log_message(self,*_):pass
        def reply(self,status,value,kind='application/json'):
            raw=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(401,{'error':'unauthorized'})
            if self.path not in ('/v1/asr','/v1/tts'):return self.reply(404,{'error':'unknown endpoint'})
            if not busy.acquire(blocking=False):return self.reply(503,{'error':'speech worker busy'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=12*1024*1024 or (self.path.endswith('tts') and size>16384):raise ValueError('body size refused')
                body=strict_json(self.rfile.read(size))
                raw,kind=backend.execute(self.path.rsplit('/',1)[1],body);self.reply(200,raw,kind)
            except (ValueError,KeyError,TypeError):self.reply(400,{'error':'invalid speech request/output'})
            except subprocess.TimeoutExpired:self.reply(504,{'error':'speech worker timed out; no result'})
            except (RuntimeError,subprocess.CalledProcessError,OSError):self.reply(503,{'error':'speech backend failed; check local installation/model'})
            finally:busy.release()
    server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True;return server


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model-dir',required=True)
    p.add_argument('--listen',choices=['127.0.0.1'],default='127.0.0.1');p.add_argument('--port',type=int,default=8768)
    p.add_argument('--voice',default='cmn');p.add_argument('--language',default='zh');p.add_argument('--threads',type=int,default=2)
    p.add_argument('--worker-timeout',type=float,default=12.)
    a=p.parse_args();backend=SpeechBackend(a.model_dir,a.voice,a.language,a.worker_timeout,a.threads);backend.check_dependencies()
    server=make_gateway(backend,os.environ.get('MICRODUCK_SPEECH_TOKEN',''),a.listen,a.port)
    print(json.dumps({'url':f'http://{a.listen}:{a.port}','asr':'faster-whisper/cpu/int8','tts':'espeak-ng/'+a.voice,'models_validated':False}),flush=True)
    def interrupt(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    try:server.serve_forever(poll_interval=.1)
    finally:backend.close();server.server_close()


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,KeyboardInterrupt) as exc:print('SPEECH GATEWAY STOPPED: '+str(exc),file=sys.stderr);sys.exit(2)
