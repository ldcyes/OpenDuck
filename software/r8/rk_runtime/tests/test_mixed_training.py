"""Synthetic, standard-library tests of R8 training assembly, not physical fits."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from types import SimpleNamespace
from test_mixed_drive import data, load
from power_fixture import power_data,power_sha,platform_sha256
from microduck_rk.motion_limits import limits_sha256,policy_action_scales
from microduck_rk.contract import JOINT_NAMES, POLICY_SLOTS
from microduck_rk.actuators import current_raw, spec_for_id,profile_sha256
from microduck_rk import prepare_training as pt

BAM={1020:'xm430',1210:'xc330',1220:'xc330_t288'}

def bam(model):
    return {'model':'m6','actuator':'microduck_r8_'+BAM[model],
        'kt':2.0 if model==1020 else(.8 if model==1220 else .5),'R':5.,'armature':.001,'q_offset':0.,
        'friction_base':.01,'friction_viscous':.01,'friction_stribeck':.01,
        'load_friction_motor':.01,'load_friction_external':.01,
        'load_friction_motor_stribeck':.01,'load_friction_external_stribeck':.01,
        'load_friction_motor_quad':.001,'load_friction_external_quad':.001,
        'dtheta_stribeck':.1,'alpha':1.,
        'r8_actuator':{'drive_profile_sha256':profile_sha256(),'motion_limits_sha256':limits_sha256(),'hardware_platform_sha256':platform_sha256(),'power_configuration_sha256':power_sha(),'model_number':model,'voltage_V':10.8,'error_gain':.01,'max_pwm':1.},
        'synthetic_test_fixture':True}

def dynamics(cal):
    return {'motion_limits_sha256':limits_sha256(),'hardware_platform_sha256':platform_sha256(),'power_configuration_sha256':power_sha(),'schema':2,'robot':cal.data['robot'],'measured':True,'geometry_verified':True,
      'mode5_current_limit_fit_verified':True,'holdout_verified':True,
      'calibration_sha256':cal.sha256,'measurement_report':'SYNTHETIC TEST','holdout_report':'SYNTHETIC TEST',
      'vin_range':[10.5,11.5],'vin_drop_gain_range':[0.,.1],
      'delay_min_lag':2,'delay_max_lag':5,'joint_fits':{
        j['name']:{'model_number':j['model_number'],'goal_current_raw':current_raw(j['id'],j['current_limit_ma']),
            'effective_current_limit_A':.2+idx*.01,'p_gain':j['p_gain']} for idx,j in enumerate(cal.joints) if idx in POLICY_SLOTS},
      'bam_sha256_by_model':{},'bodies':{'trunk':{'mass_kg':1,'com_m':[0,0,0],'fullinertia_kgm2':[.01,.01,.01,0,0,0]}}}

class MixedTrainingTests(unittest.TestCase):
    def test_T288_fit_cannot_reuse_T181_or_old_drive_profile(self):
        b=bam(1220);pt.validate_bam(b,1220)
        with self.assertRaisesRegex(ValueError,'identity|model'):pt.validate_bam(bam(1210),1220)
        b['r8_actuator']['drive_profile_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'drive profile'):pt.validate_bam(b,1220)

    def test_bam_rejects_previous_platform_or_unbound_power_fit(self):
        for key,value in [('hardware_platform_sha256','old-Q38'),('power_configuration_sha256',None)]:
            b=bam(1020);b['r8_actuator'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'platform|power'):pt.validate_bam(b,1020)

    def test_router_exists(self):self.assertTrue(hasattr(pt,'training_routes'))
    @unittest.skipUnless(hasattr(pt,'training_routes'),'implementation not present yet')
    def test_exact_14_axis_routes_use_correct_models_currents_and_gains(self):
        c=load(data(),True);d=dynamics(c);routes=pt.training_routes(c,d)
        self.assertEqual([r['joint_name'] for r in routes],[JOINT_NAMES[i] for i in POLICY_SLOTS])
        for j,r in zip([c.joints[i] for i in POLICY_SLOTS],routes):
            self.assertEqual(r['model_number'],spec_for_id(j['id']).model_number)
            self.assertEqual(r['goal_current_raw'],111 if j['model_number']==1020 else 300)
            self.assertEqual(r['kp_fw'],j['p_gain'])
            matches=[n for n in JOINT_NAMES if re.fullmatch(r['target_names_expr'][0],n)]
            self.assertEqual(matches,[j['name']])
        self.assertEqual(sum(r['model_number']==1020 for r in routes),10)
        self.assertEqual(sum(r['model_number']==1220 for r in routes),2)
        self.assertEqual(sum(r['model_number']==1210 for r in routes),2)
    @unittest.skipUnless(hasattr(pt,'training_routes'),'implementation not present yet')
    def test_wrong_fit_model_raw_current_or_missing_axis_refused(self):
        c=load(data(),True);d=dynamics(c)
        for key,value in [('model_number',1210),('goal_current_raw',300),('effective_current_limit_A',0),('p_gain',42)]:
            bad=copy.deepcopy(d);bad['joint_fits']['left_hip_roll'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):pt.training_routes(c,bad)
        del d['joint_fits']['left_ankle']
        with self.assertRaises(ValueError):pt.training_routes(c,d)
    @unittest.skipUnless(hasattr(pt,'validate_bam'),'implementation not present yet')
    def test_custom_bam_requires_complete_finite_parameters_and_exact_model(self):
        pt.validate_bam(bam(1020),1020)
        for transform in [lambda x:x.update(actuator='xl330'),lambda x:x.pop('armature'),lambda x:x.update(R=float('nan'))]:
            v=bam(1020);transform(v)
            with self.assertRaises(ValueError):pt.validate_bam(v,1020)
    @unittest.skipUnless(hasattr(pt,'training_routes'),'implementation not present yet')
    def test_prepared_tree_has_three_fits_14_routes_and_no_shared_wildcard(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';robot=root/'model';robot.mkdir();
            constants=source/'src/mjlab_microduck/robot/microduck_constants.py';constants.parent.mkdir(parents=True)
            constants.write_text('_ROBOT_DIR=None\n_BAM_ACTUATOR_KWARGS=dict(motor_name="xl330", model="m6")\nactuators=FrictionDRBamActuatorCfg(**_BAM_ACTUATOR_KWARGS)\nbacklash_actuators=BacklashEncoderBamActuatorCfg(**_BAM_ACTUATOR_KWARGS)\nHOME_FRAME=None\ncfg=EntityArticulationInfoCfg(actuators=(actuators,))\nback=EntityArticulationInfoCfg(actuators=(backlash_actuators,))\n')
            config=source/'src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py';config.parent.mkdir(parents=True)
            config.write_text('def make_microduck_velocity_env_cfg():\n    cfg=None\n    return cfg\njoint_pos_action.scale = 1.0\nMicroduckRlCfg = RslRlOnPolicyRunnerCfg(\n)\n')
            (source/'uv.lock').write_text('62bd8ce12154340be97e06f7f41a0ca8f116d967')
            calp=root/'cal.json';calp.write_text(json.dumps(data()));c=pt.Calibration.load(calp,True);d=dynamics(c)
            paths={}
            for model in (1020,1210,1220):
                p=root/(BAM[model]+'.json');p.write_text(json.dumps(bam(model)));paths[model]=p
                d['bam_sha256_by_model'][str(model)]=hashlib.sha256(p.read_bytes()).hexdigest()
            dp=root/'d.json';dp.write_text(json.dumps(d))
            xml='<mujoco><worldbody><body name="trunk"><inertial mass="1" pos="0 0 0" diaginertia=".01 .01 .01"/>'+''.join('<joint name="'+JOINT_NAMES[i]+'"/>' for i in POLICY_SLOTS)+'</body></worldbody></mujoco>'
            for name in ('robot_walk.xml','robot_groundcontact.xml','robot_allcollisions.xml'):(robot/name).write_text(xml)
            pp=root/'power.json';pp.write_text(json.dumps(power_data()))
            out=root/'output';args=SimpleNamespace(power_config=str(pp),calibration=str(calp),dynamics=str(dp),upstream=str(source),output=str(out),robot_model_dir=str(robot),bam_xm430_json=str(paths[1020]),bam_xc330_json=str(paths[1210]),bam_t288_json=str(paths[1220]))
            pt.prepare(args)
            generated=(out/'src/mjlab_microduck/robot/microduck_constants.py').read_text();ast.parse(generated)
            self.assertNotIn('motor_name=',generated);self.assertNotIn('actuators=(actuators,)',generated)
            manifest=json.loads((out/'R8_TRAINING_INPUTS.json').read_text())
            self.assertEqual(manifest['motion_limits_sha256'],limits_sha256())
            self.assertEqual(manifest['mouth_structural_torque_limit_Nm'],.05)
            self.assertEqual(manifest['mouth_load_acceptance'],c.data['mouth_load_acceptance'])
            import xml.etree.ElementTree as ET
            tree=ET.parse(out/'src/mjlab_microduck/robot/microduck/robot_walk.xml')
            for node,j in zip(tree.findall('.//joint'),[c.joints[i] for i in POLICY_SLOTS]):
                for got,want in zip(map(float,node.get('range').split()),[j['min_rad'],j['max_rad']]):self.assertAlmostEqual(got*3.141592653589793/180,want)
            namespace={};exec((out/'src/mjlab_microduck/tasks/r8_limits.py').read_text(),namespace)
            cfg=SimpleNamespace(commands={k:SimpleNamespace(ranges=SimpleNamespace())for k in ['head_pose','body_pose','twist']},curriculum={'head_pose_range':object(),'body_pose_range':object()})
            namespace['apply_limits'](cfg)
            self.assertEqual(cfg.commands['head_pose'].ranges,((0.,0.),)*4)
            self.assertEqual(manifest['motion_context'],'head_home_locked')
            self.assertEqual(manifest['action_scale_by_joint'],policy_action_scales([JOINT_NAMES[i]for i in POLICY_SLOTS],.1,'head_home_locked'))
            scale_node=next(n for n in ast.walk(ast.parse((out/'src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py').read_text())) if isinstance(n,ast.Assign)and any(isinstance(t,ast.Attribute)and t.attr=='scale' for t in n.targets))
            self.assertEqual(ast.literal_eval(scale_node.value),{'^'+n+'$':v for n,v in manifest['action_scale_by_joint'].items()})
            self.assertEqual(cfg.commands['body_pose'].ranges[0],(0.,0.));self.assertEqual(cfg.commands['body_pose'].ranges[5],(0.,0.))
            self.assertEqual(cfg.commands['twist'].ranges.lin_vel_x,(-.15,.15));self.assertFalse(cfg.curriculum)
            self.assertEqual(len(manifest['actuator_routes']),14);self.assertFalse(manifest['motion_approved'])
            self.assertTrue((out/'src/mjlab_microduck/actuator/r8_bam.py').exists())
            self.assertTrue((out/'src/mjlab_microduck/actuator/r8_bam_models.py').exists())
            self.assertEqual(set(manifest['bam_sha256_by_model']),{'1020','1210','1220'})
            with self.assertRaises(ValueError):pt.prepare(args)
            args.output=str(root/'supported');args.motion_context='supported_double';supported=pt.prepare(args)
            ns={};exec((Path(args.output)/'src/mjlab_microduck/tasks/r8_limits.py').read_text(),ns);ns['apply_limits'](cfg)
            self.assertEqual(cfg.commands['head_pose'].ranges,tuple((j['min_rad']-j['home_rad'],j['max_rad']-j['home_rad'])for j in c.joints[5:9]))
            self.assertEqual(cfg.commands['body_pose'].ranges,((0.,0.),)*6)
            self.assertEqual(cfg.commands['twist'].ranges.lin_vel_x,(0.,0.))
            self.assertEqual(supported['action_scale_by_joint'],policy_action_scales([JOINT_NAMES[i]for i in POLICY_SLOTS],.1,'supported_double'))

