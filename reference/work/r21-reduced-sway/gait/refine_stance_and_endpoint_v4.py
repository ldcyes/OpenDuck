"""Jointly refine the real stance family and support endpoint; nominal diagnostic."""
from reduced_core_v2 import *
SOURCES.bind(__file__)
seeddata=json.loads((OUT/'pitch_split_candidates_v2.json').read_text())
seedrow=min((r for r in seeddata['candidates']if r['endpoint']['numerically_feasible']),key=lambda r:abs(r['endpoint']['body_rpy_deg'][0]))
FV={}
for l in ['ankle_left','ankle_right']:
 vs=[]
 for r in A['items']:
  if r['link_frame']!=l:continue
  m=trimesh.load(SOURCES.bind(r['mesh'],r['mesh_sha256']),force='mesh');vs.append(np.array(m.vertices)@np.array(r['R']).T+r['t_mm'])
 FV[l]=np.vstack(vs)
def foot_group_Y_gap(stance):
 t={l:np.array(x)for l,x in stance['foot_target_transforms_mm'].items()};p={l:apply_points(V,t[l])for l,V in FV.items()};return float(p['ankle_left'][:,1].min()-p['ankle_right'][:,1].max())
ss=seedrow['stance'];x0=np.deg2rad([seedrow['endpoint']['q_HOME_delta_deg'][n]for n in LEGS]+[ss['toe_deg'],ss['bend_deg'],ss['hip_ankle_pitch_split_deg']]);memo={};start=time.time()
def ev(x):
 key=x.tobytes()
 if memo.get('key')!=key:
  st=make_stance(*np.rad2deg(x[10:]));e=evaluate(qdict(x[:10]),{l:np.array(t)for l,t in st['foot_target_transforms_mm'].items()},'ankle_left');e['gaps']=GUARD.gaps(e['q'],cap_mm=3.);e['initial_gaps']=GUARD.gaps(st['initial_q_HOME_delta_deg'],cap_mm=3.);e['foot_group_Y_gap_mm']=foot_group_Y_gap(st);e['stance']=st;memo.update(key=key,e=e)
 return memo['e']
def ine(x):
 e=ev(x);iq=np.deg2rad([e['stance']['initial_q_HOME_delta_deg'][n]for n in LEGS]);bb=np.array(BOUNDS)
 return np.r_[.85-np.array(list(e['static']['utilization'].values())),(e['static']['COP_margin_mm']-8)/100,(e['gaps']-2.3)/10,(e['initial_gaps']-2.31)/10,np.deg2rad([25,25,20])-e['rpy'],np.deg2rad([25,25,20])+e['rpy'],(e['foot_group_Y_gap_mm']-2.3)/100,iq-bb[:,0],bb[:,1]-iq]
def obj(x):
 e=ev(x);hy=e['head'][1]-e['stance']['initial_head_point_world_mm'][1];return (e['rpy'][0]/np.deg2rad(12))**2+.25*(e['rpy'][2]/np.deg2rad(12))**2+.5*(hy/100)**2+.03*(e['B'][1,3]/30)**2+.002*np.sum(x[:10]**2)
bb=BOUNDS+[(np.deg2rad(8),np.deg2rad(29.9)),(np.deg2rad(-40),np.deg2rad(25)),(np.deg2rad(-10),np.deg2rad(30))]
sol=minimize(obj,x0,method='SLSQP',bounds=bb,constraints=[dict(type='eq',fun=lambda x:ev(x)['eq']),dict(type='ineq',fun=ine)],options=dict(maxiter=100,ftol=1e-9));e=ev(sol.x);valid=bool(abs(e['eq']).max()<1e-6 and ine(sol.x).min()>=-1e-5)
out=dict(status='COUPLED_STANCE_AND_STATIC_ENDPOINT_CANDIDATE_NOT_A_GAIT',physical_approved=False,numerically_feasible=valid,solver_success=bool(sol.success),solver_message=sol.message,iterations=int(sol.nit),seconds=time.time()-start,stance=e['stance'],endpoint=dict(q_HOME_delta_deg=e['q'],base_transform_m=to_m(e['B']),body_rpy_deg=np.rad2deg(e['rpy']).tolist(),root_lateral_mm=float(e['B'][1,3]),head_lateral_from_stance_mm=float(e['head'][1]-e['stance']['initial_head_point_world_mm'][1]),head_point_world_mm=e['head'].tolist(),static=e['static'],guard_pairs=[list(p)for p in GUARD.pairs],guard_gaps_mm=e['gaps'].tolist(),closure_scaled_residual=float(abs(e['eq']).max()),minimum_inequality=float(ine(sol.x).min())),initial_guard_gaps_mm=e['initial_gaps'].tolist(),foot_groups_6parts_each_Y_separation_mm=e['foot_group_Y_gap_mm'],foot_guard_scope='Sufficient global Y-separating plane for both unions of all six actual source parts per foot, not a convexified material model. Guarantees a minimum gap when positive but may reject safe diagonally staggered parts.',numeric_joint_bounds_deg={n:np.rad2deg(b).tolist()for n,b in zip(LEGS,BOUNDS)},sources={**SOURCES.entries,**GUARD.sources.entries})
(OUT/'coupled_stance_endpoint_v4.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['sources']},ensure_ascii=False,indent=2),flush=True)
