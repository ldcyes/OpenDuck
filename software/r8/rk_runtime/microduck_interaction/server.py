"""Authenticated local transport to the single Arbiter. No model/network work in its tick."""
import base64
import hmac
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .audio import DEFAULT_DEVICE,Playback,WavData
from .schema import object_keys,strict_json


def make_server(arbiter,host='127.0.0.1',port=8766,token='',dry_run=True,device=DEFAULT_DEVICE,gain=.2,executor=None,audio_dry_run=None):
    audio_dry_run=dry_run if audio_dry_run is None else audio_dry_run
    if not isinstance(token,str) or len(token)<24:raise ValueError('MICRODUCK_LOCAL_TOKEN must contain at least24 characters')
    if host!='127.0.0.1':raise ValueError('local API binds127.0.0.1 only; use an authenticated tunnel for remote administration')
    class Handler(BaseHTTPRequestHandler):
        def setup(self):super().setup();self.connection.settimeout(2.)
        def log_message(self,*_):pass
        def reply(self,code,data):
            raw=json.dumps(data,allow_nan=False).encode();self.send_response(code)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def auth(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                self.reply(401,{'error':'unauthorized'});return False
            return True
        def do_GET(self):
            if not self.auth():return
            if self.path!='/v1/status':self.reply(404,{'error':'unknown endpoint'});return
            self.reply(200,{**arbiter.status(),'dry_run':dry_run,'audio_dry_run':audio_dry_run,'executor_healthy':executor is None or executor.error is None})
        def do_POST(self):
            if not self.auth():return
            try:
                if executor and executor.error and self.path!='/v1/stop':raise RuntimeError('executor stopped; no new leases accepted')
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=12*1024*1024:raise ValueError('request byte limit exceeded or missing length')
                if self.path!='/v1/audio' and n>16384:raise ValueError('control JSON limit exceeded')
                body=strict_json(self.rfile.read(n))
                if self.path=='/v1/sessions':
                    object_keys(body,{'source','duration_s'},'session request')
                    result=arbiter.start_session(body.get('source'),body.get('duration_s',30.))
                elif self.path=='/v1/intents':
                    object_keys(body,{'session_id','sequence','robot_profile','intent','vla_context'},'intent request')
                    result=arbiter.submit(body.get('session_id'),body.get('sequence'),body.get('robot_profile'),body.get('intent'),vla_context=body.get('vla_context'))
                elif self.path=='/v1/stop':
                    object_keys(body,{'session_id'},'stop request');arbiter.stop(body.get('session_id'));result={'stopped':True,'lease_renewal':False}
                elif self.path=='/v1/audio':
                    object_keys(body,{'session_id','sequence','robot_profile','wav_base64'},'audio request')
                    if body.get('robot_profile')!=arbiter.robot_profile:raise ValueError('robot_profile mismatch')
                    raw=base64.b64decode(body.get('wav_base64',''),validate=True)
                    data=WavData.from_bytes(raw,gain=gain);p=Playback(data,device=device,dry_run=audio_dry_run)
                    arbiter.attach_audio(body.get('session_id'),body.get('sequence'),p)
                    result={'accepted':True,'duration_s':p.duration,'dry_run':audio_dry_run}
                else:self.reply(404,{'error':'unknown endpoint'});return
                self.reply(200,result)
            except (ValueError,KeyError,TypeError) as exc:self.reply(409 if 'conflict' in str(exc) else 400,{'error':str(exc)})
            except RuntimeError as exc:self.reply(503,{'error':str(exc)})
            except (TimeoutError,OSError):
                # A disconnected client cannot renew leases; existing intents still expire independently.
                return
    server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True
    return server
