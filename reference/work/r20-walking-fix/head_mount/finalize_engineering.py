"""Manufacturing information, nominal source-mass allocation and interface stack budget."""
from head_common import *
delta=load(OUT/'head_mount_delta.json');mass=load('work/r17-module-mount/mass_COM_update.json')
bind(__file__);bind(OUT/'head_common.py')
old={r['name']:r for r in mass['rows']};pool=old['head_fasteners_remaining_after_R13']
allocated=sum(p['mass_from_CAD_g'] for p in delta['parts'])
rows=[]
for p in delta['parts']:
    m=p['mass_from_CAD_g'];I=np.array(p['unit_density_inertia_mm5'])*p['density_assumption_g_cm3']*1e-12
    rows.append(dict(name=p['name'],link='jaw_soft',COM_home_mm=p['center_mm'],low_g=m*.8,nominal_g=m,high_g=m*1.2,
      category='R20 explicit purchased-fastener nominal geometry estimate',basis='Nominal smooth outer-thread / root-bore CAD volume at7.93g/cm3. Actual threads/chamfers/lotmass differ. ±20% masscases are declared sensitivity assumptions, not supplier tolerance.',
      measured=False,I_COM_home_kg_m2=I.tolist(),I_COM_home_per_kg_m2=(I/(m/1000)).tolist(),
      R13_inertia_basis='Uniform-density shape inertia scaled from this nominal fastener solid; excludes unmodeled thread flank distribution.',
      COM_uncertainty_halfwidth_HOME_mm=[.3,.15,.15] if '_stack_' in p['name'] else [.15,.15,.3],
      sources={p['step']:p['step_sha256'],p['mesh']:p['mesh_sha256']}))
newpool=copy.deepcopy(pool);newpool['name']='head_fasteners_remaining_after_R20'
for k in ['low_g','nominal_g','high_g']:newpool[k]=max(0,pool[k]-allocated)
newpool['basis']=pool['basis']+'; R20 now explicitly allocates the28CM4stack/frame fasteners at fixed nominalCADmass from each reserve case. Negative residual is prohibited; the old lowcase reserve is exhausted and the lower estimate is raised to the explicit newhardware lowcase.'
newpool['old_pool_name']=pool['name'];newpool['allocated_R20_nominal_g']=allocated;newpool['excluded_R20_items']=[r['name'] for r in rows]
newpool['I_COM_home_kg_m2']=(np.array(pool['I_COM_home_per_kg_m2'])*newpool['nominal_g']/1000).tolist()
newpool['COM_uncertainty_basis']=pool['COM_uncertainty_basis']+' Remaining unbuilt pieces keep the existing unmeasured center/containment assumptions.'
removed_rows=[old[n] for n in REMOVED]
cases={}
for k in ['low_g','nominal_g','high_g']:
    new_group=sum(r[k] for r in rows)+newpool[k]
    cases[k]=dict(old_head_fastener_pool_g=pool[k],fixed_nominal_allocation_g=allocated,new_explicit_hardware_g=sum(r[k] for r in rows),remaining_pool_g=newpool[k],
      new_group_g=new_group,group_delta_g=new_group-pool[k],removed_bars_g=sum(r[k] for r in removed_rows),whole_robot_delta_g=new_group-pool[k]-sum(r[k] for r in removed_rows))
assert abs(cases['nominal_g']['group_delta_g'])<1e-10
source_mass=load('work/r18-leg-hip-covers/legs/reference_design/candidate_v8/mount_candidate_manifest.json')
before=sum(r['nominal_g'] for r in mass['rows'])+sum(r['mass_from_CAD_g'] for r in source_mass['parts'])
assert abs(before-4194.478291462334)<1e-7
report=dict(status='CONDITIONAL_SOURCE_MASS_AND_INERTIA_DELTA_NO_DUPLICATE_RESERVE',physical_approved=False,measured=False,
 baseline_R17_mass_rows=441,retained_R18_new_cover_rows=34,before_nominal_kg=before/1000,
 after_nominal_kg=(before+cases['nominal_g']['whole_robot_delta_g'])/1000,after_mass_row_count=501,
 remove_mass_rows=REMOVED+[pool['name']],add_mass_rows=rows+[newpool],removed_bar_rows=removed_rows,
 board_representation_delta_g=0,case_accounting=cases,
 supplier_crosscheck=dict(product='AccuSSC-M2-22-A2',url='https://www.accu.co.uk/metric-cap-head-screws/10634-SSC-M2-22-A2',catalog_nominal_g_each=.53,
     modeled_g_each=next(r['nominal_g'] for r in rows if r['name']=='R20_CM4_stack_1_M2_screw'),
     interpretation='Catalog mass is lower than the smooth-outer-diameter reference. For consistency this delivery uses the declared conservativeCADestimate and reserves the hardware, not two simultaneous screw masses. Weigh selected production lots before replacing this estimate.'),
 limits=['These are conditional design mass and inertia cases; no physical measurement or validated uncertainty distribution.',
      'The lowreserve cannot pay the fixed nominalallocation. Its residual is zero; the explicit hardware lowcase sets a higherfastenergroup lower estimate, recorded numerically.',
      'The residual pool keeps its oldCOM/inertialcontainmentassumptions; no new internalpositions are invented.'],sources=SOURCES)
dump(OUT/'mass_inertia_delta.json',report)

stack=[('heatsink mounting ear',2,.05),('front PEEK',4,.05),('core PCB',1.2,.10),('B2B PEEK',1.5,.03),('carrier PCB',1.6,.16),('rear PEEK',5,.05),('rear cradle',2,.05),('front washer',.3,.05),('rear washer',.3,.05)]
nom=sum(t for _,t,_ in stack);emin=sum(t-tol for _,t,tol in stack);emax=sum(t+tol for _,t,tol in stack)
bolt=[21.7,22.3];nut=[1.5,1.6];tip=[bolt[0]-emax-nut[1],bolt[1]-emin-nut[0]]
stack_report=dict(status='DECLARED_MANUFACTURING_ACCEPTANCE_STACK_BUDGET_NOT_SUPPLIER_TOLERANCE_CERTIFICATE',
 unit='mm',layers=[dict(name=n,nominal_mm=t,accepted_half_range_mm=tol) for n,t,tol in stack],
 stack_excluding_nut_nominal_mm=nom,stack_excluding_nut_range_mm=[emin,emax],nut_accepted_height_range_mm=nut,
 bolt_order='M2x22DIN912/ISO4762,A2; diameter2,pitch0.4; minimum16mmthreadfromtip, partial6mmshankacceptable.',
 bolt_incoming_accepted_length_range_mm=bolt,nominal_tip_protrusion_mm=2.5,accepted_stack_tip_protrusion_range_mm=tip,
 bolt_minimum_thread_length_mm=16,maximum_possible_thread_start_distance_from_underhead_mm=bolt[1]-16,
 nut_minimum_full_form_engagement_requirement_mm=1.1,nut_maximum_combined_entry_exit_incomplete_thread_mm=.4,
 nut_minimum_full_form_threads=1.1/.4,
 M2x20_rejected_reason='With identical dimensional budget its worst-case tip projection is−0.39mm; the distal nut thread may not be fully reached.',
 foot=dict(bare_stack_mm=6,top_washer_mm=.5,nut_mm=2,bolt_mm=10,
     accepted_bare_stack_range_mm=[5.9,6.1],accepted_top_washer_range_mm=[.45,.55],accepted_nut_range_mm=[1.9,2],accepted_bolt_length_range_mm=[9.8,10.2],
     tip_protrusion_range_mm=[9.8-6.1-.55-2,10.2-5.9-.45-1.9],minimum_full_form_nut_engagement_mm=1.5),
 inspection=['Measure actual PCB thicknesses before assembly; the1.2±.10and1.6±.16acceptancebudgets are project assumptions, not manufacturer tolerance claims.',
     'Use a free-runningØ2.05pilot through the alignedM2stack andØ2.55pilotthrough theM2.5framejoint; no forced PCB bending or reaming of the suppliercore.',
     'Retain4.00±.05frontPEEK,1.50±.03B2BPEEKand5.00±.05rearPEEK; parallel ends≤.03. Do not compensate a wrongthermalpadgap by extra screwpreload.',
     'ScreenM2nuts to≥1.50overallheightand≥1.10full-formthreadland;M2.5nuts≥1.90heightand≥1.50land. Use gauges and lotdrawings, not the smooth referencebore.',
     'Verify actual rear screwtipclearance with measured stack; ≥0.5mm to every noncontactobject is an assembly acceptance floor, while2.2mm remains the nominalfree-motiondesigngoal.'],
 physical_approved=False,sources=SOURCES)
dump(OUT/'dimension_and_stack_budget.json',stack_report)
print('MASS',report['before_nominal_kg'],report['after_nominal_kg'],'STACK TIP',tip,flush=True)
