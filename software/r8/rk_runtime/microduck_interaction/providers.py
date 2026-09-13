"""Explicit HTTP gateways, with no required cloud vendor or model dependency."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from .audio import MAX_WAV_BYTES, WavData
from .schema import ROBOT_PROFILE, number, object_keys, strict_json, validate_plan


class ProviderError(RuntimeError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_):raise ProviderError('HTTP redirects refused; configure the final service URL')


def exchange(url,payload,key='',timeout=10.,max_bytes=65536,method='POST'):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ProviderError('configure an explicit http(s) endpoint without embedded credentials')
    headers={'Content-Type':'application/json','Accept':'application/json, audio/wav'}
    if key:headers['Authorization']='Bearer '+key
    data=None if payload is None else json.dumps(payload,allow_nan=False).encode()
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=timeout) as response:
            raw=response.read(max_bytes+1)
            if len(raw)>max_bytes:raise ProviderError('HTTP response exceeds configured byte limit')
            return raw,response.headers.get_content_type()
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        # Never echo Authorization, provider response bodies or URLs containing secrets.
        raise ProviderError('HTTP service failed or timed out; no model result accepted') from exc


from microduck_rk.motion_limits import HEAD_RANGES, MOUTH_MAX, limits_sha256
SYSTEM_PROMPT=f'''Return one JSON object with exactly robot_profile, say, intent. No markdown, shell, code, tools or joint targets.
robot_profile must be {ROBOT_PROFILE}. say is a string up to1000 characters.
intent requires duration_s in[0.02,3]; optional fields default tozero:
vx[-0.15,0.15]m/s,vy[-0.10,0.10]m/s,yaw[-0.5,0.5]rad/s;
head=[neck_pitch,head_pitch,head_yaw,head_roll] DELTA radians from measured HOME, inclusive [minimum, maximum] for each joint: {list(HEAD_RANGES)};
body=[z,roll,pitch] within[0.03m,0.15rad,0.15rad]absolute; mouth absolute radians[0,{MOUTH_MAX}], zero is closed.
Software limit contract SHA256 {limits_sha256()}; these caps do not certify combined poses or walking.
If uncertain, return zero movement. A model output never arms hardware.'''


class Providers:
    def __init__(self,llm_url=None,asr_url=None,tts_url=None,timeout=None,robot_profile=ROBOT_PROFILE):
        self.urls={k:v if v is not None else os.environ.get('MICRODUCK_'+k.upper()+'_URL','') for k,v in [('llm',llm_url),('asr',asr_url),('tts',tts_url)]}
        self.keys={k:os.environ.get('MICRODUCK_'+k.upper()+'_API_KEY','') for k in self.urls}
        self.timeout=number(float(timeout if timeout is not None else os.environ.get('MICRODUCK_PROVIDER_TIMEOUT','10')),'provider timeout',.05,15.)
        self.robot_profile=robot_profile
    def _call(self,kind,payload,max_bytes=65536):
        if not self.urls[kind]:raise ProviderError(f'MICRODUCK_{kind.upper()}_URL is not configured')
        return exchange(self.urls[kind],payload,self.keys[kind],self.timeout,max_bytes)
    def plan(self,text):
        if not isinstance(text,str) or not 1<=len(text.strip())<=4000:raise ValueError('input text must contain1..4000 characters')
        prompt=SYSTEM_PROMPT.replace(ROBOT_PROFILE,self.robot_profile)
        mode=os.environ.get('MICRODUCK_LLM_PROTOCOL','generic')
        if mode=='generic':payload={'schema':1,'robot_profile':self.robot_profile,'text':text,'system_prompt':prompt}
        elif mode=='chat-completions':
            model=os.environ.get('MICRODUCK_LLM_MODEL','')
            if not model:raise ProviderError('MICRODUCK_LLM_MODEL required for chat-completions')
            payload={'model':model,'stream':False,'messages':[{'role':'system','content':prompt},{'role':'user','content':text}],
                     'response_format':{'type':'json_object'},'temperature':0.,
                     'max_tokens':int(number(float(os.environ.get('MICRODUCK_LLM_MAX_TOKENS','256')),'LLM max_tokens',64,512))}
        else:raise ProviderError('unsupported LLM protocol')
        raw,_=self._call('llm',payload)
        try:
            data=strict_json(raw)
            if mode=='chat-completions':data=strict_json(data['choices'][0]['message']['content'])
            return validate_plan(data,self.robot_profile)
        except (ValueError,KeyError,IndexError,TypeError) as exc:raise ProviderError('LLM returned an invalid bounded plan; movement refused') from exc
    def transcribe(self,wav_bytes):
        WavData.from_bytes(wav_bytes,gain=0.)
        raw,_=self._call('asr',{'schema':1,'audio_format':'wav','wav_base64':base64.b64encode(wav_bytes).decode()})
        try:
            data=strict_json(raw);object_keys(data,{'text'},'ASR result');text=data['text']
            if not isinstance(text,str) or not 1<=len(text.strip())<=4000:raise ValueError('empty/oversize transcript')
            return text
        except (ValueError,KeyError,TypeError) as exc:raise ProviderError('ASR produced no valid text') from exc
    def synthesize(self,text):
        if not isinstance(text,str) or not 1<=len(text)<=1000:raise ValueError('TTS text must contain1..1000 characters')
        raw,kind=self._call('tts',{'schema':1,'text':text,'audio_format':'wav'},max_bytes=MAX_WAV_BYTES*2)
        try:
            if kind=='application/json':
                data=strict_json(raw);object_keys(data,{'wav_base64'},'TTS result');raw=base64.b64decode(data['wav_base64'],validate=True)
            elif kind not in ('audio/wav','audio/x-wav','audio/wave'):raise ValueError('TTS must return PCM WAV or JSON wav_base64')
            WavData.from_bytes(raw,gain=0.)
            return raw
        except (ValueError,KeyError,TypeError) as exc:raise ProviderError('TTS returned invalid WAV; playback refused') from exc
