"""Bounded authenticated JSON transport; remote links require TLS."""
import ipaddress
import json
import ssl
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

def loopback(host):
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirects forbidden for credentialed robot API')

def request_json(url,body,token,timeout=1.,cafile=None,method="POST"):
    p=urlparse(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment:
        raise ValueError('invalid endpoint')
    if p.scheme!='https' and not loopback(p.hostname):raise ValueError('remote endpoint requires HTTPS or an SSH localhost tunnel')
    if not token or any(c in token for c in '\r\n'):raise ValueError('missing/invalid API token')
    raw=json.dumps(body,allow_nan=False,ensure_ascii=False).encode() if body is not None else None
    if raw is not None and len(raw)>900_000:raise ValueError('request too large')
    opener=build_opener(NoRedirect(),HTTPSHandler(context=ssl.create_default_context(cafile=cafile)))
    req=Request(url,data=raw,headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method=method)
    with opener.open(req,timeout=timeout) as r:
        data=r.read(900_001)
        if len(data)>900_000:raise ValueError('response too large')
        from microduck_interaction.schema import strict_json
        return strict_json(data)

def post(url,body,token,timeout=1.,cafile=None):
    return request_json(url,body,token,timeout,cafile)

def get(url,token,timeout=1.,cafile=None):
    return request_json(url,None,token,timeout,cafile,method="GET")
