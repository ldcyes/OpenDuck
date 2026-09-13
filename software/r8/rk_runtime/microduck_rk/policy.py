import hashlib
import json
import time
from pathlib import Path
from .motion_limits import limits_sha256,policy_action_scales
from .contract import JOINT_NAMES,POLICY_SLOTS
from .power import platform_sha256
from .actuators import ROBOT_PROFILE, profile_sha256


def validate_manifest(m,calibration,policy_sha256,motion_context='head_home_locked'):
    expected={'motion_limits_sha256':limits_sha256(),'hardware_platform_sha256':platform_sha256(),'power_configuration_sha256':calibration.data.get('power_configuration_sha256'),'robot':ROBOT_PROFILE,'drive_profile_sha256':profile_sha256(),'drive_configuration_sha256':calibration.drive_sha256,'calibration_sha256':calibration.sha256,
              'policy_sha256':policy_sha256,
              'observation_size':61,'action_size':14,'motion_approved':True,
              'motion_context':motion_context,'action_scale_by_joint':policy_action_scales([JOINT_NAMES[i] for i in POLICY_SLOTS],calibration.data['action_scale'],motion_context),'action_filter':'motion_context_joint_scale_mask','action_clip':None,'action_scale':calibration.data['action_scale'],
              'previous_action':'raw_unfiltered_network_output','imu_observation':'projected_gravity',
              'control_hz':50,'home_rad':calibration.home}
    for k,v in expected.items():
        if m.get(k)!=v: raise ValueError(f'policy manifest mismatch/unapproved: {k}')
    if not m.get('validation_report') or not m.get('dynamics_sha256'):
        raise ValueError('bench/simulation validation report and dynamics provenance required')



class Policy:
    def __init__(self,path,calibration=None,manifest=None,motion_context='head_home_locked'):
        import onnxruntime as ort
        import numpy as np
        self.np=np
        options=ort.SessionOptions(); options.intra_op_num_threads=2; options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        inputs=self.session.get_inputs(); outputs=self.session.get_outputs()
        if len(inputs)!=1 or len(outputs)!=1 or inputs[0].shape!=[1,61] or outputs[0].shape!=[1,14]:
            raise ValueError('policy must be exactly [1,61] -> [1,14]; legacy exports are refused')
        if inputs[0].type!='tensor(float)' or outputs[0].type!='tensor(float)':
            raise ValueError('policy float32 input and output required')
        self.input=inputs[0].name
        if calibration:
            if not manifest: raise ValueError('R8 hardware policy manifest required')
            m=json.loads(Path(manifest).read_text())
            validate_manifest(m,calibration,hashlib.sha256(Path(path).read_bytes()).hexdigest(),motion_context)
        # Warmup is inference only: no motor handle or hardware exists here.
        warm=[0.]*61;warm[5]=-1.
        self.run(warm)

    def run(self,obs):
        result=self.session.run(None,{self.input:self.np.asarray([obs],dtype=self.np.float32)})[0]
        if result.shape!=(1,14) or not self.np.isfinite(result).all():
            raise RuntimeError('policy returned nonfinite/wrong-sized action')
        return result[0].tolist()

    def benchmark(self,n=200):
        rng=self.np.random.default_rng(20260905); samples=[]
        for _ in range(n):
            obs=rng.normal(0,.05,61);obs[5]=-1
            start=time.perf_counter();self.run(obs);samples.append((time.perf_counter()-start)*1000)
        return {'provider':'CPUExecutionProvider','samples':n,'p50_ms':float(self.np.percentile(samples,50)),
                'p99_ms':float(self.np.percentile(samples,99)),'max_ms':max(samples)}
