"""ALSA subprocesses and the envelope of the PCM actually queued for playback.

The timestamp is a software queue timestamp, not a DAC measurement. 40ms ALSA
buffering and physical lip/audio offset must be verified on the target board.
"""
import array
import io
import math
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from .schema import number

DEFAULT_DEVICE='plughw:CARD=MicroduckAudio,DEV=0'
MAX_WAV_BYTES=8*1024*1024


class WavData:
    @classmethod
    def from_bytes(cls,raw,gain=.2):
        gain=number(gain,'playback gain',0.,.25)
        if not isinstance(raw,bytes) or len(raw)>MAX_WAV_BYTES:raise ValueError('WAV byte limit exceeded')
        try:
            with wave.open(io.BytesIO(raw),'rb') as w:
                channels,width,rate,frames=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
                if w.getcomptype()!='NONE' or channels not in (1,2) or width not in (2,4) or rate not in (8000,16000,22050,24000,32000,44100,48000) or not 0<frames/rate<=20:
                    raise ValueError('require PCM16/32 mono/stereo WAV, 8..48kHz and 0..20 seconds')
                pcm=w.readframes(frames)
                if len(pcm)!=frames*channels*width:raise ValueError('truncated WAV data')
        except (wave.Error,EOFError,OSError) as exc:raise ValueError('invalid PCM WAV') from exc
        source=array.array('h' if width==2 else 'i');source.frombytes(pcm)
        if sys.byteorder!='little':source.byteswap()
        mono=array.array('h')
        for i in range(0,len(source),channels):
            value=sum(source[i:i+channels])/channels
            if width==4:value/=65536
            mono.append(round(value*gain))
        if sys.byteorder!='little':mono.byteswap()
        # Only upsampling: linear interpolation, no automatic gain or normalization.
        # Always request the shared I2S clock at48kHz, including16kHz TTS input.
        if rate!=48000:
            if sys.byteorder!='little':mono.byteswap()
            count=round(len(mono)*48000/rate);upsampled=array.array('h')
            for i in range(count):
                pos=i*rate/48000;left=min(int(pos),len(mono)-1);right=min(left+1,len(mono)-1)
                upsampled.append(round(mono[left]+(mono[right]-mono[left])*(pos-left)))
            mono=upsampled
            if sys.byteorder!='little':mono.byteswap()
        rate=48000
        obj=cls();obj.rate=rate;obj.pcm=mono.tobytes();obj.duration=len(obj.pcm)/(2*rate)
        size=round(rate*.02)*2;obj.chunks=[obj.pcm[i:i+size] for i in range(0,len(obj.pcm),size)]
        obj.levels=[]
        for chunk in obj.chunks:
            values=array.array('h');values.frombytes(chunk)
            if sys.byteorder!='little':values.byteswap()
            rms=math.sqrt(sum(v*v for v in values)/len(values))/32768
            obj.levels.append(0. if rms<.005 else min(1.,rms/.15))
        return obj


class Playback:
    def __init__(self,data,device=DEFAULT_DEVICE,dry_run=True):
        self.data=data;self.duration=data.duration;self.device=device;self.dry_run=dry_run
        self.stop_event=threading.Event();self.proc=None;self.error=None
        self._level=0.;self._stamp=0.;self._started_at=None;self._running=False
        self.thread=threading.Thread(target=self._run,daemon=True,name='wav-playback')
    def start(self):
        self._started_at=time.monotonic();self._running=True;self.thread.start()
    def alive(self,now):
        return bool(self._running and not self.stop_event.is_set() and self._started_at is not None and
                    now-self._started_at<=self.duration+.3 and (self.proc is None or self.proc.poll() is None))
    def level(self,now):
        return self._level if self.alive(now) and 0<=now-self._stamp<=.06 else 0.
    def cancel(self):
        self.stop_event.set();self._level=0.;self._running=False
        if self.proc and self.proc.poll() is None:
            try:self.proc.terminate()
            except ProcessLookupError:pass
    def _run(self):
        try:
            if not self.dry_run:
                self.proc=subprocess.Popen(['aplay','-q','-D',self.device,'-t','raw','-f','S32_LE','-r','48000','-c','2',
                                            '--buffer-time=40000','--period-time=20000'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                os.set_blocking(self.proc.stdin.fileno(),False)
            next_tick=time.monotonic()
            for chunk,level in zip(self.data.chunks,self.data.levels):
                if self.stop_event.wait(max(0.,next_tick-time.monotonic())):break
                if self.proc:
                    if self.proc.poll() is not None:raise RuntimeError('ALSA playback exited')
                    samples=array.array('h');samples.frombytes(chunk)
                    if sys.byteorder!='little':samples.byteswap()
                    stereo=array.array('i',(v<<16 for sample in samples for v in (sample,sample)))
                    if sys.byteorder!='little':stereo.byteswap()
                    remaining=memoryview(stereo.tobytes());deadline=time.monotonic()+.05
                    while remaining:
                        if self.stop_event.is_set():return
                        if time.monotonic()>deadline:raise RuntimeError('ALSA queue stalled; stale mouth motion refused')
                        if not select.select([],[self.proc.stdin],[],.01)[1]:continue
                        try:n=os.write(self.proc.stdin.fileno(),remaining)
                        except BlockingIOError:continue
                        remaining=remaining[n:]
                self._level=level;self._stamp=time.monotonic();next_tick+=len(chunk)/(2*self.data.rate)
                if time.monotonic()>next_tick+.04:raise RuntimeError('playback scheduler missed freshness budget')
            self.stop_event.wait(max(0.,next_tick-time.monotonic()))
            if self.proc and not self.stop_event.is_set():
                self.proc.stdin.close()
                try:self.proc.wait(timeout=.3)
                except subprocess.TimeoutExpired:raise RuntimeError('ALSA did not drain on time')
                if self.proc.returncode:raise RuntimeError('ALSA returned a playback error')
        except Exception as exc:self.error=exc
        finally:
            self.cancel()
            if self.proc:
                try:self.proc.wait(timeout=.3)
                except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=.3)
                if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()


def capture_push_to_talk(path,device=DEFAULT_DEVICE,max_seconds=10.,input_fn=input):
    """Press Enter to begin; Enter to finish, with an independent ten-second cap.

    I2S contract: 48kHz S32_LE stereo slots, microphone in the left slot.
    A plughw device may perform format conversion; inspect the actual ALSA card.
    """
    max_seconds=number(max_seconds,'record max_seconds',.1,10.)
    input_fn('按回车开始录音；再次回车结束（最多10秒）：')
    with tempfile.TemporaryDirectory(prefix='microduck-record-') as d:
        raw=Path(d)/'capture.wav'
        proc=subprocess.Popen(['arecord','-q','-D',device,'-t','wav','-f','S32_LE','-r','48000','-c','2',str(raw)],
                              stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        done=threading.Event()
        def key():
            try:input_fn('录音中，回车结束：')
            except (EOFError,KeyboardInterrupt):pass
            finally:done.set()
        threading.Thread(target=key,daemon=True).start()
        deadline=time.monotonic()+max_seconds
        try:
            while not done.wait(.02) and time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('ALSA capture exited early')
        finally:
            if proc.poll() is None:proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=.5)
        if not raw.exists():raise RuntimeError('ALSA produced no recording')
        try:
            with wave.open(str(raw),'rb') as w:
                if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(2,4,48000):raise ValueError('recording format differs from I2S contract')
                pcm=w.readframes(w.getnframes())
            samples=array.array('i');samples.frombytes(pcm)
            if sys.byteorder!='little':samples.byteswap()
            left=array.array('h',(max(-32768,min(32767,v>>16)) for v in samples[::2]))
            if not left:raise ValueError('empty recording')
            if sys.byteorder!='little':left.byteswap()
            with wave.open(str(path),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(left.tobytes())
        except (wave.Error,EOFError) as exc:raise RuntimeError('invalid ALSA recording') from exc
    return Path(path)
