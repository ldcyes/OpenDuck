from reduced_core_v2 import *
import time,subprocess
SOURCES.bind(__file__)
for rel in ['work/r21-reduced-sway/gait/build_reduced_cycle_v2.py','work/r21-reduced-sway/gait/cycle_resume_checkpoint_v2.json','work/r21-reduced-sway/gait/build_reduced_cycle_v1.py','work/r21-reduced-sway/gait/support_pair_v4.json']:SOURCES.bind(rel)
p=OUT/'reduced_cycle_keypoints_v2.json';deadline=time.time()+3600
while time.time()<deadline:
 try:
  d=json.loads(p.read_text());k=d['keypoints'];end=next(i for i,r in enumerate(k)if r['phase']=='right_step_lower'and abs(r['phase_progress']-1)<1e-10);break
 except (OSError,ValueError,StopIteration):time.sleep(1.)
else:raise RuntimeError('No finished right step before deadline')
k=json.loads(json.dumps(k[:end+1]));hold=json.loads(json.dumps(k[-1]));hold.update(phase='right_landing_still_unloaded',phase_progress=1.,contact_mode='double',support_links=['ankle_left','ankle_right'],minimum_hold_s=.6,maximum_from_previous_joint_delta_deg=0.,solver_message='Exact landed pose held; same q, root and foot targets',iterations=0);k.append(hold)
f=OUT/'reduced_prefix_keypoints_v1.json';assert not f.exists();report=dict(status='FROZEN_TRUE_RIGHT_STEP_PREFIX_NOT_A_COMPLETE_GAIT',keypoints=k,stance=d['stance'],guard_sources=d['guard_sources'],sources={**SOURCES.entries,**d['guard_sources']},physical_approved=False,limits=['One true right step10mm only; not a four-step gait.','Ends with the same0.6s unloaded landing hold as full builder; no q/root reset.']);f.write_text(json.dumps(report,indent=2)+'\n');print('PREFIX_KEYPOINTS_READY',hashlib.sha256(f.read_bytes()).hexdigest(),flush=True)
subprocess.run([sys.executable,'-B',str(OUT/'export_reduced_v1.py'),'--prefix'],check=True,cwd=ROOT)
