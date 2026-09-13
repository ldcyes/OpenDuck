"""Recompute single-support gravity requirements against the final mass, without changing source gait."""
from quasistatic import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--contract',required=True);p.add_argument('--out',required=True);a=p.parse_args();ev=StaticEvaluator(ROOT/a.model,ROOT/a.contract);tp=OUT/'retimed_trajectory_4steps_v2.json';data=json.loads(tp.read_text());rows=[]
for s in data['keypoints']:
 if len(s['support_links'])!=1:continue
 r=ev.evaluate(s['q_HOME_delta_deg'],s['base_transform_m'],s['support_links'][0]);r.update(time_s=s['time_s'],phase=s['phase']);rows.append(r)
result=dict(status='FINAL_MASS_SINGLE_SUPPORT_GRAVITY_SCREEN',physical_approved=False,mass_kg=sum(ev.m.body_mass),sample_count=len(rows),maximum_utilization=max(r['max_utilization']for r in rows),minimum_COP_margin_mm=min(r['COP_margin_mm']for r in rows),worst_utilization_row=max(rows,key=lambda r:r['max_utilization']),rows=rows,sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [ev.model_path,ev.contract_path,tp,Path(__file__),OUT/'quasistatic.py']});Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print({k:result[k]for k in ['mass_kg','sample_count','maximum_utilization','minimum_COP_margin_mm']})
