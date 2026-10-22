"""Eve's head as a Wilds face mesh (Pyra/Mythra method): Eve's face, eyes, teeth, brows and hair skinned to the hunter's
facial bones, with the facial bones moved onto Eve's face. At runtime stellar_eve_outfit_bones.lua swaps the Player_Face
mesh to this file while the Eve outfit is worn and hides the hunter hairstyle.

blender --background <work/wilds-armor/ch03_091_0002.blend> --python build_eve_face.py -- <outfit build dir> <stage root>
needs <outfit build dir>/eve_outfit_bind.json (build_eve_outfit.py) and the outfit mesh in <stage>.

Face rig (game space, head-local = in the head joint frame):
  body bones of the face skeleton (root..Neck_1, Head) = the outfit bind (Eve joint positions, hunter rotations);
  facial bones = hunter head-local offset mapped by A, A(x) = cE + S (x - cH): S per axis from interocular distance (x),
  eye -> teeth height (vertical) and eye -> nose-tip depth (depth), cH / cE = eye midpoints; eyeball bones exactly on
  Eve's eyeball centres. Rotations stay the hunter's.
Weights: Eve skin / brow verts -> A^-1 into hunter head space -> nearest point on the hunter face surface -> barycentric
  blend of that triangle's weights; teeth from the hunter mouth mesh; eyeballs 100 % to the hunter eyeball bone;
  hair 100 % Head (rigid, no physics in v1).
Output: <stage>/natives/stm/stellar/eve27/face/eve27_face.mesh (materials evf00.., mdf2 from build_eve_default_tex.py
  EVE_OUTFIT=face), previews <outfit build dir>/face_*.png.
"""
import bpy, sys, os, json, math, struct
from mathutils import Matrix, Vector, Quaternion
from mathutils.bvhtree import BVHTree
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()

BUILD, STAGE = sys.argv[sys.argv.index('--') + 1:]
import eve_paths as EP
P = EP.WORK
FACE_H = P + 'wilds-hair/natives/stm/art/model/character/ch00/001/0000/ch00_001_0000.mesh.241111606'
EH = P + 'eve-head/SB/Content/Art/Character/PC/CH_P_EVE_Head/CH_P_EVE_Face_Jali3.glb'
HAIR_F = P + 'eve-hair/SB/Content/Art/Character/PC/CH_P_EVE_Hair/CH_P_EVE_Hair_Seperate_001-1/CH_P_EVE_Hair_Seperate_001-1_Hair_V01.glb'
SWORD_F = P + 'eve-sword01-full/SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01/CH_W_Sword_01_Folded.glb'   # hairpin form of Eve's sword
HAIRPIN_FIT = EP.DATA + 'hairpin_fit.json'   # fit_hairpin.py: socket SC_SwordingPoint on the head
BODY = STAGE + '/natives/stm/art/model/character/ch03/002/101/2/ch03_002_1012.mesh.241111606'
OUT = STAGE + '/natives/stm/stellar/eve27/face/eve27_face.mesh.241111606'
# NewMaterial = Eve's eyelashes (strand geometry, no texture): dropped before, the eyes looked bare / too big (user)
KEEP = ['MI_EVE_Head_V02_Jali', 'MI_EyeRefractive1', 'MI_Teeth', 'MI_EyeBrow1', 'MI_EVE_HR_01_TypeA', 'NewMaterial', 'CH_W_Sword_02_Blade_Body']   # = evf00..06 (build_eve_default_tex.py EVE_OUTFIT=face); the ponytail moved to the body part
R90 = Matrix.Rotation(math.radians(90), 4, 'X'); R90i = R90.inverted()
YAW = Matrix.Rotation(math.radians(-90), 4, 'Z')
rep = {}
mesh_col = next(c for c in bpy.data.collections if c.name.endswith('.mesh'))
for o in list(bpy.data.objects):
    if o.type in ('MESH', 'ARMATURE'): bpy.data.objects.remove(o, do_unlink=True)
B = json.load(open(os.path.join(BUILD, 'eve_outfit_bind.json')))
NG = {n: Matrix(m) for n, m in B['bind'].items()}
eve_head_bl = Vector(B['eveHeadBlender'])


def new_objects(fn):
    before = set(bpy.data.objects); fn()
    return [o for o in bpy.data.objects if o not in before]


def restore_raw(path, mesh):
    data = open(path, 'rb').read(); n = struct.unpack_from('<I', data, 12)[0]
    js = json.loads(data[20:20 + n]); off0 = 20 + n + 8
    def acc(i):
        a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
        off = off0 + bv.get('byteOffset', 0) + a.get('byteOffset', 0); st = bv.get('byteStride', 12)
        return [struct.unpack_from('<3f', data, off + k * st) for k in range(a['count'])]
    Pp = []
    for p in js['meshes'][0]['primitives']: Pp += acc(p['attributes']['POSITION'])
    if len(Pp) != len(mesh.data.vertices): return 'count mismatch'
    for v, (x, y, z) in zip(mesh.data.vertices, Pp): v.co = Vector((x, -z, y))
    return 'ok'


def import_glb(path):
    objs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=path))
    arm = next(o for o in objs if o.type == 'ARMATURE')
    me = next(o for o in objs if o.type == 'MESH' and not o.name.startswith('Icosphere'))
    rep.setdefault('raw', {})[os.path.basename(path)] = restore_raw(path, me)
    if me.data.shape_keys: me.shape_key_clear()
    heads = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    mw = me.matrix_world.copy()
    for o in objs:
        if o is not me: bpy.data.objects.remove(o, do_unlink=True)
    me.matrix_world = mw
    for m in list(me.modifiers): me.modifiers.remove(m)
    return me, heads


# ---------------- hunter face (rig, landmarks, weight source) ----------------
hf_objs = new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=FACE_H, files=[{'name': os.path.basename(FACE_H)}], directory=os.path.dirname(FACE_H)))
fa = next(o for o in hf_objs if o.type == 'ARMATURE')
hmeshes = [o for o in hf_objs if o.type == 'MESH']
HF = {b.name: R90i @ fa.matrix_world @ b.matrix_local for b in fa.data.bones}
FPAR = {b.name: (b.parent.name if b.parent else None) for b in fa.data.bones}
def fdepth(n): return 0 if FPAR[n] is None else 1 + fdepth(FPAR[n])
FORDER = sorted(HF, key=fdepth)
def under_head(n):
    while n:
        if n == 'Head': return True
        n = FPAR[n]
    return False
HHi = HF['Head'].inverted(); EHm = NG['Head']; EHi = EHm.inverted()
def h_local(p_blender): return (HHi @ (R90i @ p_blender))        # hunter head-local (game axes)
def e_local(p_blender): return (EHi @ (R90i @ p_blender))
def e_world(x_local): return R90 @ (EHm @ x_local)

def verts_world(o): return [o.matrix_world @ v.co for v in o.data.vertices]
def centroid(ps): return sum(ps, Vector()) / max(1, len(ps))
hmesh = {o.name: o for o in hmeshes}
h_eyeL = next(o for o in hmeshes if 'eye_L' in o.name); h_eyeR = next(o for o in hmeshes if 'eye_R' in o.name)
h_mouth = next(o for o in hmeshes if 'mouth' in o.name)
h_face = [o for o in hmeshes if o.name.endswith('__face')]
def top_group(o):
    acc = {}
    for v in o.data.vertices:
        for g in v.groups: acc[o.vertex_groups[g.group].name] = acc.get(o.vertex_groups[g.group].name, 0) + g.weight
    return max(acc, key=acc.get)
EYEB = {'L': top_group(h_eyeL), 'R': top_group(h_eyeR)}
rep['hunterEyeBones'] = EYEB
hL, hR = h_local(centroid(verts_world(h_eyeL))), h_local(centroid(verts_world(h_eyeR)))
# hunter teeth: the mouth mesh vertices that are inside the lips (behind the front-most mouth points)
hm = [h_local(p) for p in verts_world(h_mouth)]
h_teeth = centroid(hm)
hskin = [h_local(p) for o in h_face for p in verts_world(o)]

# ---------------- Eve head ----------------
face, fheads = import_glb(EH)
hairf, _ = import_glb(HAIR_F)
# hairpin (folded sword) only with EVE_HAIRPIN=1: in game Eve carries the Wilds weapon, the hairpin form is not wanted
hairt = None
if os.environ.get('EVE_HAIRPIN') == '1':
    hairt, _ = import_glb(SWORD_F)
    hairt.matrix_world = Matrix(json.load(open(HAIRPIN_FIT))['best']) @ hairt.matrix_world
for o in [x for x in (face, hairf, hairt) if x]:
    o.matrix_world = YAW @ o.matrix_world
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
face_head = YAW @ fheads['Bip001-Head']; tail_head = face_head
face.data.transform(Matrix.Translation(eve_head_bl - face_head))
hairf.data.transform(Matrix.Translation(eve_head_bl))                    # front hair file is head-local (origin = head)
if hairt: hairt.data.transform(Matrix.Translation(eve_head_bl - tail_head))
rep['faceHeadOffset_cm'] = round((eve_head_bl - face_head).length * 100, 2)
# drop overlay materials (tear line, eye shadow occlusion, eye light, eye blend, teeth occlusion, lash card)
mats = [m.name if m else '' for m in face.data.materials]
drop = {i for i, m in enumerate(mats) if m not in KEEP}
bpy.ops.object.select_all(action='DESELECT'); face.select_set(True); bpy.context.view_layer.objects.active = face
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for p in face.data.polygons: p.select = p.material_index in drop
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='FACE'); bpy.ops.object.mode_set(mode='OBJECT')
rep['faceMaterials'] = mats
mi = {m.name: i for i, m in enumerate(face.data.materials) if m}
def verts_of(mat):
    s = set()
    for p in face.data.polygons:
        if p.material_index == mi.get(mat, -1): s.update(p.vertices)
    return s
eye_v = verts_of('MI_EyeRefractive1'); teeth_v = verts_of('MI_Teeth')
FW = [face.matrix_world @ v.co for v in face.data.vertices]
eL = centroid([FW[i] for i in eye_v if FW[i].x > 0]); eR = centroid([FW[i] for i in eye_v if FW[i].x <= 0])
eL_l, eR_l = e_local(eL), e_local(eR)
e_teeth = e_local(centroid([FW[i] for i in teeth_v]))
skin_v = verts_of('MI_EVE_Head_V02_Jali')
eskin = [e_local(FW[i]) for i in skin_v]

# ---------------- landmark map A (hunter head-local -> Eve head-local) ----------------
cH, cE = (hL + hR) / 2, (eL_l + eR_l) / 2
side = (hL - hR); ax_side = max(range(3), key=lambda i: abs(side[i]))
up_h = cH - h_teeth; ax_up = max((i for i in range(3) if i != ax_side), key=lambda i: abs(up_h[i]))
ax_dep = 3 - ax_side - ax_up
def nose_depth(pts, c, sgn):
    mid = [p for p in pts if abs(p[ax_side] - c[ax_side]) < 0.008]
    return max((p[ax_dep] - c[ax_dep]) * sgn for p in mid)
# forward direction sign along the depth axis: from the head joint towards the eyes
sgn = 1.0 if cH[ax_dep] > 0 else -1.0
S = [1.0, 1.0, 1.0]
S[ax_side] = (eL_l - eR_l)[ax_side] / side[ax_side]
S[ax_up] = (cE - e_teeth)[ax_up] / up_h[ax_up]
S[ax_dep] = nose_depth(eskin, cE, sgn) / nose_depth(hskin, cH, sgn)
# chin: below the teeth the vertical scale comes from teeth -> chin tip (one eye->teeth scale for the whole face mapped
# Eve's chin into the hunter's neck, so the jaw did not carry it when the mouth opened)
def chin(pts, teeth, c):
    front = [p for p in pts if abs(p[ax_side] - c[ax_side]) < 0.008 and (p[ax_dep] - teeth[ax_dep]) * sgn > -0.015 and p[ax_up] < teeth[ax_up]]
    return min(p[ax_up] for p in front)
hC, eC = chin(hskin, h_teeth, cH), chin(eskin, e_teeth, cE)
S_chin = (e_teeth[ax_up] - eC) / (h_teeth[ax_up] - hC)
rep['chinScale'] = round(S_chin, 3); rep['chinUp_cm'] = {'hunter': round(hC * 100, 2), 'eve': round(eC * 100, 2)}
def A(x):
    out = cE + Vector([(x - cH)[i] * S[i] for i in range(3)])
    if x[ax_up] < h_teeth[ax_up]: out[ax_up] = e_teeth[ax_up] + (x[ax_up] - h_teeth[ax_up]) * S_chin
    return out
def Ai(x):
    out = cH + Vector([(x - cE)[i] / S[i] for i in range(3)])
    if x[ax_up] < e_teeth[ax_up]: out[ax_up] = h_teeth[ax_up] + (x[ax_up] - e_teeth[ax_up]) / S_chin
    return out
rep['landmarkScale'] = [round(s, 3) for s in S]; rep['axes'] = {'side': ax_side, 'up': ax_up, 'depth': ax_dep}
rep['eyeMid_cm'] = {'hunter': [round(x * 100, 2) for x in cH], 'eve': [round(x * 100, 2) for x in cE]}

# ---------------- face bind ----------------
FG = {}
for n in FORDER:
    if n in NG and not (under_head(n) and n != 'Head'):
        FG[n] = NG[n].copy(); continue
    if under_head(n):
        L = HHi @ HF[n]
        pos = A(L.translation)
        if n == EYEB['L']: pos = eL_l
        if n == EYEB['R']: pos = eR_l
        FG[n] = EHm @ Matrix.Translation(pos) @ L.to_quaternion().to_matrix().to_4x4()
    else:
        p = FPAR[n]
        FG[n] = (FG[p] @ (HF[p].inverted() @ HF[n])) if p else HF[n].copy()
rep['faceBones'] = len(FG)

# ---------------- weights ----------------
def bvh_of(objs):
    vs, fs, owner = [], [], []
    for o in objs:
        base = len(vs); mw = o.matrix_world
        vs += [mw @ v.co for v in o.data.vertices]
        for p in o.data.polygons:
            for k in range(1, len(p.vertices) - 1):
                fs.append((base + p.vertices[0], base + p.vertices[k], base + p.vertices[k + 1])); owner.append((o, (p.vertices[0], p.vertices[k], p.vertices[k + 1])))
    return BVHTree.FromPolygons(vs, fs), vs, fs, owner
def vweights(o, i):
    return {o.vertex_groups[g.group].name: g.weight for g in o.data.vertices[i].groups if g.weight > 0}
bvh_face, fvs, ffs, fown = bvh_of(h_face)
bvh_mouth, mvs, mfs, mown = bvh_of([h_mouth])
def transfer(p_hunter_bl, tree, vs, fs, own):
    loc, nrm, idx, dist = tree.find_nearest(p_hunter_bl)
    a, b, c = (vs[k] for k in fs[idx]); o, tri = own[idx]
    # barycentric
    v0, v1, v2 = b - a, c - a, loc - a
    d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01 or 1e-12
    wb = (d11 * d20 - d01 * d21) / den; wc = (d00 * d21 - d01 * d20) / den; wa = 1 - wb - wc
    acc = {}
    for w, vi in zip((wa, wb, wc), tri):
        for g, x in vweights(o, vi).items(): acc[g] = acc.get(g, 0) + max(0.0, w) * x
    return acc, dist
for g in list(face.vertex_groups): face.vertex_groups.remove(g)
dist_stats = []
W = {}
for i, p in enumerate(FW):
    if i in eye_v:
        W[i] = {EYEB['L'] if p.x > 0 else EYEB['R']: 1.0}; continue
    hp = R90 @ (HF['Head'] @ Ai(e_local(p)))            # same spot on the hunter's head (Blender world)
    if i in teeth_v:
        acc, d = transfer(hp, bvh_mouth, mvs, mfs, mown)
    else:
        acc, d = transfer(hp, bvh_face, fvs, ffs, fown)
    dist_stats.append(d); W[i] = acc
dist_stats.sort()
rep['transferDist_cm'] = {'median': round(dist_stats[len(dist_stats) // 2] * 100, 2), 'p95': round(dist_stats[int(len(dist_stats) * 0.95)] * 100, 2)}
groups = {}
for i, acc in W.items():
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:6]; tot = sum(w for _, w in top) or 1
    for g, w in top:
        if g not in groups: groups[g] = face.vertex_groups.new(name=g)
        groups[g].add([i], w / tot, 'REPLACE')
for o in [x for x in (hairf, hairt) if x]:
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    g = o.vertex_groups.new(name='Head'); g.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
rep['skinBones'] = len(groups)

# ---------------- export ----------------
for o in hf_objs:
    if o is not fa: o.hide_render = True
bind = fa.copy(); bind.data = fa.data.copy(); bind.name = 'EveFaceBind'; mesh_col.objects.link(bind)
bpy.ops.object.select_all(action='DESELECT'); bind.select_set(True); bpy.context.view_layer.objects.active = bind
bpy.ops.object.mode_set(mode='EDIT')
for eb in bind.data.edit_bones: eb.use_connect = False
for eb in bind.data.edit_bones:
    L = max(eb.length, 0.005); eb.matrix = R90 @ FG[eb.name]; eb.length = L
bpy.ops.object.mode_set(mode='OBJECT')
parts = []
for o in [x for x in (face, hairf, hairt) if x]:
    for c in list(o.users_collection): c.objects.unlink(o)
    mesh_col.objects.link(o)
    while len(o.data.uv_layers) > 1: o.data.uv_layers.remove(o.data.uv_layers[-1])
    for ca in list(o.data.color_attributes): o.data.color_attributes.remove(ca)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='MATERIAL'); bpy.ops.object.mode_set(mode='OBJECT')
objs = [o for o in mesh_col.objects if o.type == 'MESH' and o.data.polygons]
for o in [o for o in mesh_col.objects if o.type == 'MESH' and not o.data.polygons]: bpy.data.objects.remove(o, do_unlink=True)
objs.sort(key=lambda o: KEEP.index(o.data.materials[o.data.polygons[0].material_index].name))
prev = {}
for sub, o in enumerate(objs):
    m = o.data.materials[o.data.polygons[0].material_index]; key = f'evf{KEEP.index(m.name):02d}'
    o.data.materials.clear(); o.data.materials.append(bpy.data.materials.get(key) or bpy.data.materials.new(key))
    o.name = f'Group_0_Sub_{sub}__{key}'; prev[o.name] = key
    o.parent = bind
    for md in list(o.modifiers): o.modifiers.remove(md)
    md = o.modifiers.new('Armature', 'ARMATURE'); md.object = bind
    parts.append(o); rep.setdefault('parts', []).append([o.name, m.name, len(o.data.vertices)])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
rep['export'] = list(bpy.ops.re_mesh.exportfile(filepath=OUT, targetCollection=mesh_col.name, exportAllLODs=False, exportBoundingBoxes=True))

# ---------------- preview ----------------
for o in hmeshes: bpy.data.objects.remove(o, do_unlink=True)
body = new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=BODY, files=[{'name': os.path.basename(BODY)}], directory=os.path.dirname(BODY)))
barm = next(o for o in body if o.type == 'ARMATURE')
TEXD = P + 'eve27-suit/SB/Content/Art/Character/PC/CH_P_EVE_27/Textures/'
HEADT = P + 'eve-head/SB/Content/Art/Character/PC/CH_P_EVE_Head/Textures/'
def img_mat(name, path=None, rgb=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    if path:
        tn = m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(path)
        m.node_tree.links.new(tn.outputs['Color'], m.node_tree.nodes['Principled BSDF'].inputs['Base Color']); m.node_tree.nodes.active = tn
    if rgb:
        m.diffuse_color = rgb + (1,); m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = rgb + (1,)
    return m
BODYT = {'evo00': TEXD + 'EVE_COS_27_BB_A_02.png', 'evo01': TEXD + 'EVE_COS_27_UV01_A.png', 'evo02': TEXD + 'EVE_COS_27_UV02_A.png', 'evo03': TEXD + 'EVE_COS_27_UV03_A.png'}
for o in body:
    if o.type == 'MESH':
        k = o.name.split('__')[-1]
        o.data.materials[0] = img_mat('p_' + k, BODYT.get(k), None if k in BODYT else ((0.10, 0.075, 0.055) if k == 'evo05' else (0.32, 1.0, 1.0)))
FACET = {'evf00': (HEADT + 'Tex_P_EVE_Head_A.png', None), 'evf01': (None, (0.82, 0.8, 0.8)), 'evf02': (None, (0.9, 0.88, 0.84)),
         'evf03': (None, (0.12, 0.09, 0.07)), 'evf04': (None, (0.10, 0.075, 0.055)), 'evf05': (None, (0.03, 0.025, 0.02)), 'evf06': (P + 'eve-sword01-full/SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01/Textures/CH_W_Sword_02_D.png', None)}
for o in parts:
    pth, rgb = FACET[prev[o.name]]
    o.data.materials[0] = img_mat('p_' + prev[o.name], pth if pth and os.path.exists(pth) else None, rgb)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'TEXTURE'; scene.display.shading.show_cavity = True
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(cam); scene.camera = cam
cam.data.type = 'ORTHO'
renders = []
def shot(tag, centre, d, scale, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.data.ortho_scale = scale; cam.location = centre + d * 5
    cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(BUILD, f'face_{tag}.png'); bpy.ops.render.render(write_still=True); renders.append(scene.render.filepath)
FWD, LEFT = Vector((0, -1, 0)), Vector((1, 0, 0))
hc = R90 @ NG['Head'].translation + Vector((0, 0, 0.06))
shot('head_front', hc, FWD, 0.45, (700, 700)); shot('head_34', hc, (FWD + LEFT).normalized(), 0.45, (700, 700))
shot('head_side', hc, LEFT, 0.45, (700, 700)); shot('head_back', hc, -FWD, 0.55, (700, 700))
shot('body_front', Vector((0, 0, 0.85)), FWD, 1.9, (700, 1000)); shot('body_side', Vector((0, 0, 0.85)), LEFT, 1.9, (700, 1000))
# expression check: jaw opened 15 deg about the jaw bone's axis closest to the head's side axis (sign: chin goes down),
# Eve (left) next to the original hunter face (right) with the same rotation
hun = new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=FACE_H, files=[{'name': os.path.basename(FACE_H)}], directory=os.path.dirname(FACE_H)))
harm = next(o for o in hun if o.type == 'ARMATURE')
grey = img_mat('p_hunter', None, (0.75, 0.64, 0.58))
for o in hun:
    if o.type == 'MESH':
        for i in range(len(o.data.materials)): o.data.materials[i] = grey
head_shift = (R90 @ NG['Head'].translation) - (R90 @ HF['Head'].translation)
harm.location = head_shift + Vector((0.26, 0, 0))
JAW = 'C_Jaw_LOD02'
jl = (HHi @ HF[JAW]).to_quaternion().to_matrix()          # jaw orientation in the head frame (hunter; Eve keeps it)
e_side = Vector([1.0 if i == ax_side else 0.0 for i in range(3)])
local_side = jl.transposed() @ e_side
k = max(range(3), key=lambda i: abs(local_side[i])); axis = Vector([0.0] * 3); axis[k] = 1.0
chin_h = Vector([0.0] * 3); chin_h[ax_up] = hC - (HHi @ HF[JAW]).translation[ax_up]; chin_h[ax_dep] = 0.04 * sgn
sign = 1.0
test = (jl @ Quaternion(axis, math.radians(15)).to_matrix() @ jl.transposed()) @ chin_h
if test[ax_up] > chin_h[ax_up]: sign = -1.0
q = Quaternion(axis, math.radians(15 * sign))
rep['jawTest'] = {'localAxis': k, 'sign': sign}
for a_ in (bind, harm):
    for pb in a_.pose.bones: pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()
hc2 = hc + Vector((0.13, 0, 0))
shot('expr_rest_vs_hunter', hc2, FWD, 0.62, (900, 600))
for a_ in (bind, harm):
    if JAW in a_.pose.bones: a_.pose.bones[JAW].rotation_quaternion = q
bpy.context.view_layer.update()
shot('expr_jaw_vs_hunter', hc2, FWD, 0.62, (900, 600))
for a_ in (bind, harm):
    for pb in a_.pose.bones: pb.rotation_quaternion = (1, 0, 0, 0)
rep['renders'] = renders
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, 'eve27_face.blend'))
json.dump(rep, open(os.path.join(BUILD, 'face_report.json'), 'w'), indent=1, default=str)
print('done')
