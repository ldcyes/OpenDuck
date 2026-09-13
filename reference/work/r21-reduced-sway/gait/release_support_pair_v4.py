"""Independently solve opposite support and gate the actual new start posture."""
from reduced_core_v2 import *
from feedforward_v2 import Feedforward
SOURCES.bind(__file__);V=SOURCES.json('work/r21-reduced-sway/gait/coupled_stance_endpoint_v4.json');stance=V['stance'];left=V['endpoint'];assert V['numerically_feasible']
initial_q=stance['initial_q_HOME_delta_deg'];initial_guard=GUARD.gaps(initial_q,cap_mm=3.)
FF=Feedforward(MP,CP);initial_static=FF.evaluate_dynamic(initial_q,stance['initial_base_transform_m'],['ankle_left','ankle_right'],desired_load_fraction_by_link={'ankle_left':.5,'ankle_right':.5})
assert min(initial_guard)>=2.3-1e-7 and initial_static['max_utilization']<=.85+1e-7
target=json.loads(json.dumps(stance));target['foot_target_transforms_mm']['ankle_right'][0][3]+=10
mirror=zero()
for n in LEGS:mirror[n]=-left['q_HOME_delta_deg'][('right_'if n.startswith('left_')else'left_')+n.split('_',1)[1]]
right=endpoint(target,mirror,support='ankle_right',roll_cap_deg=25.,head_side_cap_mm=150.,yaw_cap_deg=20.,maxiter=200)
out=dict(status='INITIAL_AND_INDEPENDENT_OPPOSITE_SUPPORT_CANDIDATE_NOT_A_GAIT',physical_approved=False,initial=dict(q_HOME_delta_deg=initial_q,base_transform_m=stance['initial_base_transform_m'],guard_pairs=GUARD.pairs,guard_gaps_mm=initial_guard.tolist(),double_support_static=initial_static),stance=stance,left_support_initial=left,right_support_after_right_10mm=right,right_targets=target['foot_target_transforms_mm'],both_endpoints_numerically_feasible=bool(right['numerically_feasible']),sources={**SOURCES.entries,**GUARD.sources.entries},limits=['Initial14-pair guard and true double-support gravity allocation checked; global557 review is separate.','Right support is independently solved with the right foot10mm forward, not accepted by mirror symmetry.','The two endpoints do not prove that their connection or swing motions are feasible.'])
(OUT/'support_pair_v4.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(initial_gap=float(min(initial_guard)),initial_util=initial_static['max_utilization'],right_numerically_feasible=right['numerically_feasible'],right_body_rpy=right['body_rpy_deg'],right_head=right['head_lateral_from_stance_mm'],right_static_util=right['static']['max_utilization'],right_COP=right['static']['COP_margin_mm'],right_min_gap=min(right['guard_gaps_mm']),right_q=right['q_HOME_delta_deg']),indent=2),flush=True)
