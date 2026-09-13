"""One session arbiter and one atomic command-file owner. No servo imports."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid
from microduck_rk.motion_limits import MOUTH_MAX, validate_frame, limits_sha256
from .schema import ROBOT_PROFILE, command_values, number, validate_intent


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',delete=False) as f:
            name=f.name;os.chmod(name,0o600)
            json.dump(value,f,allow_nan=False,separators=(',',':'));f.write('\n')
        os.replace(name,path);name=None
    finally:
        if name:
            try:os.unlink(name)
            except FileNotFoundError:pass


class CommandWriter:
    def __init__(self,path):self.path=Path(path);self.lock=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=open(str(self.path)+'.lock','a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock.close();self.lock=None
            raise RuntimeError('another local command writer owns this command path')
        return self
    def write(self,frame):
        if self.lock is None:raise RuntimeError('command writer has no ownership lock')
        atomic_json(self.path,validate_frame(frame))
    def __exit__(self,*_):
        if self.lock:
            fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close();self.lock=None


class Arbiter:
    def __init__(self,clock=time.monotonic,robot_profile=ROBOT_PROFILE,mouth_closed=0.,mouth_open=.20,context_check=None):
        self.clock=clock;self.robot_profile=robot_profile;self.context_check=context_check
        self.closed=number(mouth_closed,'mouth_closed',0.,0.)
        self.opened=number(mouth_open,'mouth_open',self.closed,MOUTH_MAX)
        self.lock=threading.RLock();self.session=None;self.intent=None
        self.intent_since=0.;self.vla_context=None;self.intent_until=0.;self.audio=None;self.closing_until=0.;self.last_audio=False;self.audio_error=None
        self.close_grace=.8  # Bounded target-close window; physical closure is not guaranteed.
    def _valid(self,sid):
        if not self.session or sid!=self.session['session_id'] or self.clock()>=self.session['deadline']:
            raise ValueError('inactive or expired session; obtain a new local session')
        return self.session
    def start_session(self,source,duration_s=30.):
        if not isinstance(source,str) or not 1<=len(source)<=64:raise ValueError('source must be a 1..64 character label')
        duration_s=number(duration_s,'session duration_s',.1,30.)
        with self.lock:
            if self.session and self.clock()<self.session['deadline']:raise ValueError('session conflict: stop existing session before changing owner')
            self._clear();self.audio_error=None
            self.session={'session_id':uuid.uuid4().hex,'source':source,'deadline':self.clock()+duration_s,'sequence':-1}
            return {'session_id':self.session['session_id'],'expires_in_s':duration_s,'robot_profile':self.robot_profile}
    def submit(self,session_id,sequence,robot_profile,intent,vla_context=None):
        normalized=validate_intent(intent)
        if robot_profile!=self.robot_profile:raise ValueError('robot_profile mismatch')
        if isinstance(sequence,bool) or not isinstance(sequence,int) or not 0<=sequence<2**53:raise ValueError('sequence must be a nonnegative integer')
        with self.lock:
            s=self._valid(session_id)
            if sequence<=s['sequence']:raise ValueError('duplicate or reordered sequence')
            from .vla_context import validate_context
            if s['source']=='vla':
                if vla_context is None:raise ValueError('VLA requires original observation context')
                bound=validate_context(vla_context,self.clock(),normalized)
            else:
                if vla_context is not None:raise ValueError('VLA context requires a VLA session')
                bound=None
            if self.context_check:self.context_check({'commands':command_values(normalized),'mouth_rad':normalized['mouth'],'vla_context':bound})
            if bound:validate_context(bound,self.clock(),normalized)
            self._valid(session_id)
            s['sequence']=sequence;self.intent=normalized;self.vla_context=bound;self.intent_since=self.clock()
            self.intent_until=min(self.clock()+normalized['duration_s'],s['deadline'])
            if bound:self.intent_until=min(self.intent_until,bound['deadline_monotonic_s'])
            self.closing_until=min(self.intent_until+self.close_grace,s['deadline'])
            if bound:self.closing_until=min(self.closing_until,bound['deadline_monotonic_s'])
            return {'accepted':True,'sequence':sequence,'valid_for_s':self.intent_until-self.clock()}
    def attach_audio(self,session_id,sequence,playback):
        with self.lock:
            s=self._valid(session_id)
            if s['source']=='vla':raise ValueError('VLA session cannot extend observations with audio')
            if isinstance(sequence,bool) or not isinstance(sequence,int) or not s['sequence']<sequence<2**53:raise ValueError('duplicate or invalid audio sequence')
            if playback.duration+self.close_grace+.1>s['deadline']-self.clock():raise ValueError('audio would outlive session; obtain a fresh session first')
            if self.context_check:self.context_check({'commands':[0.]*13,'mouth_rad':self.opened})
            s['sequence']=sequence
            if self.audio:self.audio.cancel()
            self.audio=playback;self.audio_error=None;self.last_audio=True;playback.start()
    def _clear(self):
        if self.audio:self.audio.cancel()
        self.audio=None;self.intent=None;self.vla_context=None;self.last_audio=False;self.closing_until=0.
    def stop(self,session_id):
        with self.lock:
            self._valid(session_id);self._clear();self.session=None
    def shutdown(self):
        with self.lock:self._clear();self.session=None
    def active(self,session_id):
        with self.lock:
            try:self._valid(session_id);return True
            except ValueError:return False
    def status(self):
        with self.lock:
            now=self.clock();s=self.session
            return {'motion_limits_sha256':limits_sha256(),'robot_profile':self.robot_profile,'session_active':bool(s and now<s['deadline']),
                    'source':s['source'] if s and now<s['deadline'] else None,
                    'active_source':s['source'] if s and now<s['deadline'] else None,
                    'remaining_s':max(0.,s['deadline']-now) if s else 0.,
                    'intent_active':bool(s and now<s['deadline'] and self.intent and now<self.intent_until),
                    'intent':self.intent if s and now<s['deadline'] and now<self.intent_until else None,
                    'intent_since_monotonic_s':self.intent_since,
                    'intent_deadline_monotonic_s':self.intent_until,
                    'last_sequence':s['sequence'] if s else None,
                    'audio_playing':bool(self.audio and self.audio.alive(now)),
                    'last_audio_error':self.audio_error,
                    'close_grace_s':self.close_grace}
    def frame(self):
        with self.lock:
            now=self.clock()
            if not self.session or now>=self.session['deadline']:
                self._clear();return None
            live_intent=self.intent is not None and now<self.intent_until
            commands=command_values(self.intent) if live_intent else [0.]*13
            mouth=self.intent['mouth'] if live_intent else self.closed
            audio_live=False
            if self.audio:
                amplitude=self.audio.level(now)
                audio_live=self.audio.alive(now)
                if audio_live:
                    mouth=self.closed+(self.opened-self.closed)*amplitude
                    self.last_audio=True
                else:
                    self.audio_error=str(self.audio.error) if getattr(self.audio,'error',None) else self.audio_error
                    self.audio.cancel();self.audio=None
                    self.closing_until=min(now+self.close_grace,self.session['deadline'])
            # Playback and silence own the mouth for the entire utterance; old model mouth never resumes.
            if self.last_audio and not audio_live:mouth=self.closed
            if not (live_intent or audio_live or now<self.closing_until):return None
            frame={'monotonic_s':now,'commands':commands,'mouth_rad':mouth}
            if self.context_check:self.context_check({**frame,'vla_context':self.vla_context})
            return frame


class Executor:
    def __init__(self,arbiter,command_path,dry_run=True,dry_log=None,stop_file=None):
        self.arbiter=arbiter;self.command_path=command_path;self.dry_run=dry_run;self.dry_log=dry_log
        self.stop_file=stop_file;self.stop_event=threading.Event();self.error=None
        self.ready=threading.Event()
        self.thread=threading.Thread(target=self._run,daemon=True,name='intent-50hz')
    def start(self):
        self.thread.start()
        if not self.ready.wait(1.):raise RuntimeError('executor startup timeout')
        if self.error:raise RuntimeError(str(self.error))
    def _run(self):
        writer=None;log=None
        try:
            if not self.dry_run:writer=CommandWriter(self.command_path).__enter__()
            if self.dry_log:
                Path(self.dry_log).parent.mkdir(parents=True,exist_ok=True);log=open(self.dry_log,'a',buffering=1)
            self.ready.set();deadline=time.monotonic()
            while not self.stop_event.is_set():
                if self.stop_file and Path(self.stop_file).exists():raise RuntimeError('STOP file present; interaction lease renewal stopped')
                frame=self.arbiter.frame()
                if frame:
                    if writer:writer.write(frame)
                    if log:log.write(json.dumps({'dry_run':self.dry_run,**frame},allow_nan=False)+'\n')
                deadline+=.02
                if time.monotonic()>deadline+.04:raise RuntimeError('interaction loop missed freshness budget; command renewal stopped')
                self.stop_event.wait(max(0.,deadline-time.monotonic()))
        except Exception as exc:
            self.error=exc;self.arbiter.shutdown()
        finally:
            self.ready.set()
            if writer:writer.__exit__(None,None,None)
            if log:log.close()
    def close(self):
        self.stop_event.set();self.arbiter.shutdown()
        if self.thread.is_alive():self.thread.join(timeout=1.)
