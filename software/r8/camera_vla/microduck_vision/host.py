"""Workstation service. Default mock mode tests transport only; it rejects live input."""
import argparse
import hmac
import json
import os
import ssl
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .protocol import PROFILE, validate_observation,context_binding
from .httpio import loopback

class MockPolicy:
    def infer(self,o):
        if not o['simulated']:raise ValueError('mock policy refuses live robot observations')
        return {'robot_profile':PROFILE,'say':'','intent':{'vx':0.,'duration_s':.2}}

def make_server(address,token,backend):
    if not token:raise ValueError('VLA token required')
    lock=threading.Lock(); seen=set()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,code,data):
            raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_POST(self):
            self.connection.settimeout(2.)
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(401,{'error':'unauthorized'})
            if self.path!='/v1/observe':return self.reply(404,{'error':'unknown endpoint'})
            if not lock.acquire(blocking=False):return self.reply(503,{'error':'inference busy; do not queue stale frames'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=900000:raise ValueError('invalid body length')
                raw=self.rfile.read(n)
                if len(raw)!=n:raise ValueError('incomplete body')
                from microduck_interaction.schema import strict_json
                o=strict_json(raw); validate_observation(o)
                if o['request_id'] in seen:raise ValueError('duplicate request')
                seen.add(o['request_id'])
                if len(seen)>4096:seen.clear();seen.add(o['request_id'])
                plan=backend.infer(o)
                self.reply(200,{'schema':1,'request_id':o['request_id'],'sequence':o['sequence'],'robot_profile':PROFILE,**context_binding(o['state']),'plan':plan})
            except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.reply(400,{'error':str(e)[:240]})
            except Exception:self.reply(503,{'error':'backend unavailable; inspect workstation logs'})
            finally:lock.release()
    return ThreadingHTTPServer(address,Handler)

def main():
    p=argparse.ArgumentParser();p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=8767)
    p.add_argument('--backend',choices=['mock','smolvla'],default='mock');p.add_argument('--manifest');p.add_argument('--cert');p.add_argument('--key')
    a=p.parse_args()
    if not loopback(a.bind) and not (a.cert and a.key):p.error('non-loopback binding requires TLS certificate and key')
    if a.backend=='smolvla':
        if not a.manifest:p.error('--manifest required')
        from .smolvla_adapter import SmolVLAAdapter
        backend=SmolVLAAdapter(a.manifest)
    else:backend=MockPolicy()
    server=make_server((a.bind,a.port),os.environ.get('MICRODUCK_VLA_TOKEN',''),backend)
    if a.cert:
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(a.cert,a.key);server.socket=ctx.wrap_socket(server.socket,server_side=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
