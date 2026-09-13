"""Floating-base rigid inverse dynamics with explicit, smooth support load sharing.
No root actuation: the solved wrenches are desired contact reactions only.
"""
from quasistatic import *
from scipy.optimize import linprog, minimize
from scipy.linalg import null_space
from itertools import product

class Feedforward(StaticEvaluator):
 def evaluate_dynamic(self,q_deg,base_transform_m,support_links,qvel=None,qacc=None,desired_load_fraction_by_link=None):
  self.set_state(q_deg,base_transform_m);m,d=self.m,self.d
  if qvel is not None:d.qvel[:]=qvel;mujoco.mj_forward(m,d)
  desired=d.qfrc_bias.copy()
  if qacc is not None:
   M=np.zeros((m.nv,m.nv));mujoco.mj_fullM(m,M,d.qM);desired+=M@np.array(qacc)
  Js=[];points=[];polys=[]
  for link in support_links:
   bid=m.body(link).id;R=d.xmat[bid].reshape(3,3);poly=(self.feet[link]-self.pivots[link])@R.T+d.xpos[bid];point=poly.mean(0);jp=np.zeros((3,m.nv));jr=np.zeros((3,m.nv));mujoco.mj_jac(m,d,jp,jr,point,bid);Js.append(np.vstack([jp,jr]));points.append(point);polys.append(poly)
  JT=np.hstack([J.T for J in Js]);H=JT[:6];v=desired[:6];nw=6*len(support_links)
  fractions=None
  if desired_load_fraction_by_link is not None:
   fractions=np.array([desired_load_fraction_by_link.get(l,0) for l in support_links],float)
   if np.any(fractions<0) or abs(sum(fractions)-1)>1e-6:raise ValueError(('INVALID_LOAD_SHARES',fractions))
  if len(support_links)==1:wrench=np.linalg.solve(H,v);allocation='UNIQUE_SINGLE_SUPPORT_WRENCH';E=H;rhs=v
  else:
   A=[];b=[]
   for i,vi in enumerate(self.vids):
    A.append(np.r_[JT[vi],-self.caps[i]]);b.append(desired[vi]);A.append(np.r_[-JT[vi],-self.caps[i]]);b.append(-desired[vi])
   for k,(point,poly) in enumerate(zip(points,polys)):
    # Include unilateral Fz in both LP and quadratic tie break, not just LP bounds.
    row=np.zeros(nw+1);row[k*6+2]=-1;A.append(row);b.append(0)
    # Conservative inscribed L1 cone for both nominal mu=.8 and mu=.5
    # sensitivity; includes torsion .01 m, matching the contact XML.
    for sx,sy,sz in product([-1,1],repeat=3):
     row=np.zeros(nw+1);row[k*6]=sx/.5;row[k*6+1]=sy/.5;row[k*6+5]=sz/.01;row[k*6+2]=-1;A.append(row);b.append(0)
    for ex,ey,off in ConvexHull(poly[:,:2]).equations:
     row=np.zeros(nw+1);row[k*6+2]=ex*point[0]+ey*point[1]+off+.002;row[k*6+3]=ey;row[k*6+4]=-ex;A.append(row);b.append(0)
   E=H.copy();rhs=v.copy()
   if fractions is not None:
    # The root translation columns are world forces; total world Fz is v[2].
    for k in range(len(support_links)-1):
     row=np.zeros(nw);row[k*6+2]=1;E=np.vstack([E,row]);rhs=np.r_[rhs,fractions[k]*v[2]]
   limits=[(None,None)]*nw+[(0,None)]
   sol=linprog(np.r_[np.zeros(nw),1.],A_ub=np.array(A),b_ub=np.array(b),A_eq=np.c_[E,np.zeros(len(E))],b_eq=rhs,bounds=limits,method='highs')
   if not sol.success:raise RuntimeError(('INFEASIBLE_CONTACT_WRENCH_ALLOCATION',sol.message))
   wrench=sol.x[:-1];allocation='DOUBLE_SUPPORT_LOAD_SHARE_MINMAX_MOMENT_LP'
   # Strictly convex tie break in the equilibrium/load-sharing nullspace removes
   # arbitrary opposing internal forces without changing the solved root balance.
   N=null_space(E);w0=E.T@np.linalg.solve(E@E.T,rhs)
   if fractions is None:
    center=d.subtree_com[m.body('trunk_base').id];centers=np.array(points);line=centers[1,:2]-centers[0,:2];f=float(np.clip(np.dot(center[:2]-centers[0,:2],line)/max(np.dot(line,line),1e-12),0,1));fractions=np.array([1-f,f])
   target=np.zeros(nw)
   for k,f in enumerate(fractions):target[6*k+2]=f*v[2]
   weights=np.tile([1,1,.3,40,40,40],len(support_links));upper=max(.8,float(sol.x[-1])+.01);Aw=np.array(A)[:,:nw];bw=np.array(b)-np.array(A)[:,-1]*upper;Az=Aw@N;bz=bw-Aw@w0;z0=N.T@(wrench-w0);W2=weights**2
   objective=lambda z:float(np.sum(W2*(w0+N@z-target)**2))
   jac=lambda z:2*N.T@(W2*(w0+N@z-target))
   opt=minimize(objective,z0,jac=jac,method='SLSQP',constraints=[dict(type='ineq',fun=lambda z:bz-Az@z,jac=lambda z:-Az)],options=dict(maxiter=100,ftol=1e-10))
   if np.min(bz-Az@opt.x)>-1e-6:wrench=w0+N@opt.x;allocation='DOUBLE_SUPPORT_LOAD_SHARE_WITH_QUADRATIC_FORCE_TIEBREAK'
  tau=desired[self.vids]-JT[self.vids]@wrench
  return dict(torque_Nm=dict(zip(self.names,tau.tolist())),support_links=support_links,contact_wrenches=wrench.reshape(-1,6).tolist(),max_utilization=float(np.max(abs(tau)/self.caps)),allocation=allocation,root_equilibrium_residual=float(np.max(abs(H@wrench-v))),all_equalities_residual=float(np.max(abs(E@wrench-rhs))))
