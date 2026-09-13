"""R8 custom measured voltage-control models for pinned BAM 62bd8ce.

Generated training tree only. No XL330 parameters or current units are inherited.
Two custom factories retain separate physical model parameters; each controlled
joint gets a separate BAM instance with its calibrated gain and fitted limit.
"""
from dataclasses import dataclass
from mjlab_microduck.actuator.r8_bam_models import register_models,set_effective_limit
from mjlab_microduck.actuator.friction_dr_bam import (
    FrictionDRBamActuator,FrictionDRBamActuatorCfg,
    BacklashEncoderBamActuator,BacklashEncoderBamActuatorCfg,
)

class R8CurrentLimitMixin:
    def __init__(self,cfg,*args,**kwargs):
        super().__init__(cfg,*args,**kwargs)
        # A fitted equivalent in the voltage-control law, never raw DXL current.
        set_effective_limit(self._bam_model.actuator,cfg.effective_current_limit_A)

class R8BamActuator(R8CurrentLimitMixin,FrictionDRBamActuator):pass
class R8BacklashBamActuator(R8CurrentLimitMixin,BacklashEncoderBamActuator):pass

@dataclass(kw_only=True)
class R8BamActuatorCfg(FrictionDRBamActuatorCfg):
    effective_current_limit_A:float
    def build(self,entity,target_ids,target_names):
        return R8BamActuator(self,entity,target_ids,target_names)

@dataclass(kw_only=True)
class R8BacklashBamActuatorCfg(BacklashEncoderBamActuatorCfg):
    effective_current_limit_A:float
    def build(self,entity,target_ids,target_names):
        return R8BacklashBamActuator(self,entity,target_ids,target_names)
