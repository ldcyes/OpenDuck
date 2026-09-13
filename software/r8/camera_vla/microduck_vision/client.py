"""RK camera bridge. --live only submits validated high-level intents to the local executor."""
import argparse
import json
import os
import threading
import time
from pathlib import Path
from .protocol import PROFILE,ReplyGate,make_observation,submission_context,validate_state,validate_live_state,context_binding,validate_intent_context,validate_submission_state
from .httpio import post

class LatestCamera:
    def __init__(self,pipeline,rotation_deg=180):
        import cv2
        if rotation_deg not in (0,180):raise ValueError('rotation must be0 or180')
        self.rotation=rotation_deg
        self.cv2=cv2;self.cap=cv2.VideoCapture(pipeline,cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():raise RuntimeError('GStreamer camera pipeline did not open')
        self.lock=threading.Lock();self.latest=None;self.stop=threading.Event();self.worker=threading.Thread(target=self._read,daemon=True);self.worker.start()
    def _read(self):
        while not self.stop.is_set():
            ok,frame=self.cap.read();stamp=time.monotonic()
            if not ok:return
            if frame.shape[:2]!=(480,640):return
            if self.rotation==180:frame=self.cv2.rotate(frame,self.cv2.ROTATE_180)
            ok,jpeg=self.cv2.imencode('.jpg',frame,[self.cv2.IMWRITE_JPEG_QUALITY,75])
            if ok:
                with self.lock:self.latest=(stamp,jpeg.tobytes())
    def get(self):
        with self.lock:
            if self.latest is None:raise RuntimeError('no camera frame yet')
            return self.latest
    def close(self):
        self.stop.set();self.worker.join(timeout=.5)
        if not self.worker.is_alive():self.cap.release()

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='http://127.0.0.1:8767');p.add_argument('--local',default='http://127.0.0.1:8766')
    p.add_argument('--telemetry',required=True);p.add_argument('--task',required=True);p.add_argument('--pipeline',required=True)
    p.add_argument('--seconds',type=float,default=10);p.add_argument('--live',action='store_true');p.add_argument('--ca-file');p.add_argument('--report',default='vision-session.jsonl');p.add_argument('--rotation',type=int,choices=[0,180],required=True)
    a=p.parse_args()
    if not .1<=a.seconds<=30:p.error('session must be 0.1..30 seconds')
    from .httpio import loopback
    from urllib.parse import urlparse
    if not loopback(urlparse(a.local).hostname):p.error('executor must be on this RK host')
    token=os.environ.get('MICRODUCK_VLA_TOKEN','');local_token=os.environ.get('MICRODUCK_LOCAL_TOKEN','')
    camera=LatestCamera(a.pipeline,a.rotation);session=None;gate=ReplyGate();sequence=0
    try:
        start=time.monotonic()
        # Warm-up stays outside the control process. Never grants a motor lease.
        while camera.latest is None and time.monotonic()-start<2.:time.sleep(.02)
        if a.live:session=post(a.local+'/v1/sessions',{'source':'vla','duration_s':a.seconds},local_token)['session_id']
        deadline=time.monotonic()+a.seconds
        with Path(a.report).open('x',encoding='utf8') as log:
            while time.monotonic()<deadline:
                cycle_start=time.monotonic()
                capture,jpeg=camera.get();state=json.loads(Path(a.telemetry).read_text())
                observation=make_observation(jpeg,state,capture_s=capture,now_s=time.monotonic(),sequence=sequence,task=a.task,live=a.live,rotation_deg=a.rotation)
                reply=post(a.host+'/v1/observe',observation,token,timeout=.65,cafile=a.ca_file)
                plan=gate.accept(observation,reply,time.monotonic())
                if time.monotonic()>=deadline:raise ValueError('session expired during inference')
                if session:
                    latest=json.loads(Path(a.telemetry).read_text())
                    validate_submission_state(observation,plan,latest,time.monotonic())
                    # Server results never select the session, robot profile, sequence or a shell command.
                    post(a.local+'/v1/intents',{'session_id':session,'sequence':sequence,'robot_profile':PROFILE,'intent':plan['intent'],'vla_context':submission_context(observation,gate.max_age_s)},local_token,timeout=.15)
                log.write(json.dumps({'sequence':sequence,'capture_monotonic_s':capture,'received_monotonic_s':time.monotonic(),'dry_run':not a.live,'plan':plan},ensure_ascii=False)+'\n');log.flush()
                sequence+=1
                time.sleep(max(0.,.2-(time.monotonic()-cycle_start)))
    finally:
        if session:
            try:post(a.local+'/v1/stop',{'session_id':session},local_token,timeout=.2)
            except Exception:pass # Existing executor intent/session expiry still applies.
        camera.close()
if __name__=='__main__':main()
