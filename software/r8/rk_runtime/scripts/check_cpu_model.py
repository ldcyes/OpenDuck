#!/usr/bin/env python3
"""CPU-only source/MJCF integrity smoke, NOT learned locomotion or R1 validation."""
import argparse
import json
from pathlib import Path
import numpy as np
import mujoco


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--models',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();results=[]
    expected=['left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle','neck_pitch','head_pitch','head_yaw','head_roll','right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle']
    for name in ['robot_walk.xml','robot_groundcontact.xml','robot_allcollisions.xml']:
        m=mujoco.MjModel.from_xml_path(str(Path(a.models)/name));d=mujoco.MjData(m)
        names=[m.joint(int(m.actuator_trnid[i,0])).name for i in range(m.nu)]
        assert names==expected,(name,names)
        assert m.nu==14
        assert np.all(m.body_mass[1:]>0)
        # The robot file has no floor; this checks finite integration, not balancing.
        for _ in range(100):
            mujoco.mj_step(m,d);assert np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()
        results.append({'model':name,'nq':m.nq,'nv':m.nv,'actuators':m.nu,'body_mass_sum_kg':float(m.body_mass.sum()),
                        'actuator_joint_order':names,'finite_steps':100})
    report={'status':'passed','scope':'upstream CPU model compilation and finite integration only',
            'not_validated':['R1 changed geometry/inertia','XC330 actuation','learned walking','real robot'],
            'mujoco_version':mujoco.__version__,'models':results}
    Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
