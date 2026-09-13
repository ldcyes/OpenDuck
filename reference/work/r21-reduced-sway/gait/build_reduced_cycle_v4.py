"""Current rigid geometry, true two-step closed cycle with continuous translation."""
from reduced_core_v2 import *
SOURCES.bind(__file__)
from scipy.spatial import ConvexHull
sys.path.insert(0,str(ROOT/'work/r20-walking-fix/geometry'))
from collision_guard import LegBatteryGuard
RES=SOURCES.json('work/r21-reduced-sway/gait/support_pair_v4.json');assert RES['both_endpoints_numerically_feasible'];STANCE=RES['stance'];INIT=STANCE['initial_q_HOME_delta_deg'];BINIT=np.array(STANCE['initial_base_transform_m']);BINIT[:3,3]*=1000;TARGET0={l:np.array(t)for l,t in STANCE['foot_target_transforms_mm'].items()};L='ankle_left';R='ankle_right';CAP=.85;DTOL=np.deg2rad(1.3)
BOUNDS=[(-np.deg2rad(30),np.deg2rad(30))if 'yaw'in n else(-np.pi/4,np.pi/4)for n in LEGS]
source_left=RES['left_support_initial'];source_right=RES['right_support_after_right_10mm']
CHECKPOINT=SOURCES.json('work/r21-reduced-sway/gait/cycle_resume_checkpoint_v4.json');ALL=CHECKPOINT['keypoints'];LOG=[];assert len(ALL)==147;SOURCES.entries.update(CHECKPOINT['sources'])

def xq(q):return np.deg2rad([q[n]for n in LEGS])

def evaluate(q,targets,support):
 T=transforms(J,q);B=targets[support]@np.linalg.inv(T[support]);other=R if support==L else L;delta=np.linalg.inv(targets[other])@B@T[other];eq=np.r_[delta[:3,3]/100,Rotation.from_matrix(delta[:3,:3]).as_rotvec()];st=EV.evaluate(q,to_m(B),support);rp=Rotation.from_matrix(B[:3,:3]).as_euler('xyz');g=GUARD.gaps(q,cap_mm=5.)
 return dict(q=q,T=T,B=B,eq=eq,static=st,rpy=rp,gaps=g,head=head_point(B,T))

def solve(prev,seed,targets,support,ctarget=None,single=False,fixed=None):
 xx=xq(prev);seedx=xq(seed);memo={}
 def ev(x):
  key=x.tobytes()
  if key not in memo:memo[key]=evaluate(qdict(x),targets,support)
  return memo[key]
 def eq(x):
  e=ev(x);return np.r_[e['eq'],(np.array(e['static']['COM_world_m'])[:2]*1000-ctarget[:2])/100]if ctarget is not None else e['eq']
 def ine(x):
  e=ev(x);v=np.r_[np.deg2rad(25)-e['rpy'][:2],np.deg2rad(25)+e['rpy'][:2],(e['gaps']-2.3)/10]
  if single:v=np.r_[v,(e['static']['COP_margin_mm']-8)/100,CAP-np.array(list(e['static']['utilization'].values()))]
  return v
 bb=[(max(lo,p-DTOL),min(hi,p+DTOL))for p,(lo,hi)in zip(xx,BOUNDS)]
 def objective(x):
  e=ev(x);hy=e['head'][1]-STANCE['initial_head_point_world_mm'][1]
  return (e['rpy'][0]/np.deg2rad(12))**2+.25*(e['rpy'][2]/np.deg2rad(12))**2+.5*(hy/100)**2+.03*(e['B'][1,3]/30)**2+.003*np.sum((x-seedx)**2)+.03*np.sum((x-xx)**2)
 if fixed is not None:
  x=xq(fixed);success=True;msg='Exact pre-solved endpoint';iterations=0
 else:
  sol=minimize(objective,xx,method='SLSQP',bounds=bb,constraints=[dict(type='eq',fun=eq),dict(type='ineq',fun=ine)],options=dict(maxiter=50,ftol=5e-11));x=sol.x;success=bool(sol.success);msg=sol.message;iterations=int(sol.nit)
 e=ev(x);maxdq=float(np.rad2deg(np.max(abs(x-xx))));valid=bool(np.max(abs(eq(x)))<1e-6 and ine(x).min()>=-1e-5 and maxdq<=1.30001)
 other=R if support==L else L;err=np.max(np.linalg.norm(apply_points(feet[other]['sole'],e['B']@e['T'][other])-apply_points(feet[other]['sole'],targets[other]),axis=1))
 return e,dict(q_HOME_delta_deg=e['q'],base_transform_m=to_m(e['B']),support_link=support,foot_target_transforms_mm={l:t.tolist()for l,t in targets.items()},static_designated_support=e['static'],body_rpy_deg=np.rad2deg(e['rpy']).tolist(),head_point_world_mm=e['head'].tolist(),leg_battery_gaps_mm=e['gaps'].tolist(),max_foot_target_point_error_mm=float(err),target_COM_world_mm=ctarget.tolist()if ctarget is not None else None,solver_success=success,solver_message=msg,iterations=iterations,numerically_feasible=valid,closure_residual=float(np.max(abs(eq(x)))),minimum_inequality=float(ine(x).min()),maximum_from_previous_joint_delta_deg=maxdq)

def save_partial():
 (OUT/'reduced_cycle_keypoints_v4.json').write_text(json.dumps(dict(status='BUILDING_GUARDED_TRUE_STEP_CYCLE',physical_approved=False,keypoints=ALL,log=LOG,stance=STANCE,guard_sources=GUARD.sources.entries),ensure_ascii=False,indent=2)+'\n')

def record(row,phase,u,contacts,load,hold=0):
 row.update(phase=phase,phase_progress=u,contact_mode='double'if len(contacts)==2 else'left'if contacts==[L]else'right',support_links=contacts,desired_load_fraction_by_link=load,minimum_hold_s=hold);ALL.append(row);print(phase,round(u,4),row.get('numerically_feasible'), 'qstep',round(row.get('maximum_from_previous_joint_delta_deg',0),4),'ratio',round(row['static_designated_support']['max_utilization'],3),'gap',round(min(row['leg_battery_gaps_mm']),4),flush=True)
 if row.get('numerically_feasible')is False:save_partial();raise RuntimeError('FAILED '+phase+' '+str(u)+' '+str(row['solver_message']))

qprev=ALL[-1]['q_HOME_delta_deg'].copy();targets={l:np.array(t)for l,t in ALL[-1]['foot_target_transforms_mm'].items()}

def transfer(goal,support,phase,load0,load1,n=80):
 global qprev
 initial=INIT.copy()if phase=='double_transfer_to_left'else qprev.copy();e0=evaluate(initial,targets,support);eg=evaluate(goal,targets,support);c0=np.array(e0['static']['COM_world_m'])*1000;c1=np.array(eg['static']['COM_world_m'])*1000
 for i in range(21 if phase=='double_transfer_to_left'else 1,n+1):
  u=i/n;seed={k:(1-u)*initial[k]+u*goal[k]for k in names};ct=(1-u)*c0+u*c1;e,row=solve(qprev,seed,targets,support,ctarget=ct,fixed=goal if i==n else None);load={l:(1-u)*load0[l]+u*load1[l]for l in [L,R]};record(row,phase,u,[L,R],load);qprev=e['q'];
  if i%20==0:save_partial()

def hold(phase,support,load):
 e,row=solve(qprev,qprev,targets,support,fixed=qprev);record(row,phase,1,[L,R],load,hold=.6)

def step(support,phase):
 global qprev
 swing=R if support==L else L;orig=targets[swing].copy();prevprev=qprev.copy();seq=[('lift',0.,5*t)for t in np.linspace(1/20,1,20)]+[('advance',10*t,5.)for t in np.linspace(1/20,1,20)]+[('lower',10.,5*(1-t))for t in np.linspace(1/20,1,20)]
 for i,(sub,dx,dz)in enumerate(seq,1):
  targets[swing]=orig.copy();targets[swing][:3,3]+=np.array([dx,0,dz]);seed={n:qprev[n]+.7*(qprev[n]-prevprev[n])for n in names};e,row=solve(qprev,seed,targets,support,single=True);record(row,phase+'_'+sub,i/len(seq),[support],{support:1.,swing:0.});prevprev=qprev.copy();qprev=e['q']
  if i%20==0:save_partial()

def adaptive_transfer(goal,support,phase,load0,load1,n,initial=None,start_u=0.):
 global qprev
 initial=qprev.copy()if initial is None else initial;e0=evaluate(initial,targets,support);eg=evaluate(goal,targets,support);c0=np.array(e0['static']['COM_world_m'])*1000;c1=np.array(eg['static']['COM_world_m'])*1000;current_u=start_u
 def attempt(u,depth=0):
  nonlocal current_u
  global qprev
  seed={k:(1-u)*initial[k]+u*goal[k]for k in names};ct=(1-u)*c0+u*c1;e,row=solve(qprev,seed,targets,support,ctarget=ct,fixed=goal if abs(u-1)<1e-12 else None)
  if not row['numerically_feasible']:
   LOG.append(dict(status='REJECTED_NOT_APPENDED',phase=phase,from_u=current_u,target_u=u,depth=depth,diagnostic=row));print('SUBDIVIDE',phase,current_u,u,depth,row['closure_residual'],flush=True)
   if depth>=4:save_partial();raise RuntimeError('ADAPTIVE_TRANSFER_FAILED '+phase)
   attempt((current_u+u)/2,depth+1);attempt(u,depth+1);return
  load={l:(1-u)*load0[l]+u*load1[l]for l in [L,R]};record(row,phase,u,[L,R],load);qprev=e['q'];current_u=u;save_partial()
 for u in np.linspace(1/n,1,n):
  if u>start_u+1e-10:attempt(float(u))
startq=next(r['q_HOME_delta_deg']for r in ALL if r['phase']=='right_landing_still_unloaded')
adaptive_transfer(source_right['q_HOME_delta_deg'],R,'double_transfer_to_right',{L:1.,R:0.},{L:0.,R:1.},100,initial=startq,start_u=0.68);hold('pre_unload_left',R,{L:0.,R:1.});step(R,'left_step');hold('left_landing_still_unloaded',R,{L:0.,R:1.})
adaptive_transfer(INIT,R,'double_recenter',{L:0.,R:1.},{L:.5,R:.5},40);hold('cycle_end_center',R,{L:.5,R:.5})
assert max(abs(qprev[n]-INIT[n])for n in names)<1e-10
END=evaluate(qprev,targets,R);BEND=END['B'];assert np.max(abs(BEND[:3,:3]-BINIT[:3,:3]))<1e-8;assert np.linalg.norm(BEND[:3,3]-BINIT[:3,3]-[10,0,0])<1e-6
for l in feet:assert np.linalg.norm(targets[l][:3,3]-TARGET0[l][:3,3]-[10,0,0])<1e-8
report=dict(status='GUARDED_TWO_TRUE_STEPS_EXACT_CYCLE_CANDIDATE_NOT_APPROVED',physical_approved=False,geometry_approved=False,dynamic_approved=False,keypoints=ALL,stance=STANCE,cycle_end_minus_start_q_max_deg=0,cycle_translation_mm=[10,0,0],swing_lift_mm=5,each_foot_step_mm=10,single_support_static_utilization_cap=CAP,leg_battery_sampled_gap_requirement_mm=2.3,number_numerical_guard_pairs=14,maximum_keypoint_joint_delta_deg=max(r['maximum_from_previous_joint_delta_deg']for r in ALL),guard_sources=GUARD.sources.entries,sources={**SOURCES.entries,**GUARD.sources.entries},limits=['All actual 557 part pairs require independent review.','Static inverse dynamics and assigned contact load fractions do not prove dynamic balance.','Simulation starts from a checked prepared stance; autonomous HOME-to-stance foot repositioning is not yet implemented.','No independent foot narrowing was prescribed; actual 5DOF geometry and feet remain unchanged.','Each pair of q knots will use a shared quintic time scalar, not a spline. Between-knot closure must be explicitly checked.'])
(OUT/'reduced_cycle_keypoints_v4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('CYCLE_COMPLETE',len(ALL),flush=True)
