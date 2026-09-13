"""Measured state gates preserve the head-HOME assumption of static candidates.
The supported-double mode is a declared supported fixture/setup, not a contact sensor.
"""
import json,math,time
from pathlib import Path
from .contract import finite
from .motion_limits import limits_sha256
from .actuators import ROBOT_PROFILE
HEAD=tuple(range(5,10));LEGS=tuple(range(5))+tuple(range(10,15))
from .motion_limits import SUPPORT_CONTEXT_CONTRACT as CONTEXT_CONTRACT
class MotionContextGuard:
 def __init__(self,home,mode='head_home_locked',supported_confirmed=False):
  self.home=finite(home,15,'measured calibrated HOME');self.mode=mode
  if mode not in ('head_home_locked','supported_double'):raise ValueError('unknown motion context')
  if mode=='supported_double'and supported_confirmed is not True:raise ValueError('supported double mode requires actual support/setup confirmation')
  self.since=None;self.last=None;self.imu_sample=None;self.ready=False;self.active=False;self.head_stable=False
 def observe(self,q,dq,gyro,gravity,measured_s,now,imu_age):
  q=finite(q,15,'actual q');dq=finite(dq,15,'actual dq');gyro=finite(gyro,3,'actual gyro');gravity=finite(gravity,3,'actual gravity');finite([measured_s,now,imu_age],3,'actual sample time')
  if not 0<=now-measured_s<=.1 or not 0<=imu_age<=.1:raise RuntimeError('motion context measured state stale or future')
  if self.last is not None and measured_s<=self.last:raise RuntimeError('motion context sample reused or reordered')
  gap=self.last is not None and measured_s-self.last>.100000001;self.last=measured_s;self.imu_sample=measured_s-imu_age
  pos=CONTEXT_CONTRACT['position_tolerance_rad'];vel=CONTEXT_CONTRACT['velocity_tolerance_rad_s']
  near=lambda indices:all(abs(q[i]-self.home[i])<=pos and abs(dq[i])<=vel for i in indices)
  self.head_stable=near(HEAD)
  good=self.head_stable if self.mode=='head_home_locked' else near(LEGS)
  if not self.active:good=good and self.head_stable
  if self.mode=='supported_double':
   norm=math.sqrt(sum(x*x for x in gravity));good=good and .9<=norm<=1.1 and -gravity[2]/max(norm,1e-12)>=math.cos(math.radians(5)) and max(map(abs,gyro))<=.05
  if gap:good=False
  if not good:self.since=None;self.ready=False
  else:
   if self.since is None:self.since=measured_s
   self.ready=measured_s-self.since>=.5-1e-10
  if self.active and not self.ready:raise RuntimeError('motion context actual posture/velocity no longer satisfies locked support condition')
  return self.ready
 def require_fresh(self,now):
  finite([now],1,'current time')
  if self.last is None or self.imu_sample is None or not 0<=now-self.last<=.1 or not 0<=now-self.imu_sample<=.1:
   self.ready=False
   raise RuntimeError('motion context final actual HOME/IMU sample stale or future')
 def activate(self,now=None):
  if now is not None:self.require_fresh(now)
  if not self.ready:raise RuntimeError('stable actual HOME readback required before motion')
  self.active=True
 def validate_commands(self,commands,mouth):
  commands=finite(commands,13,'command');finite([mouth],1,'mouth')
  if self.mode=='head_home_locked':
   if any(commands[3:7])or mouth!=0:raise ValueError('head-home mode rejects head and mouth movement')
  elif any(commands[:3]+commands[7:]):raise ValueError('supported double interaction forbids leg/body/velocity commands')
 def filter_actions(self,actions,mouth):
  a=finite(actions,14,'policy action')
  slots=range(5,9)if self.mode=='head_home_locked'else tuple(range(5))+tuple(range(9,14))
  for i in slots:a[i]=0.
  return a,0. if self.mode=='head_home_locked'else mouth
 def status(self):return {'mode':self.mode,'ready':self.ready,'head_home_stable':self.ready and self.head_stable,'active':self.active,'stable_since_monotonic_s':self.since,'contact_automatically_proven':False}

def validate_live_frame(frame,state,calibration_sha,now):
 c=finite(frame.get('commands'),13,'command');mouth=finite([frame.get('mouth_rad')],1,'mouth')[0]
 # Zero lease is allowed for explicit arming/bootstrap, never an automatic keepalive.
 provenance=frame.get('vla_context')
 if not any(c)and mouth==0 and provenance is None:return
 if not isinstance(state,dict)or state.get('source')!='live_dynamixel_sflp'or state.get('robot_profile')!=ROBOT_PROFILE or state.get('calibration_sha256')!=calibration_sha or state.get('motion_limits_sha256')!=limits_sha256()or state.get('armed')is not True:raise ValueError('live executor needs matching actual armed runtime state')
 stamp=state.get('monotonic_s');finite([stamp,now],2,'telemetry time')
 if not 0<=now-stamp<=.1:raise ValueError('live runtime telemetry stale or future')
 ctx=state.get('motion_context',{})
 if provenance is not None:
  if provenance.get('calibration_sha256')!=calibration_sha or provenance.get('motion_limits_sha256')!=limits_sha256()or provenance.get('motion_context')!=ctx.get('mode'):raise ValueError('VLA observation differs from current runtime binding/context')
  if not provenance['capture_monotonic_s']<=now<provenance['deadline_monotonic_s']:raise ValueError('VLA observation expired')
 if ctx.get('ready')is not True:raise ValueError('runtime motion context not ready')
 if ctx.get('mode')=='head_home_locked':
  if ctx.get('head_home_stable')is not True or any(c[3:7])or mouth!=0:raise ValueError('head HOME stable lock forbids this interaction')
 elif ctx.get('mode')=='supported_double':
  if any(c[:3]+c[7:]):raise ValueError('supported double context forbids leg/body intent')
 else:raise ValueError('unknown runtime motion context')

def live_context_reader(path,calibration_sha,clock=time.monotonic):
 def check(frame):
  if not any(frame['commands'])and frame['mouth_rad']==0 and frame.get('vla_context')is None:return
  try:state=json.loads(Path(path).read_text())
  except (OSError,ValueError)as exc:raise ValueError('actual runtime telemetry unavailable')from exc
  validate_live_frame(frame,state,calibration_sha,clock())
 return check
