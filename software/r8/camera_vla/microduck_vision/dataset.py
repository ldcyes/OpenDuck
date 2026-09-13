"""Validate manual demonstration JSONL and export a LOCAL LeRobot dataset. Never uploads."""
import argparse
import base64
import io
import json
from pathlib import Path
from .protocol import ACTION_NAMES,PROFILE,number,state_vector,validate_observation,validate_intent_context,context_binding,CAMERA_PROFILE
from .smolvla_adapter import STATE_NAMES

def validate_episode(rows):
    from microduck_interaction.schema import validate_intent
    if len(rows)<2:raise ValueError('episode needs at least two real demonstration frames')
    last=None;calibration=None;rotation=None;context=None;seen=set()
    result=[]
    for row in rows:
        if row.get('teacher')!='human_teleoperation' or row.get('successful') is not True:
            raise ValueError('only reviewed successful human demonstrations are exported')
        o=row['observation'];validate_observation(o)
        mode=o['state']['motion_context']['mode']
        if context is not None and context!=mode:raise ValueError('mixed motion contexts inside episode')
        context=mode
        orientation=o['image']['rotation_applied_deg']
        if rotation is not None and orientation!=rotation:raise ValueError('mixed camera rotation inside episode')
        rotation=orientation
        if o['simulated']:raise ValueError('real dataset refuses simulated observations')
        stamp=o['capture_monotonic_s'];applied=row.get('executed_monotonic_s')
        if not number(applied) or abs(applied-stamp)>.1:raise ValueError('image/applied action misalignment')
        if last is not None and abs(stamp-last-.2)>.04:raise ValueError('5 Hz sampling has a gap; split episode or recollect')
        if o['request_id'] in seen:raise ValueError('duplicate observation in episode')
        seen.add(o['request_id']);last=stamp
        digest=o['state']['calibration_sha256']
        if calibration is not None and digest!=calibration:raise ValueError('calibration changed inside episode')
        calibration=digest
        intent=validate_intent_context(row['executed_intent'],mode)
        action=[intent['vx'],intent['vy'],intent['yaw']]+intent['head']+intent['body']+[intent['mouth']]
        result.append((o,action))
    return result

def dataset_profile(episodes):
    identities={(o['image']['rotation_applied_deg'],o['state']['calibration_sha256'],o['state']['motion_limits_sha256'],o['state']['motion_context']['mode']) for episode in episodes for o,_ in episode}
    if len(identities)!=1:raise ValueError('all episodes must share camera rotation and calibration')
    rotation,calibration,motion_sha,mode=next(iter(identities))
    return {'motion_limits_sha256':motion_sha,'motion_context':mode,'camera_profile':CAMERA_PROFILE,'robot_profile':PROFILE,'camera_key':'observation.images.front','camera_rotation_applied_deg':rotation,'calibration_sha256':calibration,'fps':5,'state_names':STATE_NAMES,'action_names':ACTION_NAMES,'width':640,'height':480}

def main():
    p=argparse.ArgumentParser();p.add_argument('episodes',nargs='+');p.add_argument('--root');p.add_argument('--repo-id',default='local/microduck-r8-demonstrations');p.add_argument('--validate-only',action='store_true')
    a=p.parse_args();episodes=[]
    for path in a.episodes:
        rows=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        episodes.append(validate_episode(rows))
    profile=dataset_profile(episodes)
    if a.validate_only:print(json.dumps({'episodes':len(episodes),'frames':sum(map(len,episodes)),'data':'validated, not a trained model'}));return
    if not a.root:p.error('--root required for local dataset export')
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from PIL import Image
    import numpy as np
    features={'observation.state':{'dtype':'float32','shape':(21,),'names':STATE_NAMES},
              'observation.images.front':{'dtype':'image','shape':(480,640,3),'names':['height','width','channels']},
              'action':{'dtype':'float32','shape':(11,),'names':ACTION_NAMES}}
    dataset=LeRobotDataset.create(repo_id=a.repo_id,root=a.root,fps=5,robot_type=PROFILE,features=features,use_videos=False)
    try:
        for episode in episodes:
            for o,action in episode:
                im=Image.open(io.BytesIO(base64.b64decode(o['image']['jpeg_base64']))).convert('RGB')
                if im.size!=(640,480):raise ValueError('expected actual 640x480 camera frames')
                dataset.add_frame({'observation.state':np.array(state_vector(o),dtype=np.float32),'observation.images.front':np.asarray(im),'action':np.array(action,dtype=np.float32),'task':o['task']})
            dataset.save_episode()
    finally:dataset.finalize()
    (Path(a.root)/'meta'/'microduck_training_profile.json').write_text(json.dumps(profile,indent=2))
if __name__=='__main__':main()
