"""Create a measured R8 tree with separate XM430, T181 and T288 BAM fits."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from .motion_limits import limits_sha256, CONTRACT, HEAD_NAMES, COMMAND_CAPS,policy_action_scales
from .voltage_limits import WINDOW
from .contract import Calibration,finite,JOINT_NAMES,POLICY_SLOTS
from .actuators import ROBOT_PROFILE,current_raw,profile_sha256
from .power import PowerConfig,platform_sha256

BAM_COMMIT='62bd8ce12154340be97e06f7f41a0ca8f116d967'
MODEL_NAMES={1020:'xm430',1210:'xc330',1220:'xc330_t288'}
def determinant(m):
    return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0])


def validate_inertial(d):
    finite([d['mass_kg']],1,'mass');finite(d['com_m'],3,'center of mass')
    v=finite(d['fullinertia_kgm2'],6,'inertia tensor')
    if d['mass_kg']<=0: raise ValueError('mass must be positive')
    a,b,c,xy,xz,yz=v;m=[[a,xy,xz],[xy,b,yz],[xz,yz,c]]
    if a<=0 or a*b-xy*xy<=0 or determinant(m)<=0: raise ValueError('inertia must be positive definite')
    half=(a+b+c)/2;n=[[half*(i==j)-m[i][j] for j in range(3)] for i in range(3)]
    if min(n[i][i] for i in range(3))<0 or determinant(n)<-1e-24 or any(n[i][i]*n[j][j]-n[i][j]**2 < -1e-24 for i,j in [(0,1),(0,2),(1,2)]):
        raise ValueError('inertia violates rigid-body triangle inequality')


def replace_assignment(text,name,replacement):
    node=next(n for n in ast.parse(text).body if isinstance(n,(ast.Assign,ast.AnnAssign)) and
              any(isinstance(x,ast.Name) and x.id==name for x in (n.targets if isinstance(n,ast.Assign) else [n.target])))
    lines=text.splitlines(True);lines[node.lineno-1:node.end_lineno]=[replacement+'\n'];return ''.join(lines)



def validate_bam(payload,model_number,power_sha=None):
    if payload.get('model')!='m6' or payload.get('actuator')!='microduck_r8_'+MODEL_NAMES[model_number]:
        raise ValueError('R8 requires explicit custom m6 BAM model identity; no bundled XL330 fallback')
    keys=('kt','R','armature','q_offset','friction_base','friction_viscous','friction_stribeck',
          'load_friction_motor','load_friction_external','load_friction_motor_stribeck',
          'load_friction_external_stribeck','load_friction_motor_quad','load_friction_external_quad',
          'dtheta_stribeck','alpha')
    finite([payload.get(k) for k in keys],len(keys),'complete BAM fit')
    if any(payload[k]<=0 for k in ('kt','R','armature','dtheta_stribeck','alpha')):
        raise ValueError('BAM motor/velocity parameters must be positive')
    if any(payload[k]<0 for k in keys if k.startswith(('friction','load_friction'))):
        raise ValueError('negative BAM friction budget')
    m=payload.get('r8_actuator',{})
    if m.get('drive_profile_sha256')!=profile_sha256():raise ValueError('BAM drive profile mismatch')
    if m.get('motion_limits_sha256')!=limits_sha256():raise ValueError('BAM motion/load contract mismatch')
    digest=m.get('power_configuration_sha256')
    if m.get('hardware_platform_sha256')!=platform_sha256():raise ValueError('BAM platform mismatch')
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef'for c in digest) or (power_sha is not None and digest!=power_sha):raise ValueError('BAM power calibration binding mismatch')
    if m.get('model_number')!=model_number:raise ValueError('BAM physical model mismatch')
    finite([m.get(k) for k in ('voltage_V','error_gain','max_pwm')],3,'BAM actuator metadata')
    if not WINDOW['bench_XM_terminal_min_V']<=m['voltage_V']<=11.8 or not 0<m['error_gain']<=1 or not 0<m['max_pwm']<=1:
        raise ValueError('BAM voltage/error_gain/PWM outside R8 fit envelope')

def training_routes(cal,d):
    expected={JOINT_NAMES[i] for i in POLICY_SLOTS}
    if not isinstance(d.get('joint_fits'),dict) or set(d['joint_fits'])!=expected:
        raise ValueError('R8 mixed fit requires each of 14 policy axes once; mouth is independently controlled')
    routes=[]
    for i in POLICY_SLOTS:
        j=cal.joints[i];f=d['joint_fits'][j['name']]
        raw=current_raw(j['id'],j['current_limit_ma'])
        if f.get('model_number')!=j['model_number'] or f.get('goal_current_raw')!=raw or f.get('p_gain')!=j['p_gain']:
            raise ValueError(f'{j["name"]}: mixed model/current/gain fit does not match hardware calibration')
        finite([f.get('effective_current_limit_A')],1,'per-axis measured equivalent current')
        if not 0<f['effective_current_limit_A']<=10:raise ValueError('invalid per-axis equivalent current fit')
        routes.append({'joint_name':j['name'],'id':j['id'],'model_number':j['model_number'],
                       'goal_current_raw':raw,'target_names_expr':('^'+re.escape(j['name'])+'$',),
                       'kp_fw':j['p_gain'],'effective_current_limit_A':f['effective_current_limit_A']})
    return routes

def prepare(args):
    if not hasattr(args,'calibration'):raise ValueError('R8 mixed training inputs required')
    mode=getattr(args,'motion_context','head_home_locked')
    cal=Calibration.load(args.calibration,motion=True)
    scales=policy_action_scales([JOINT_NAMES[i]for i in POLICY_SLOTS],cal.data['action_scale'],mode)
    d=json.loads(Path(args.dynamics).read_text())
    power=PowerConfig.load(args.power_config)
    if any(x.get('power_configuration_sha256')!=power.sha256 or x.get('hardware_platform_sha256')!=platform_sha256() for x in (cal.data,d)):raise ValueError('training CM4 power/platform binding mismatch')
    if d.get('motion_limits_sha256')!=limits_sha256():raise ValueError('training motion limits contract mismatch')
    if d.get('schema')!=2 or d.get('robot')!=ROBOT_PROFILE:raise ValueError('R8 dynamics profile required')
    required=('measured','geometry_verified','mode5_current_limit_fit_verified','holdout_verified')
    if any(d.get(k) is not True for k in required):raise ValueError('R8 dynamics/current fits must be measured and verified')
    if d.get('calibration_sha256')!=cal.sha256:raise ValueError('dynamics calibration SHA mismatch')
    if not d.get('measurement_report') or not d.get('holdout_report'):raise ValueError('fit measurement/holdout reports required')
    routes=training_routes(cal,d)
    finite(d.get('vin_range'),2,'terminal voltage training range');finite(d.get('vin_drop_gain_range'),2,'branch sag range')
    if not WINDOW['bench_XM_terminal_min_V']<=d['vin_range'][0]<=d['vin_range'][1]<=11.8:raise ValueError('training voltage outside R8 10.8V rail envelope')
    if not 0<=d['vin_drop_gain_range'][0]<=d['vin_drop_gain_range'][1]<=2:raise ValueError('invalid measured branch sag range')
    if any(type(d.get(k)) is not int for k in ('delay_min_lag','delay_max_lag')) or not 0<=d['delay_min_lag']<=d['delay_max_lag']<=30:
        raise ValueError('invalid per-axis measured command delay range')
    paths={1020:Path(args.bam_xm430_json).resolve(),1210:Path(args.bam_xc330_json).resolve(),1220:Path(args.bam_t288_json).resolve()}
    for model,p in paths.items():
        if hashlib.sha256(p.read_bytes()).hexdigest()!=d.get('bam_sha256_by_model',{}).get(str(model)):
            raise ValueError(f'BAM hash mismatch for model {model}')
        validate_bam(json.loads(p.read_text()),model,power.sha256)
    source=Path(args.upstream).resolve();out=Path(args.output).resolve();model_source=Path(args.robot_model_dir).resolve()
    if out.exists():raise ValueError('output already exists; choose a new training directory')
    if out.is_relative_to(source) or out.is_relative_to(model_source):raise ValueError('output cannot be inside source trees')
    if BAM_COMMIT not in (source/'uv.lock').read_text():raise ValueError('pinned BAM API version mismatch')
    constants_rel=Path('src/mjlab_microduck/robot/microduck_constants.py')
    constants=(source/constants_rel).read_text()
    kwargs=[]
    for r in routes:
        kwargs.append({k:r[k] for k in ('target_names_expr','kp_fw','effective_current_limit_A')} |
          {'json_filename':MODEL_NAMES[r['model_number']]+'_bam.json','vin_range':tuple(d['vin_range']),
           'vin_drop_gain_range':tuple(d['vin_drop_gain_range']),'vin_min':cal.data['voltage_hard'],
           'delay_min_lag':d['delay_min_lag'],'delay_max_lag':d['delay_max_lag']})
    setup=('_BAM_ACTUATOR_KWARGS = '+repr(kwargs)+'\n'+
          'from mjlab_microduck.actuator.r8_bam import register_models, R8BamActuatorCfg, R8BacklashBamActuatorCfg\n'+
          '_R8_FIT_DIR = _ROBOT_DIR.parent / "r8"\nregister_models(_R8_FIT_DIR)\n'+
          'for _r8_kw in _BAM_ACTUATOR_KWARGS:\n    _r8_kw["json_path"] = str(_R8_FIT_DIR / _r8_kw.pop("json_filename"))')
    constants=replace_assignment(constants,'_BAM_ACTUATOR_KWARGS',setup)
    constants=replace_assignment(constants,'actuators','actuators = tuple(R8BamActuatorCfg(**kw) for kw in _BAM_ACTUATOR_KWARGS)')
    constants=replace_assignment(constants,'backlash_actuators','backlash_actuators = tuple(R8BacklashBamActuatorCfg(**kw) for kw in _BAM_ACTUATOR_KWARGS)')
    # Convert every articulation to the flat tuple, never a tuple containing a tuple.
    constants=re.sub(r'actuators\s*=\s*\(actuators,\s*\)', 'actuators=actuators', constants)
    constants=re.sub(r'actuators\s*=\s*\(backlash_actuators,\s*\)', 'actuators=backlash_actuators', constants)
    home={f'^{JOINT_NAMES[i]}$':cal.joints[i]['home_rad'] for i in POLICY_SLOTS}
    constants=replace_assignment(constants,'HOME_FRAME',f'HOME_FRAME = EntityCfg.InitialStateCfg(joint_pos={home!r}, joint_vel={{".*":0.}})')
    ast.parse(constants)
    cfg_rel=Path('src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py');cfg=(source/cfg_rel).read_text()
    if cfg.count('joint_pos_action.scale = 1.0')!=1:raise ValueError('pinned action-scale source changed')
    cfg=cfg.replace('joint_pos_action.scale = 1.0','joint_pos_action.scale = '+repr({'^'+re.escape(n)+'$':v for n,v in scales.items()}))
    if cfg.count('MicroduckRlCfg = RslRlOnPolicyRunnerCfg(')!=1:raise ValueError('pinned runner configuration changed')
    cfg=cfg.replace('MicroduckRlCfg = RslRlOnPolicyRunnerCfg(', 'MicroduckRlCfg = RslRlOnPolicyRunnerCfg(\n    clip_actions=None,')
    fn=next((n for n in ast.parse(cfg).body if isinstance(n,ast.FunctionDef) and n.name=='make_microduck_velocity_env_cfg'),None)
    returns=[] if fn is None else [n for n in fn.body if isinstance(n,ast.Return) and isinstance(n.value,ast.Name) and n.value.id=='cfg']
    if len(returns)!=1:raise ValueError('pinned velocity configuration return changed')
    lines=cfg.splitlines(True);lines.insert(returns[0].lineno-1,'    from mjlab_microduck.tasks.r8_limits import apply_limits\n    apply_limits(cfg)\n');cfg=''.join(lines)
    ast.parse(cfg)
    head_ranges=tuple((j['min_rad']-j['home_rad'],j['max_rad']-j['home_rad']) for j in cal.joints if j['name'] in HEAD_NAMES) if mode=='supported_double' else ((0.,0.),)*4
    limits_code=("# Generated from measured calibration and the R8 single limit contract.\n"+
      "MOTION_LIMITS_SHA256="+repr(limits_sha256())+"\nHEAD_RANGES="+repr(head_ranges)+"\n"+
      "BODY_RANGES="+repr(((0.,0.),(0.,0.),(-COMMAND_CAPS[9],COMMAND_CAPS[9]),(-COMMAND_CAPS[10],COMMAND_CAPS[10]),(-COMMAND_CAPS[11],COMMAND_CAPS[11]),(0.,0.)) if mode=='head_home_locked' else ((0.,0.),)*6)+"\n"+
      "def apply_limits(cfg):\n    cfg.commands['head_pose'].ranges=HEAD_RANGES\n    cfg.commands['body_pose'].ranges=BODY_RANGES\n"+
      "    cfg.curriculum.pop('head_pose_range',None)\n    cfg.curriculum.pop('body_pose_range',None)\n"+
      "    v=cfg.commands['twist'].ranges\n"+
      ''.join('    v.'+k+'='+repr((-cap,cap) if mode=='head_home_locked' else (0.,0.))+'\n' for k,cap in zip(('lin_vel_x','lin_vel_y','ang_vel_z'),COMMAND_CAPS[:3])))
    trees={}
    for name in ('robot_walk.xml','robot_groundcontact.xml','robot_allcollisions.xml'):
        tree=ET.parse(model_source/name)
        joint_names=[j.attrib.get('name') for j in tree.findall('.//worldbody//joint') if not j.attrib.get('name','').startswith('passive_')]
        if joint_names!=[JOINT_NAMES[i] for i in POLICY_SLOTS]:raise ValueError(name+': policy joint order mismatch')
        compiler=tree.getroot().find('compiler')
        angle='degree' if compiler is None else compiler.get('angle','degree')
        if angle not in ('degree','radian'):raise ValueError('unknown MuJoCo angle unit')
        scale=180/math.pi if angle=='degree' else 1.
        by_name={j['name']:j for j in cal.joints}
        for node in tree.findall('.//worldbody//joint'):
            if node.get('name') in by_name:
                j=by_name[node.get('name')];node.set('range',f"{j['min_rad']*scale:.17g} {j['max_rad']*scale:.17g}");node.set('limited','true')
        for body in tree.findall('.//body'):
            inertial=body.find('inertial')
            if inertial is None:continue
            measured=d['bodies'].get(body.attrib.get('name'))
            if measured is None:raise ValueError('unmeasured rigid body '+str(body.attrib.get('name')))
            validate_inertial(measured);inertial.attrib.clear();inertial.set('mass',str(measured['mass_kg']))
            inertial.set('pos',' '.join(map(str,measured['com_m'])));inertial.set('fullinertia',' '.join(map(str,measured['fullinertia_kgm2'])))
        trees[name]=tree
    shutil.copytree(source,out)
    robot=out/'src/mjlab_microduck/robot/microduck';shutil.copytree(model_source,robot,dirs_exist_ok=True)
    for name,tree in trees.items():tree.write(robot/name,encoding='utf-8',xml_declaration=True)
    fit=out/'src/mjlab_microduck/robot/r8';fit.mkdir()
    for model,p in paths.items():shutil.copy2(p,fit/(MODEL_NAMES[model]+'_bam.json'))
    shutil.copy2(args.calibration,fit/'calibration.json');shutil.copy2(args.dynamics,fit/'dynamics.json');shutil.copy2(args.power_config,fit/'power.json')
    adapter=out/'src/mjlab_microduck/actuator/r8_bam.py';adapter.parent.mkdir(parents=True,exist_ok=True)
    for filename in ('r8_bam.py','r8_bam_models.py'):
        shutil.copy2(Path(__file__).parent/'training_templates'/filename,adapter.parent/filename)
    (out/constants_rel).write_text(constants);(out/cfg_rel).write_text(cfg)
    (out/cfg_rel.parent/'r8_limits.py').write_text(limits_code)
    (fit/'motion_limits.json').write_text(json.dumps({'motion_limits_sha256':limits_sha256(),**CONTRACT},indent=2)+'\n')
    manifest={'mouth_structural_torque_limit_Nm':CONTRACT['mouth_structural_torque_limit_Nm'],'mouth_load_acceptance':cal.data['mouth_load_acceptance'],'motor_capability_qualification':cal.data['motor_capability_qualification'],'motion_limits_sha256':limits_sha256(),'hardware_platform_sha256':platform_sha256(),'power_configuration_sha256':power.sha256,'robot':ROBOT_PROFILE,'drive_profile_sha256':profile_sha256(),'drive_configuration_sha256':cal.drive_sha256,
      'upstream_commit':'29e887ecfbf5d37144759e5a9f8a176dfb83d547','bam_commit':BAM_COMMIT,
      'calibration_sha256':cal.sha256,'dynamics_sha256':hashlib.sha256(Path(args.dynamics).read_bytes()).hexdigest(),
      'bam_sha256_by_model':d['bam_sha256_by_model'],'actuator_routes':routes,
      'task':'Mjlab-Velocity-Flat-MicroDuck','observation_size':61,'action_size':14,'training_completed':False,
      'motion_approved':False,'validation_report':None,'motion_context':mode,'action_scale_by_joint':scales,'action_filter':'motion_context_joint_scale_mask','action_clip':None,
      'action_scale':cal.data['action_scale'],'previous_action':'raw_unfiltered_network_output',
      'imu_observation':'projected_gravity','control_hz':50,'home_rad':cal.home}
    (out/'R8_TRAINING_INPUTS.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('upstream','output','calibration','dynamics','bam-xm430-json','bam-xc330-json','bam-t288-json','robot-model-dir','power-config'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--motion-context',choices=('head_home_locked','supported_double'),default='head_home_locked')
    a=p.parse_args();print(json.dumps({'prepared':a.output,**prepare(a)},indent=2))

if __name__=='__main__':main()
