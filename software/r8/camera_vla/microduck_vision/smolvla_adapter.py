"""Workstation-only SmolVLA adapter for an explicitly fine-tuned Microduck high-level policy.
No checkpoint ships with R8. Arm checkpoints are rejected by the manifest/shape contract.
API basis: Hugging Face LeRobot, revision recorded in source_versions.json.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
from .protocol import PROFILE,ACTION_NAMES,state_vector,CAMERA_PROFILE,limits_sha256,validate_intent_context,validate_observation

STATE_NAMES = ([f'position_{i}' for i in range(15)]+['gyro_x','gyro_y','gyro_z','gravity_x','gravity_y','gravity_z'])

def check_manifest(m,root):
    if m.get('robot_profile')!=PROFILE or m.get('state_names')!=STATE_NAMES or m.get('action_names')!=ACTION_NAMES:
        raise ValueError('checkpoint was not specified for the Microduck high-level contract')
    if m.get('camera_key')!='observation.images.front' or m.get('fps')!=5 or m.get('camera_rotation_applied_deg') not in (0,180):
        raise ValueError('expected front RGB camera and 5 Hz dataset')
    if m.get('motion_limits_sha256')!=limits_sha256()or m.get('motion_context')not in ('head_home_locked','supported_double')or m.get('camera_profile')!=CAMERA_PROFILE:raise ValueError('R8 motion/camera binding missing or obsolete')
    files=m.get('checkpoint_files_sha256',{})
    if not files or 'microduck_training_profile.json' not in files or 'config.json' not in files or not any(n.endswith('.safetensors') for n in files):
        raise ValueError('checkpoint manifest must bind configuration and trained weights')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if actual!=set(files):raise ValueError('manifest must bind every checkpoint file, including processors/tokenizer')
    for name,want in files.items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()):raise ValueError('checkpoint path traversal')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=want:raise ValueError('checkpoint hash mismatch: '+name)
    profile=json.loads((root/'microduck_training_profile.json').read_text())
    for key in ('robot_profile','camera_key','camera_rotation_applied_deg','calibration_sha256','fps','state_names','action_names','motion_limits_sha256','motion_context','camera_profile'):
        if profile.get(key)!=m.get(key):raise ValueError('training/deployment profile mismatch: '+key)
    if profile.get('width')!=640 or profile.get('height')!=480:raise ValueError('training image dimensions mismatch')
    if m.get('approved_for_simulation') is not True:raise ValueError('simulation review not recorded')
    return m

def decode_action(values):
    from microduck_interaction.schema import validate_intent
    if len(values)!=11:raise ValueError('VLA must output 11 high-level values, not 15 servo targets')
    return validate_intent({'vx':values[0],'vy':values[1],'yaw':values[2],'head':values[3:7],'body':values[7:10],'mouth':values[10],'duration_s':.2})

class SmolVLAAdapter:
    def __init__(self,manifest_path):
        path=Path(manifest_path).resolve();self.manifest=json.loads(path.read_text())
        root=(path.parent/self.manifest['checkpoint_directory']).resolve()
        check_manifest(self.manifest,root)
        import torch
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
        from lerobot.policies.factory import make_pre_post_processors
        self.torch=torch
        self.device=self.manifest.get('device','cuda')
        self.policy=SmolVLAPolicy.from_pretrained(str(root)).to(self.device).eval()
        cfg=self.policy.config
        if getattr(cfg,'adapt_to_pi_aloha',False) or getattr(cfg,'use_delta_joint_actions_aloha',False):raise ValueError('arm-specific action transforms forbidden')
        if cfg.max_state_dim!=32 or cfg.max_action_dim!=32:raise ValueError('base projection width must remain32; no unreviewed weight surgery')
        if list(cfg.input_features['observation.state'].shape)!=[21] or list(cfg.output_features['action'].shape)!=[11]:
            raise ValueError('checkpoint feature dimensions mismatch')
        if set(cfg.image_features)!={'observation.images.front'}:raise ValueError('camera feature mismatch')
        self.pre,self.post=make_pre_post_processors(cfg,pretrained_path=str(root),preprocessor_overrides={'device_processor':{'device':self.device}})
    def infer(self,o):
        validate_observation(o)
        if o['state']['motion_context']['mode']!=self.manifest['motion_context']:raise ValueError('checkpoint motion context mismatch')
        if o['image']['rotation_applied_deg']!=self.manifest['camera_rotation_applied_deg']:raise ValueError('camera orientation differs from training manifest')
        if o['state']['calibration_sha256']!=self.manifest['calibration_sha256']:raise ValueError('checkpoint calibration mismatch')
        if not o['simulated'] and self.manifest.get('approved_for_live') is not True:raise ValueError('checkpoint lacks live validation')
        from PIL import Image
        import numpy as np
        im=Image.open(io.BytesIO(base64.b64decode(o['image']['jpeg_base64'])))
        if im.width*im.height>1920*1080:raise ValueError('decoded image exceeds 1080p')
        # Training/export use the same explicit 640x480 camera profile; preserve RGB and [0,1].
        if im.size!=(640,480):raise ValueError('camera dimensions must match training: 640x480')
        rgb=np.asarray(im.convert('RGB')).copy()
        batch={'observation.state':self.torch.tensor(state_vector(o),dtype=self.torch.float32),
               'observation.images.front':self.torch.from_numpy(rgb).permute(2,0,1).float()/255.,'task':o['task']}
        self.policy.reset() # No stale action chunks across independent image requests.
        with self.torch.inference_mode():
            action=self.post(self.policy.select_action(self.pre(batch)))
        values=action.detach().cpu().reshape(-1).tolist()
        return {'robot_profile':PROFILE,'say':'','intent':validate_intent_context(decode_action(values),self.manifest['motion_context'])}
