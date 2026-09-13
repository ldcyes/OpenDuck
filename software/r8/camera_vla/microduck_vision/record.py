"""Record real manual demonstrations; every episode starts unreviewed and is not training-ready."""
import argparse
import json
import os
import time
from pathlib import Path
from .client import LatestCamera
from .httpio import get
from .protocol import make_observation,number,PROFILE,limits_sha256,validate_intent_context

def demonstration_row(jpeg,telemetry,status,*,capture_s,now_s,sequence,task,rotation_deg=180):
    from microduck_interaction.schema import command_values,validate_intent
    if status.get('active_source')!='manual' or status.get('intent_active') is not True or status.get('dry_run') is not False or status.get('executor_healthy') is not True:
        raise ValueError('requires a healthy LIVE manual session, not an LLM/VLA/dry-run label')
    if telemetry.get('source')!='live_dynamixel_sflp':raise ValueError('requires actual runtime feedback')
    if status.get('robot_profile')!=PROFILE or status.get('motion_limits_sha256')!=limits_sha256():raise ValueError('executor identity mismatch')
    if not number(status.get('intent_deadline_monotonic_s'))or now_s>=status['intent_deadline_monotonic_s']:raise ValueError('manual intent expired')
    intent=validate_intent_context(status['intent'],telemetry['motion_context']['mode']);sent=telemetry.get('sent_commands')
    if not isinstance(sent,list) or len(sent)!=13 or not all(number(v) for v in sent):raise ValueError('missing commands sent to low-level policy')
    if any(abs(a-b)>1e-8 for a,b in zip(sent,command_values(intent))):raise ValueError('manual intent changed during observation; discard unsynchronized row')
    stamp=telemetry.get('sent_monotonic_s');origin=telemetry.get('source_command_monotonic_s')
    if not number(stamp) or not number(origin) or not 0<=now_s-stamp<=.1 or not 0<=stamp-origin<=.3:
        raise ValueError('sent command stale or unpaired')
    since=status.get('intent_since_monotonic_s')
    if not number(since)or origin<since:raise ValueError('sent command predates current manual intent')
    actual={'vx':sent[0],'vy':sent[1],'yaw':sent[2],'head':sent[3:7],'body':sent[9:12],'mouth':telemetry.get('sent_mouth_rad'),'duration_s':.2}
    actual=validate_intent_context(actual,telemetry['motion_context']['mode'])
    observation=make_observation(jpeg,telemetry,capture_s=capture_s,now_s=now_s,sequence=sequence,task=task,live=True,rotation_deg=rotation_deg)
    return {'teacher':'human_teleoperation','successful':False,'review_status':'UNREVIEWED','observation':observation,'executed_monotonic_s':stamp,'executed_intent':actual,
            'label_note':'high-level command sent by runtime; joint arrival is not asserted'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--pipeline',required=True);p.add_argument('--telemetry',required=True);p.add_argument('--task',required=True);p.add_argument('--seconds',type=float,default=10);p.add_argument('--output',required=True);p.add_argument('--local',default='http://127.0.0.1:8766');p.add_argument('--rotation',type=int,choices=[0,180],required=True);a=p.parse_args()
    if not .1<=a.seconds<=30:p.error('duration must be 0.1..30 seconds')
    camera=LatestCamera(a.pipeline,a.rotation);token=os.environ.get('MICRODUCK_LOCAL_TOKEN','');count=0;skipped=0
    try:
        start=time.monotonic()
        while camera.latest is None and time.monotonic()-start<2:time.sleep(.02)
        next_tick=time.monotonic();deadline=next_tick+a.seconds
        with Path(a.output).open('x',encoding='utf8') as f:
            while time.monotonic()<deadline:
                capture,jpeg=camera.get();telemetry=json.loads(Path(a.telemetry).read_text());status=get(a.local+'/v1/status',token,timeout=.08)
                try:
                    row=demonstration_row(jpeg,telemetry,status,capture_s=capture,now_s=time.monotonic(),sequence=count,task=a.task,rotation_deg=a.rotation)
                except ValueError:skipped+=1
                else:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');f.flush();count+=1
                next_tick+=.2;time.sleep(max(0,next_tick-time.monotonic()))
    finally:camera.close()
    print(json.dumps({'recorded':count,'skipped_unpaired':skipped,'review_status':'UNREVIEWED','training_ready':False}))
if __name__=='__main__':main()
