"""Custom R8 measured models for BAM; CPU import needs no mjlab/GPU."""
import json
import math
from pathlib import Path
from bam.actuator import VoltageControlledActuator
from bam.actuators import actuators as registry
from bam.parameter import Parameter
from bam.testbench import Pendulum

class MeasuredVoltageActuator(VoltageControlledActuator):
    def __init__(self,meta):
        super().__init__(Pendulum,vin=meta['voltage_V'],kp=1.,
                         error_gain=meta['error_gain'],max_pwm=meta['max_pwm'],max_current=None)
    def initialize(self):
        super().initialize()
        # All three are required in the validated custom JSON before generation.
        self.model.armature=Parameter(.001,0.,1.)
    def get_extra_inertia(self):return self.model.armature.value

def register_models(directory):
    for model,name in ((1020,'xm430'),(1210,'xc330'),(1220,'xc330_t288')):
        payload=json.loads((Path(directory)/(name+'_bam.json')).read_text())
        if payload['r8_actuator']['model_number']!=model or payload['actuator']!='microduck_r8_'+name:
            raise ValueError('R8 custom BAM model identity mismatch')
        meta=payload['r8_actuator']
        registry[payload['actuator']]=lambda meta=meta:MeasuredVoltageActuator(meta)

def set_effective_limit(actuator,limit_A):
    if isinstance(limit_A,bool) or not isinstance(limit_A,(int,float)) or not math.isfinite(limit_A) or not 0<limit_A<=10:
        raise ValueError('measured equivalent current limit required')
    actuator.max_current=limit_A
