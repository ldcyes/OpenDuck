"""R26 cover-only native CAD intersection and manufacturing readback (mm).

Historical builders are data provenance only and are never executed. The new
outline is the Minkowski sum of a shifted triangle and the original circle.
The installed part is its intersection with each original candidate_v8 STEP.
"""
from pathlib import Path
import sys, json, math, hashlib, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
for rel in ['work/r3-mechanics/python-deps', 'work/r12-motion/python-deps',
            'work/rk-mechanics/python-deps', 'work/r11-integration/mechanics',
            'work/r23-power-integration/integration']:
    sys.path.insert(0, str(ROOT / rel))
import numpy as np
import trimesh
import manifold3d
import common as c
from mesh_print_export import export_indexed
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeVertex
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Pnt, gp_Vec
from OCP.BRepTools import BRepTools
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

OUT = ROOT / 'work/r26-cover-first/mechanics'
BASE = ROOT / 'work/r25-bottom-head-entry/assembly_selection.json'
SHAPE = ROOT / 'work/r18-leg-hip-covers/legs/reference_design/candidate_v3/shape_manifest.json'
FIX = ROOT / 'work/r18-leg-hip-covers/legs/reference_design/candidate_v8/fixing_contract.json'
BASIS = np.array([[1, 0, 0], [0, .08718932367607021, .9961917595708684],
                  [0, .9961917595708684, -.08718932367607021]])
KNEE_Z = -114.964562282
TARGET_Z = KNEE_Z - 10.
BOOL_TOL = 1e-6

def rel(path): return str(Path(path).relative_to(ROOT))
def write_json(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def rounded_prism(centres, radius, z0, z1):
    """Exact tangent lines and circular arcs, without polygonal approximation."""
    centres = np.asarray(centres)
    e0, e1 = centres[1]-centres[0], centres[2]-centres[0]
    if e0[0]*e1[1]-e0[1]*e1[0] < 0:
        centres = centres[::-1]
    edges = np.roll(centres, -1, axis=0) - centres
    normals = np.column_stack((edges[:, 1], -edges[:, 0]))
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    wire = BRepBuilderAPI_MakeWire()
    def point(xy): return gp_Pnt(float(xy[0]), float(xy[1]), z0)
    for i, centre in enumerate(centres):
        n0, n1 = normals[i-1], normals[i]
        a0 = math.atan2(n0[1], n0[0]); a1 = math.atan2(n1[1], n1[0])
        while a1 < a0: a1 += 2*math.pi
        mid = np.array([math.cos((a0+a1)/2), math.sin((a0+a1)/2)])
        arc = GC_MakeArcOfCircle(point(centre+radius*n0), point(centre+radius*mid), point(centre+radius*n1)).Value()
        wire.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
        wire.Add(BRepBuilderAPI_MakeEdge(point(centre+radius*n1), point(centres[(i+1)%3]+radius*n1)).Edge())
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire.Wire()).Face(), gp_Vec(0, 0, z1-z0)).Shape()

def precise_mesh(shape):
    BRepTools.Clean_s(shape)
    BRepMesh_IncrementalMesh(shape, .005, False, .035, False).Perform()
    vv, ff = [], []
    ex = c.TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = c.TopoDS.Face_s(ex.Current()); loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri:
            k = len(vv)
            for i in range(1, tri.NbNodes()+1):
                p = tri.Node(i).Transformed(loc.Transformation()); vv.append([p.X(), p.Y(), p.Z()])
            for i in range(1, tri.NbTriangles()+1):
                ids = list(tri.Triangle(i).Get())
                if face.Orientation() == TopAbs_REVERSED: ids.reverse()
                ff.append([k+j-1 for j in ids])
        ex.Next()
    mesh = trimesh.Trimesh(vv, ff, process=True)
    mesh.merge_vertices(digits_vertex=8)
    f = mesh.faces
    mesh.update_faces((f[:,0]!=f[:,1]) & (f[:,1]!=f[:,2]) & (f[:,0]!=f[:,2]))
    mesh.remove_unreferenced_vertices()
    return mesh

def exact_bounds(shape):
    b = Bnd_Box(); BRepBndLib.AddOptimal_s(shape, b, False, False)
    v = b.Get(); return [list(v[:3]), list(v[3:])]

def edge_distances(shape, basis, outside, uv):
    """Exact hole-axis to outer lateral surface distance at main-wall mid-plane.

    Historical rounded-triangle unions split the planar wall into many faces;
    selecting one face's outer wire would not give the part's exterior outline.
    Planar side faces have normals perpendicular to the extrusion direction.
    Rounded outer sides have radius > 7 mm; hole/pocket/pad cylinders are < 7.
    """
    lateral_faces = []
    ex = c.TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = c.TopoDS.Face_s(ex.Current()); surface = BRepAdaptor_Surface(face)
        if surface.GetType() == GeomAbs_Plane:
            d = surface.Plane().Axis().Direction()
            normal = np.array([d.X(), d.Y(), d.Z()])
            if abs(np.dot(normal, basis[:,2])) < 1e-7:
                lateral_faces.append(face)
        elif surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder(); d = cylinder.Axis().Direction()
            axis = np.array([d.X(), d.Y(), d.Z()])
            if cylinder.Radius()>7 and abs(abs(np.dot(axis,basis[:,2]))-1)<1e-7:
                lateral_faces.append(face)
        ex.Next()
    assert lateral_faces, 'Outer lateral surfaces missing'
    values = []
    for xy in uv:
        p = basis @ np.array([*xy, outside-1])
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
        distances=[]
        for face in lateral_faces:
            query = BRepExtrema_DistShapeShape(vertex, face); query.Perform()
            assert query.IsDone(); distances.append(query.Value())
        values.append(min(distances))
    return values

def mesh_check(mesh, cad_volume):
    status = manifold3d.Manifold(manifold3d.Mesh64(np.asarray(mesh.vertices), np.asarray(mesh.faces, dtype=np.uint64))).status()
    result = dict(watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                  connected_components=len(mesh.split()), volume_mm3=float(mesh.volume),
                  cad_volume_error_mm3=abs(float(mesh.volume)-cad_volume), manifold3d_status=str(status),
                  vertex_count=len(mesh.vertices), face_count=len(mesh.faces), bounds_mm=mesh.bounds.tolist())
    assert result['watertight'] and result['winding_consistent'] and result['connected_components']==1
    assert mesh.volume>0 and status == manifold3d.Error.NoError
    assert result['cad_volume_error_mm3'] < max(.5, cad_volume*.001)
    return result

def fresh_step_audit(new_path, old_path):
    """Each operation gets independently read STEP inputs, with zero fuzzy tolerance."""
    extra = c.volume(c.cut(c.read(new_path), c.read(old_path)))
    overlap = c.volume(c.common(c.read(new_path), c.read(old_path)))
    return dict(new_minus_old_mm3=extra, common_volume_mm3=overlap,
                new_volume_mm3=c.volume(c.read(new_path)), fuzzy_tolerance_mm=0.,
                independent_STEP_reads_per_operation=True)


def subprocess_step_audit(new_path, old_path):
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--audit-step',
                              str(new_path), str(old_path)], text=True, capture_output=True, check=True)
    return json.loads(process.stdout.strip().splitlines()[-1])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assembly = json.loads(BASE.read_text()); original = {p['name']:p for p in assembly['items']}
    shape_manifest = json.loads(SHAPE.read_text()); reference = shape_manifest['parts'][0]
    fixing = json.loads(FIX.read_text()); outside = reference['visible_plane_offset_mm']; inner = outside-2
    centres = np.array(reference['rounded_triangle_centers_uv_mm']); radius=reference['corner_radius_mm']
    new_centres = centres.copy()
    # World z = up_z*v + normal_z*w; the lowest rim is at the outside wall plane.
    new_centres[1,1] = (TARGET_Z - BASIS[2,2]*outside)/BASIS[2,1] + radius
    # Negative control reproduces the fresh-reader defect of nominally coincident
    # old and clipping arcs. The historical triangle strips were rounded to 1e-5
    # mm; reproducing their nominal circle boundary creates tolerance-sensitive
    # seams. Extend the two upper clipping centres 2% along rays away from the
    # new lower centre. The original upper centres then lie inside the clipping
    # triangle, preserving their circular surfaces instead of reclipping them.
    # Actual part remains a native intersection and the original circle radius,
    # target bottom and all mounting geometry are unchanged.
    with tempfile.TemporaryDirectory(prefix='r26-native-regression-') as temporary:
        baseline = original['R18P_L_thigh_photo_triangle']
        unperturbed = c.common(c.read(ROOT/baseline['step']),
            c.tf(rounded_prism(new_centres, radius, inner-2, outside+2), BASIS, [0,0,0]))
        rejected = Path(temporary)/'unperturbed_coincident_contour.step'
        writer=c.STEPControl_Writer(); writer.Transfer(unperturbed,c.STEPControl_AsIs)
        assert writer.Write(str(rejected))==c.IFSelect_RetDone
        negative_control=subprocess_step_audit(rejected,ROOT/baseline['step'])
        negative_control.update(description='Unperturbed clipping centres reproduce fresh-reader coincident-seam failure.',
                                detected=negative_control['new_minus_old_mm3']>BOOL_TOL)
        assert negative_control['detected'], 'Expected fresh-reader regression did not reproduce; investigate geometry kernel changes.'
    new_centres[[0,2]] = new_centres[1] + 1.02*(new_centres[[0,2]]-new_centres[1])
    clip = rounded_prism(new_centres, radius, inner-2, outside+2)
    parts, checks = [], []
    sources = {rel(p):c.sha(p) for p in [BASE, SHAPE, FIX, Path(__file__)]}
    for side, sign in [('L',1), ('R',-1)]:
        oldname = f'R18P_{side}_thigh_photo_triangle'; name=f'R26_{side}_thigh_short_cover'
        src=original[oldname]; srcpath=ROOT/src['step']; assert c.sha(srcpath)==src['step_sha256']
        sources[src['step']] = c.sha(srcpath)
        module=next(q for q in fixing['modules'] if q['side']==side); uv=module['boss_centers_uv_mm']
        basis=np.diag([1,sign,1])@BASIS; old=c.read(srcpath)
        new=c.common(old, c.tf(clip, basis, [0,0,0]))
        info=c.properties(new); assert info['valid_BRep'] and info['solid_count']==1 and info['volume_mm3']>0
        removed=c.cut(old,new); extra=c.volume(c.cut(new,old)); assert abs(extra)<=BOOL_TOL, (side, extra)
        interfaces=[]
        for index, xy in enumerate(uv, 1):
            local=lambda r,z0,z1:c.tf(c.cylinder([*xy,(z0+z1)/2],r,z1-z0,[0,0,1]),basis,[0,0,0])
            # R7 cylinders include every original pad/pocket feature and the complete
            # thickness, not merely a circle at the nominal main wall surface.
            zones={'full_support_R7':local(7,inner-2,outside+2),
                   'full_OD9_pad':local(4.5,outside-.2,outside+.12),
                   'spigot_pocket_and_surround':local(3,inner-.01,inner+.85)}
            zone_checks={}
            for label, zone in zones.items():
                loss=c.volume(c.common(removed,zone)); assert abs(loss)<=BOOL_TOL,(side,index,label,loss)
                before=c.common(old,zone); after=c.common(new,zone)
                symmetric=abs(c.volume(c.cut(before,after)))+abs(c.volume(c.cut(after,before)))
                assert symmetric<=BOOL_TOL,(side,index,label,symmetric)
                zone_checks[label]=dict(removed_volume_mm3=loss,symmetric_difference_mm3=symmetric,
                                       retained_original_volume_mm3=c.volume(before))
            interfaces.append(dict(index=index, centre_uv_mm=xy, axis_HOME_mm=basis[:,2].tolist(),
                centre_at_inner_face_HOME_mm=(basis@np.array([*xy,inner])).tolist(),
                through_hole_diameter_mm=2.7, spigot_pocket_diameter_mm=4.05,
                spigot_pocket_depth_mm=.85, original_spigot_engagement_mm=.8,
                washer_pad_OD_mm=9, washer_pad_raised_height_mm=.12, zones=zone_checks))
        distances=edge_distances(new,basis,outside,uv)
        assert min(distances)>=7-1e-7,(side,distances)
        for row, dist in zip(interfaces,distances):row['centre_to_outer_edge_mm']=dist
        props=c.export(name,new,OUT,'EOS PA2200 / PA12 SLS',.93,src['link_frame'],
                       notes='R26 shorter cover candidate; original installed plane and full mounting interfaces retained.')
        step=OUT/props['STEP']; rb=c.read(step); read_props=c.properties(rb)
        assert read_props['valid_BRep'] and read_props['solid_count']==1
        assert abs(read_props['volume_mm3']-info['volume_mm3'])<1e-5
        fresh_audit=subprocess_step_audit(step,srcpath)
        readback_extra=fresh_audit['new_minus_old_mm3']; assert abs(readback_extra)<=BOOL_TOL
        assert abs(fresh_audit['common_volume_mm3']-fresh_audit['new_volume_mm3'])<=BOOL_TOL
        mesh=precise_mesh(rb); mesh_report=mesh_check(mesh,info['volume_mm3'])
        stl=OUT/props['STL']; stl.write_text(mesh.export(file_type='stl_ascii'))
        stl_rb=trimesh.load(stl,force='mesh'); stl_report=mesh_check(stl_rb,info['volume_mm3'])
        assert abs(stl_rb.volume-mesh.volume)<1e-7
        assert np.max(np.abs(stl_rb.bounds-mesh.bounds))<1e-8
        indexed=export_indexed(mesh,OUT/'print',name)
        exact=exact_bounds(rb); old_exact=exact_bounds(old)
        mesh_bounds_error=float(np.max(np.abs(np.asarray(exact)-mesh.bounds)))
        assert mesh_bounds_error < .01
        mesh_report.update(cad_bounds_max_error_mm=mesh_bounds_error, cad_bounds_tolerance_mm=.01)
        props.update(step=rel(step),mesh=rel(indexed['mesh_path']),manufacturing_file=rel(indexed['manufacturing_path']),
            step_sha256=c.sha(step),mesh_sha256=c.sha(indexed['mesh_path']),manufacturing_sha256=c.sha(indexed['manufacturing_path']),
            sha256_STEP=c.sha(step),sha256_STL=c.sha(stl),stl=rel(stl),mesh_load_process=False,
            R=np.eye(3).tolist(),t_mm=[0,0,0],geometry_scale=[1,1,1],link_frame=src['link_frame'],
            nominal_COM=info['center_mm'],part_role='cover',kind='R26_cover_first_candidate',
            is_new=True,replaces=[oldname],input_group='R26_cover_first',reference_only=False,not_installed=False,
            manufacturing_approved=False,physical_approved=False,display_color_rgba=src['display_color_rgba'],
            interfaces=interfaces,visible_wall_mm=2.,bounds_mm=exact,
            mass_accounting='replace_one_R25_cover_once',source_step=src['step'],source_step_sha256=src['step_sha256'])
        parts.append(props)
        checks.append(dict(name=name,replaces=oldname,valid_BRep=info['valid_BRep'],solid_count=info['solid_count'],
            new_minus_old_mm3=extra,step_readback_new_minus_old_mm3=readback_extra,
            step_readback_volume_error_mm3=abs(read_props['volume_mm3']-info['volume_mm3']),
            fresh_process_STEP_containment=fresh_audit,
            old_volume_mm3=c.volume(old),new_volume_mm3=info['volume_mm3'],removed_volume_mm3=c.volume(removed),
            old_exact_bounds_mm=old_exact,new_exact_bounds_mm=exact,knee_HOME_z_mm=KNEE_Z,
            requested_bottom_z_mm=TARGET_Z,actual_bottom_z_mm=exact[0][2],
            old_extension_below_knee_mm=KNEE_Z-old_exact[0][2],new_extension_below_knee_mm=KNEE_Z-exact[0][2],
            vertical_exposure_gain_mm=exact[0][2]-old_exact[0][2],interfaces=interfaces,
            nominal_main_wall_mm=2.,main_wall_policy='Intersection preserves both original parallel planes; no thickness scaling.',
            mesh=mesh_report,stl_readback=stl_report,indexed_readback=indexed['readback']))
        print('VERIFIED',name,'edge_mm',distances,'bottom_z',exact[0][2],'mass_g',props['mass_from_CAD_g'],flush=True)
    report=dict(status='PASS_NATIVE_COVER_AND_EXPORT_CHECKS',units='mm',boolean_volume_tolerance_mm3=BOOL_TOL,
        mesh_CAD_volume_tolerance='max(0.5 mm3, 0.1% CAD volume)',sources=sources,parts=checks,
        fresh_reader_negative_control=negative_control,
        construction=dict(upper_clipping_centres_ray_extension_factor=1.02,original_centres_uv_mm=centres.tolist(),new_centres_uv_mm=new_centres.tolist(),
            bottom_corner_shift_v_mm=float(new_centres[1,1]-centres[1,1]),corner_radius_mm=radius,
            main_wall_mm=2.,outside_plane_offset_mm=outside,method='Native intersection with exact line-and-circle rounded triangular prism.'),
        lateral_inset=dict(applied_mm=0,examined_mm=4,original_spigot_engagement_mm=.8,
            reason='Moving the skin 4 mm inward changes its locating pocket and seating plane relative to fixed bridge, spigots, washers and screws. Original engagement is only 0.8 mm; bridge redesign and screw-stack validation required. This revision preserves the installed plane.'),
        manufacturing_approved=False,physical_approved=False)
    write_json(OUT/'geometry_checks.json',report)
    write_json(OUT/'manifest.json',dict(status='R26_COVER_FIRST_ENGINEERING_CANDIDATE',parts=parts,sources=sources,
        geometry_checks=rel(OUT/'geometry_checks.json'),manufacturing_approved=False,physical_approved=False))

if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--audit-step':
        print(json.dumps(fresh_step_audit(sys.argv[2],sys.argv[3])))
    else: main()
