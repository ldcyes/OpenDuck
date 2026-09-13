from pathlib import Path
import json,math,hashlib
R=Path(__file__).parent;V=R/'verification';out={}
rows=[];boardrows={}
for label in ['source','r22']:
 fine=json.loads((V/f'dc_sheet_{label}_fine_power.json').read_text());ground=json.loads((V/f'dc_sheet_{label}_0.075.json').read_text())[4:]
 chosen=[q for q in fine if q['grid_mm']==.025]+ground;boardrows[label]=chosen
for i,q in enumerate(boardrows['r22']):
 src=boardrows['source'][i];rows.append(dict(net=q['net'],from_pins=q['from_pins'],to_pins=q['to_pins'],source_R20_mOhm=src['R20_mOhm'],r22_R20_mOhm=q['R20_mOhm'],source_R85_mOhm=src['R85_mOhm'],r22_R85_mOhm=q['R85_mOhm'],change_percent=(q['R20_mOhm']/src['R20_mOhm']-1)*100))
loops=[]
for kind,inds in [('MOBILE',[1,3,4]),('BENCH',[2,3,5])]:
 q=dict(mode=kind)
 for label in ['source','r22']:
  rr=sum(boardrows[label][i]['R20_mOhm']for i in inds);q[label+'_R20_mOhm']=rr;q[label+'_R85_mOhm']=rr*(1+.00393*65)
 q['change_percent']=(q['r22_R20_mOhm']/q['source_R20_mOhm']-1)*100;loops.append(q)
module25=.98*(1+4.1*.999/1.001);module105=.98*(1+4.1*.997/1.003)
voltage=[]
for current in [2.7,3.0]:
 for loop in loops:
  r105=loop['r22_R20_mOhm']*(1+.00393*85)/.8*1.05/1000
  pcb=current*r105;mux=current*.033;minimum=module105-pcb-mux
  voltage.append(dict(mode=loop['mode'],current_A=current,copper_temp_C=105,copper_cross_section_fraction=.8,numerical_model_allowance=1.05,mux_max_Ohm=.033,PCB_loop_drop_V=pcb,mux_drop_V=mux,module_min_with_tolerance_and_TCR_V=module105 if loop['mode']=='MOBILE'else None,at_W7_W8_before_ripple_harness_V=minimum if loop['mode']=='MOBILE'else None,bench_required_at_W5_W6_for_4p75V_out_before_ripple_harness_V=4.75+pcb+mux if loop['mode']=='BENCH'else None,remaining_to_4p75_V=minimum-4.75 if loop['mode']=='MOBILE'else None,conditional_ripple_pp_budget_V=.050,conditional_dynamic_extra_droop_budget_V=.020,max_external_loop_R_if_budgets_met_mOhm=(minimum-4.75-.025-.020)/current*1000 if loop['mode']=='MOBILE'else None))
convergence=[]
for label in['source','r22']:
 f=json.loads((V/f'dc_sheet_{label}_fine_power.json').read_text())
 for a,b in zip(f[::2],f[1::2]):convergence.append(dict(board=label,net=a['net'],coarse_grid_mm=.05,fine_grid_mm=.025,coarse_R20_mOhm=a['R20_mOhm'],fine_R20_mOhm=b['R20_mOhm'],relative_difference_percent=abs(a['R20_mOhm']/b['R20_mOhm']-1)*100))
 a=json.loads((V/f'dc_sheet_{label}_0.1.json').read_text())[4:];b=json.loads((V/f'dc_sheet_{label}_0.075.json').read_text())[4:]
 for aa,bb in zip(a,b):convergence.append(dict(board=label,net='GND',to_pins=aa['to_pins'],coarse_grid_mm=.1,fine_grid_mm=.075,coarse_R20_mOhm=aa['R20_mOhm'],fine_R20_mOhm=bb['R20_mOhm'],relative_difference_percent=abs(aa['R20_mOhm']/bb['R20_mOhm']-1)*100))
report=dict(status='DESIGN REVIEW CANDIDATE; NOT HARDWARE OR MANUFACTURING QUALIFIED',method=dict(copper='Union of native filled zones, actual pad polygons, trace widths and via annuli. 2D sheet networks connected by 32 distributed barrel sectors.',rho20_Ohm_mm=1.7241e-5,temp_coefficient_per_K=.00393,plating_minimum_assumed_mm=.025,source_copper_mm=[.07,.07],r22_copper_mm=[.07,.035,.035,.07],terminals='All cells within named source/target pads held at1V/0V;ideal solder/contact;PTH terminal pads ideal on all copper layers. No wire/contact resistance included.',ground='W8 to PGND14/15/18 for mobile;W8 to W6 for bench;existing high-current battery-return sharing is not modeled as a simultaneous injection.',limits='Grid comparison and analytic checks validate the numerical method only. Etch, copper/plating tolerance, thermoelectric effects, thermal gradients, vias-in-pad assembly, feedback sense error and dynamic output require hardware validation.'),pin_path_comparison=rows,complete_board_loop_comparison=loops,grid_convergence=convergence,regulator=dict(nominal_V=5.1,VFB_full_temperature_min_V=.98,RFBT_Ohm=41000,RFBB_Ohm=10000,resistor_initial_tolerance=.001,resistor_TCR_max_ppm_K=25,TCR_temperature_excursion_K=80,VFB_full_temperature_min_with_initial_resistor_tolerance_V=module25,divider_min_including_worst_independent_TCR_V=module105,ripple_typical_pp_V=.010,ripple_max_V=None,load_regulation_typical_percent=.04,load_regulation_max_percent=None,warning='Ripple and load regulation are typical-only datasheet values. The quoted divider lower bound is not a guaranteed all-load instantaneous output minimum.'),TPS2117=dict(Ron_max_25C_Ohm=.025,Ron_max_85C_Ohm=.031,Ron_max_105C_Ohm=.033,conditions='VIN=5V or3.3V;datasheet characterization at200mA;current/thermal and transient behavior require bench validation.'),conditional_voltage_scenarios=voltage,primary_sources=['https://www.ti.com/lit/ds/symlink/lmzm33603.pdf','https://www.ti.com/lit/ds/symlink/tps2117.pdf','https://www.yageogroup.com/component-documentation/download/specsheet/RT0603BRD0710KL','https://yageogroup.com/content/datasheet/asset/file/PYU-RT_1-TO-0-01_ROHS_L'],file_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in[R/'Microduck_Entry_5V_R22.kicad_pcb',V/'source_dc_geometry.json',V/'r22_dc_geometry.json',R/'solve_dc_copper.py']})
(V/'DC_New_vs_Source_Final.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(loops=loops,voltage=voltage),indent=2))
