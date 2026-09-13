"""Read-only resampling for display. Never creates or qualifies a dynamics trajectory."""
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

ACTUAL_STATUS='ACTUAL_CONTINUOUS_FREE_BASE_NUMERICAL_INTEGRATION_FOR_CAD_POSTCHECK'

class PhaseMapping:
    def __init__(self, rows, baseline_duration, candidate_duration):
        if not rows:raise ValueError('No ordered phase intervals')
        self.rows=rows
        self.baseline_knots=np.array([rows[0]['baseline_s'][0]]+[r['baseline_s'][1]for r in rows],float)
        self.candidate_knots=np.array([rows[0]['candidate_s'][0]]+[r['candidate_s'][1]for r in rows],float)
        for key,knots,duration in [('baseline_s',self.baseline_knots,baseline_duration),('candidate_s',self.candidate_knots,candidate_duration)]:
            if not np.isfinite(knots).all() or abs(knots[0])>1e-9 or abs(knots[-1]-duration)>1e-8 or np.any(np.diff(knots)<=0):
                raise ValueError('Phase intervals must cover the full positive-duration trace')
            for i,r in enumerate(rows):
                if not r.get('name') or len(r[key])!=2 or abs(r[key][0]-knots[i])>1e-8:
                    raise ValueError('Phase gap, overlap, reversal, or unnamed interval')

    @staticmethod
    def _interpolate(values,source,target):
        a=np.atleast_1d(np.asarray(values,float))
        if not np.isfinite(a).all() or np.any(a<source[0]-1e-9) or np.any(a>source[-1]+1e-9):
            raise ValueError('Display mapping cannot extrapolate')
        return np.interp(a,source,target)

    def candidate_time(self,baseline_display_time):
        return self._interpolate(baseline_display_time,self.baseline_knots,self.candidate_knots)

    def baseline_time(self,candidate_actual_time):
        return self._interpolate(candidate_actual_time,self.candidate_knots,self.baseline_knots)

def phase_mapping(rows,baseline_duration,candidate_duration):
    return PhaseMapping(rows,baseline_duration,candidate_duration)

def comparison_keys(baseline_actual_times,candidate_actual_times,mapping):
    # All samples from both integrations survive, plus exact time-map boundaries.
    return np.unique(np.r_[baseline_actual_times,mapping.baseline_time(candidate_actual_times),mapping.baseline_knots])

class ActualSeries:
    def __init__(self,trace):
        if trace.get('status')!=ACTUAL_STATUS:raise ValueError('Only actual free-root integration is displayable here')
        self.samples=trace['samples'];self.times=np.array([s['time_s']for s in self.samples],float)
        if len(self.times)<2 or abs(self.times[0])>1e-10 or not np.isfinite(self.times).all() or np.any(np.diff(self.times)<=0):
            raise ValueError('Invalid actual time sequence')
        self.transforms=np.array([s['base_transform_m']for s in self.samples],float)
        if self.transforms.shape!=(len(self.times),4,4) or not np.isfinite(self.transforms).all():raise ValueError('Invalid root transforms')
        R=self.transforms[:,:3,:3]
        if np.max(abs(R.transpose(0,2,1)@R-np.eye(3)))>1e-8 or np.max(abs(np.linalg.det(R)-1))>1e-8 or np.max(abs(self.transforms[:,3,:]-[0,0,0,1]))>1e-10:
            raise ValueError('Actual root transform must be rigid')
        self.joint_names=list(self.samples[0]['q_HOME_delta_deg'])
        if any(set(s['q_HOME_delta_deg'])!=set(self.joint_names)for s in self.samples):raise ValueError('Joint schema changed within trace')
        self.q=np.array([[s['q_HOME_delta_deg'][j]for j in self.joint_names]for s in self.samples],float)
        if not np.isfinite(self.q).all():raise ValueError('Nonfinite joint coordinates')
        self.rotation=Slerp(self.times,Rotation.from_matrix(R))

    def at(self,actual_times):
        t=np.atleast_1d(np.asarray(actual_times,float))
        if not np.isfinite(t).all() or np.any(t<self.times[0]-1e-9) or np.any(t>self.times[-1]+1e-9):raise ValueError('Actual trace cannot be extrapolated')
        t=np.clip(t,self.times[0],self.times[-1]);Ts=np.tile(np.eye(4),(len(t),1,1));Ts[:,:3,:3]=self.rotation(t).as_matrix()
        for axis in range(3):Ts[:,axis,3]=np.interp(t,self.times,self.transforms[:,axis,3])
        qs=np.array([np.interp(t,self.times,self.q[:,i])for i in range(len(self.joint_names))]).T
        indices=np.maximum(0,np.searchsorted(self.times,t,side='right')-1)
        return [dict(time_s=float(ti),q_HOME_delta_deg=dict(zip(self.joint_names,qi.tolist())),base_transform_m=Ti.tolist(),phase=self.samples[ii].get('phase','UNSPECIFIED'),display_interpolation_only=True)for ti,qi,Ti,ii in zip(t,qs,Ts,indices)]
