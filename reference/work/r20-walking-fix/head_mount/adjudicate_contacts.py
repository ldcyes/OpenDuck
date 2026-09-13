"""Explain each raw positive with named source material/nominal thread evidence."""
from head_common import *
delta=load(OUT/'head_mount_delta.json');raw=load(OUT/'raw_full_assembly_HOME.json');interface=load(OUT/'interface_audit.json')
bind(__file__);bind(OUT/'head_common.py')
ep=load('work/r8-design/integration/electronics_world_envelopes.json');elect={r['name']:r for r in ep['items']}
new={r['name']:r for r in delta['added_or_replacement_items']};shapes={}
for n,r in new.items():shapes[n]=c.read(bind(r['step'],r['step_sha256']))
board_name=delta['board_representation']['name'];board=shapes[board_name]
results=[]
for r in raw['positive_pairs']:
    a,b=r['a'],r['b'];row=copy.deepcopy(r)
    if board_name in [a,b]:
        old=b if a==board_name else a
        if old.startswith('R10_HEAD_CM4carrier_'):
            key=old.removeprefix('R10_HEAD_');p=elect[key]
            bounds=p['native_bbox_mm'];s=c.box([(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)],[bounds[2*i+1]-bounds[2*i] for i in range(3)])
            s=c.tf(s,p['R'],np.array(p['t_mm'])+SHIFT)
            row['precise_source_component']=p
        else:
            assert old.startswith('R10_HEAD_R8_CM4_PEEK_B2B_1p50mm_');s=source_shape(old)
        iv=float(c.volume(c.common(board,s)));assert abs(iv)<1e-7,(a,b,iv)
        row.update(classification='SOURCE_EXACT_BOARD_FACE_CONTACT_BINARY_STL_ROUNDING',source_exact_common_mm3=iv,
             reason='Each named envelope/PEEK face is tested at precise declared source coordinates against the new1.6mmholedboard. Positive binarySTL residue is not positive exact source material.')
    elif 'R10_HEAD_R8_CM4_6061_finned_heatsink' in [a,b]:
        n=b if a=='R10_HEAD_R8_CM4_6061_finned_heatsink' else a
        assert n.endswith('front_washer')
        iv=float(c.volume(c.common(source_shape('R10_HEAD_R8_CM4_6061_finned_heatsink'),shapes[n])));assert abs(iv)<1e-7
        row.update(classification='SOURCE_EXACT_WASHER_BEARING_FACE_BINARY_STL_ROUNDING',source_exact_common_mm3=iv,
          reason='Nominal front washer bears on the original mounting lug face; the independently measured rigid contact area is recorded ininterface_audit.')
    elif 'R10_HEAD_CM4_VENDOR_MAX_ENVELOPE' in [a,b]:
        n=b if a=='R10_HEAD_CM4_VENDOR_MAX_ENVELOPE' else a
        assert n.startswith('R20_CM4_stack_') and n.endswith('_screw')
        checks=[p for p in interface['supplier_core']['hardware_near_candidates'] if p['hardware']==n]
        assert len(checks)==1 and all(abs(p['actual_STEP_common_mm3'])<1e-7 for p in checks)
        row.update(classification='HIDDEN_SUPPLIER_MAXIMUM_BOX_OVER_VERIFIED_EXISTING_NPTH',supplier_material_checks=checks,
          reason='The selected item is explicitly the supplier maximum box, hidden and not a material part. All385originalsolidbboxes screened; the only nearby valid PCB solid has diameter2.6NPTH and no positive material intersection. The one invalid source body is bbox-separated.')
    else:
        assert a.rsplit('_',1)[0]==b.rsplit('_',1)[0] and {a.rsplit('_',1)[1],b.rsplit('_',1)[1]}=={'screw','nut'},(a,b)
        prefix=a.rsplit('_',1)[0];joint=next(j for j in delta['joints'] if prefix.startswith('R20_CM4_'+('stack_'+j['id'].split('_')[-1] if 'STACK' in j['id'] else 'foot_'+j['id'].split('_')[-1])+'_'))
        v=np.array(joint['axis']);p=np.array(joint['nut_front_mm']);q=np.array(joint['nut_back_mm']);d=2 if 'STACK' in joint['id'] else 2.5
        A=shapes[a];B=shapes[b];I=c.common(A,B);roi=c.cylinder((p+q)/2,d/2+.00001,float(np.linalg.norm(q-p))+.00002,v)
        outside=float(c.volume(c.cut(I,roi)));assert abs(outside)<1e-8
        row.update(classification='NAMED_NOMINAL_MATING_THREAD_ENVELOPES',exact_nominal_thread_common_mm3=float(c.volume(I)),
          thread_ROI=dict(axis=v.tolist(),front_mm=p.tolist(),rear_mm=q.tolist(),max_radius_mm=d/2),outside_named_thread_ROI_mm3=outside,
          reason='The external-thread maximum-cylinder and mating nut root bore are deliberately dimensioned nominal thread representations. This specific engagement volume is not unexpected metal intrusion; it does not permit any other same-link overlap.')
    results.append(row)
assert len(results)==57
categories={r['classification']:sum(q['classification']==r['classification'] for q in results) for r in results}
dump(OUT/'contact_adjudication.json',dict(status='ALL57_NAMED_RAW_HOME_POSITIVES_ADJUDICATED_NO_UNEXPECTED_NEW_MATERIAL_PENETRATION',
    selection_count=557,pair_count=15718,positive_count=57,unexpected_positive_count=0,classification_counts=categories,rows=results,
    physical_approved=False,manufacturing_approved=False,whole_robot_assembly_approved=False,
    limits=['Only new/replacement geometry at HOME is adjudicated here; parent performs continuousmoving-pairchecks and retains unrelated oldsame-linkreviewitems.',
        'No whole-assembly2.2mmclearancepass is implied; named shank holes and bolted bearing faces have intentionally smaller mating clearances.',
        'A declared nominal thread pair is not a supplier lot/strength/preload/vibration qualification.'],sources=SOURCES))
print('ADJUDICATED',categories,flush=True)
