"""Atomic last measured state. Targets and inferred poses are never substituted."""
import math
from .motion_limits import limits_sha256
from .contract import finite
from microduck_interaction.executor import atomic_json


def publish(path,sensors,imu,calibration_sha256,robot_profile,armed,measured_monotonic_s,sent=None,motion_context=None):
    q=finite(sensors['positions'],15,'measured q');dq=finite(sensors['velocities'],15,'measured dq')
    gyro=finite(imu['gyro'],3,'measured gyro');gravity=finite(imu['gravity'],3,'measured gravity')
    finite([measured_monotonic_s,imu['age_s']],2,'measurement time')
    if imu['age_s']<0:raise ValueError('invalid IMU age')
    extra={}
    if sent is not None:
        extra={'sent_commands':finite(sent['commands'],13,'sent command'),
               'sent_mouth_rad':finite([sent['mouth_rad']],1,'sent mouth')[0],
               'sent_monotonic_s':finite([sent['monotonic_s']],1,'sent timestamp')[0],
               'source_command_monotonic_s':finite([sent['source_monotonic_s']],1,'source timestamp')[0]}
        if extra['source_command_monotonic_s']>extra['sent_monotonic_s']:raise ValueError('future source command timestamp')
    atomic_json(path,{'motion_context':motion_context,**extra,'motion_limits_sha256':limits_sha256(),'schema':1,'source':'live_dynamixel_sflp','robot_profile':robot_profile,
                     'commissioned':True,'armed':bool(armed),'calibration_sha256':calibration_sha256,
                     'monotonic_s':measured_monotonic_s,'imu_age_s':imu['age_s'],
                     'q':q,'dq':dq,'positions':q,'velocities':dq,'gyro':gyro,'gravity':gravity})
