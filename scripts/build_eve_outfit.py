"""One Eve outfit as a Wilds innerwear replacement, LUA-Bone-System style: hunter bone names and rest ORIENTATIONS,
Eve's joint POSITIONS (bone lengths). The runtime sets those joint local positions before the motion runs
(stellar_eve_outfit_bones.lua), so the hunter's own motions (rotation-only on body joints) drive an Eve-proportioned body.

blender --background <work/wilds-armor/ch03_091_0002.blend> --python build_eve_outfit.py -- <outfit glb> <stage root> <report.json>

Steps
 1. Eve outfit glb (bind = rest, raw positions restored), turned to face -Y like the Wilds rig.
 2. Re-pose Eve's arms, hands, fingers and legs so every segment points the way the hunter's rest segment points
    (swing only, lengths kept); feet/toes keep Eve's high-heel angle, spine/neck/head keep Eve's posture.
 3. New skeleton (game space, Y up): Wilds_Female_Reference bones; mapped bones get Eve's joint position + the hunter's
    rest rotation; Hip = Eve mid-thigh + the hunter's hip-to-thigh offset (COG stays at the hunter height, so the motion's
    COG track lifts Eve to her own standing height); Neck_1 / *_Shin placed along their segment by the hunter fraction;
    everything else keeps the hunter's local offset to its (moved) parent.
 4. Eve weights -> hunter bone names (53 mapped bones, twist helpers split along the limb, other helpers / frills merged
    into the nearest mapped ancestor), max 6 influences.
 5. Export natives/stm/art/model/character/ch03/002/101/2/ch03_002_1012.mesh (body part = whole outfit), and 4-vertex
    hidden meshes for parts 1 (arms), 4 (legs), 5 (waist pouch/knife) of the same innerwear. Part 6 (slinger) untouched.
 6. eve_outfit_joints.json: joint local positions for the runtime (LUA Bone System json format: {joint: {x,y,z}}).
 7. Preview: rest and hunter motion poses (plc_female idle/jog/sprint, wp03 dodge/attacks) applied by forward kinematics to
    Eve (new skeleton) and, next to her, the hunter in the original innerwear (original skeleton). No foot IK in the preview.
"""
import bpy, sys, os, json, math, struct
import mathutils
from mathutils import Matrix, Vector, Quaternion
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()

outfit_glb, STAGE, REPORT = sys.argv[sys.argv.index('--') + 1:]
OUTD = os.path.dirname(REPORT)
import eve_paths as EP
ROOT = EP.ROOT
P = EP.WORK
# EVE_OUTFIT_ID: which Eve outfit on which default look "outfit beta" (type 2 = 101 Ocean Maid, type 1 = 100 Wave Diver Bikini)
OUTFITS = {
    '27': dict(sub='101', name='eve27', pfx='evo', toeExtra='-12', lift='0', keys=['MI_EVE_Cos_27_BB_02', 'MI_EVE_Cos_27_01', 'MI_EVE_Cos_27_02', 'MI_EVE_Cos_27_03', 'MI_EVE_Cos_27_Glow'],
               texd='eve27-suit/SB/Content/Art/Character/PC/CH_P_EVE_27/Textures/',
               base={'MI_EVE_Cos_27_BB_02': 'EVE_COS_27_BB_A_02', 'MI_EVE_Cos_27_01': 'EVE_COS_27_UV01_A', 'MI_EVE_Cos_27_02': 'EVE_COS_27_UV02_A', 'MI_EVE_Cos_27_03': 'EVE_COS_27_UV03_A'},
               hide={1: ['ch03_002_1011_arm_UseSC', 'skin'], 4: ['ch03_002_1014_leg_UseSC', 'ch03_002_1014_leg_toe_UseSC', 'skin'],
                     5: ['cage', 'ch03_002_1015_wst_UseSC', 'knife']}),
    '63': dict(sub='100', name='eve63', pfx='evb', bust='1.25', lift='0.6', toeExtra='-12', shoulderBlend='0', shoulderXfer='1.0', keys=['MI_Basebody_V02_F1', 'MI_CH_P_EVE_63_Suit', 'MI_CH_P_EVE_43'],
               texd='eve63-suit/SB/Content/Art/Character/PC/',
               base={'MI_Basebody_V02_F1': 'CH_P_EVE_ReferenceBody/Textures/CH_EVE_BaseBody_V02_F1_A', 'MI_CH_P_EVE_63_Suit': 'CH_P_EVE_63/Textures/CH_P_EVE_63_A',
                     'MI_CH_P_EVE_43': 'CH_P_EVE_43/TexTures/CH_P_EVE_43_A'},
               hide={1: ['ch03_002_1001_arm_UseSC', 'skin'], 4: ['ch03_002_1004_leg_UseSC', 'ch03_002_1004_leg_toe_UseSC', 'ch03_002_1004_leg_trn_UseSC', 'skin'],
                     5: ['cage', 'ch03_002_1005_waist_UseSC', 'knife']}),
    # Racer's High (CH_P_EVE_41) on Mizutsune beta ch03/066/001, split by part (user 10-18): body part 2 = jacket/top +
    # waist band, arms part 1, legs part 4; helm part 3 and waist part 5 hidden (Eve face/hair via Lua). The innerwear
    # type 2 (101) stays the template for skeleton / bust jiggle / shoulder weights; only the output files change.
    '41': dict(sub='101', name='eve41', pfx='evr', odir='ch03/066/001', opre='ch03_066_001',
               split={2: ('body', 'waist', 'head'), 1: ('arm',), 4: ('leg',)}, toeExtra='0',   # closed boots: no toe lift (user 10-18: feet odd)
               neckFrom=('eve63-suit/SB/Content/Art/Character/PC/CH_P_EVE_63/CH_P_EVE_63.glb', 'MI_Basebody_V02_F1', 'MI_Basebody_V02_F2'),
               keys=['MI_CH_P_EVE_41_Upper', 'MI_CH_P_EVE_41_Lower', 'MI_Basebody_V02_F2', 'MI_CH_P_EVE_41_Emissive'],
               texd='eve41-suit/SB/Content/Art/Character/PC/',
               base={'MI_CH_P_EVE_41_Upper': 'CH_P_EVE_41/Textures/CH_P_EVE_41_Upper_A', 'MI_CH_P_EVE_41_Lower': 'CH_P_EVE_41/Textures/CH_P_EVE_41_Lower_A',
                     'MI_Basebody_V02_F2': 'CH_P_EVE_ReferenceBody/Textures/CH_EVE_BaseBody_V02_F2_A'},
               # hidden parts without the fur-shell / hair materials (user 10-18: the waist part's shellfer made sparkly noise
               # round Eve); their mdf2 is the original one minus those materials (written next to the mesh)
               hide={3: ['ch03_066_0010_helm_UseSC'], 5: ['cage', 'ch03_066_0010_waist_UseSC']},
               emptyGpuc=[5]),   # part 5 has GPU cloth (gpuc) for the skirt: on the hidden mesh it drew black streaks (user 10-18)
    # Daily Mascot (CH_P_EVE_18) on Rey Dau gamma ch03/021/301 (sheet: ch03/021/0301), split like Racer's High (user 10-18).
    # The part has no chain2 / gpuc of its own; the helm keeps only its plain material (no vector-emit VFX material).
    '18': dict(sub='101', name='eve18', pfx='evm', odir='ch03/021/301', opre='ch03_021_301',
               split={2: ('body', 'waist', 'head'), 1: ('arm',), 4: ('leg',)},
               keys=['MI_Basebody_V02_F3', 'MI_EVE_Cos_18_01', 'MI_EVE_Cos_18_02'],
               texd='eve18-suit/SB/Content/Art/Character/PC/',
               base={'MI_Basebody_V02_F3': 'CH_P_EVE_ReferenceBody/Textures/CH_EVE_BaseBody_V02_F2_A',
                     'MI_EVE_Cos_18_01': 'CH_P_EVE_18/Textures/EVE_Cos_18_01_A', 'MI_EVE_Cos_18_02': 'CH_P_EVE_18/Textures/EVE_Cos_18_02_A'},
               hide={3: ['ch03_021_3013_helm_UseSC'],
                     5: ['cage', 'ch03_021_3015_knife', 'ch03_021_3015_knife_UseSC', 'ch03_021_3015_waist02_UseSC', 'ch03_021_3015_waist_UseSC']}),
    # Moran with stockings (CH_P_EVE_34_body) on Nu Udra gamma ch03/027/301 (sheet: ch03/027/0301), split like Racer's High
    # (user 10-18). The helm / waist materials are all vector-emit VFX shaders: the hidden parts use the plain 'cage'
    # material instead (their mdf2 = the waist's original mdf2 cut down to 'cage', written next to each); the waist part
    # also has two knife meshes (_0 / _9) -- hidden as well. The body has no chain2 of its own: Lua CHAIN_FIX.
    '34': dict(sub='101', name='eve34', pfx='evn', odir='ch03/027/301', opre='ch03_027_301',   # bust: the common default (user 10-18: every Eve outfit like the existing ones)
               split={2: ('body', 'waist', 'head'), 1: ('arm',), 4: ('leg',)},
               # clean seams (user 10-18: body / legs not clearly split, dress hem / stocking band jagged): the dress and its
               # laces stay whole on the body part, the skin / stockings are cut by one horizontal line (zcut)
               bodyMats=['MI_CH_P_EVE_34_Suit', 'MI_CH_P_EVE_34_ACC'], zcut=True, zcutUp='0.06',
               # dress panels: no physics (user 10-18: swinging panels looked wrong, Daily Mascot's plain skinning looks fine);
               # each panel bone follows the pelvis at the top and more of its own side's thigh further down
               skirtThigh=['Ab-L-SkirtA', 'Ab-R-SkirtA', 'Ab-L-SkirtC', 'Ab-R-SkirtC'],
               # the white panties sat on top of the black stockings (SB paints the stockings on the skin, the panties are
               # their own mesh): drop them -- the stockings show under the dress (user 10-18)
               dropIslands=[('MI_CH_P_EVE_34_ACC', 0.90, 1.10, 0.12)],
               keys=['MI_CH_P_EVE_34_BB', 'MI_CH_P_EVE_34_Suit', 'MI_CH_P_EVE_34_ACC'],
               texd='eve34-suit/SB/Content/Art/Character/PC/',
               base={'MI_CH_P_EVE_34_BB': 'CH_P_EVE_34/Textures/CH_P_EVE_29_BB_Addd', 'MI_CH_P_EVE_34_Suit': 'CH_P_EVE_34/Textures/CH_P_EVE_34_Cloth_A'},
               hide={3: ['cage'], 5: ['cage']},
               hideExtra={'5/ch03_027_3015_0': ['ch03_027_3015_knife'], '5/ch03_027_3015_9': ['ch03_027_3015_knife']}),
}
if os.environ.get('EVE_OUTFIT_JSON'):
    # night batch (10-18): outfit settings from a json file written by make_eve_auto.py (same keys as OUTFITS entries;
    # numeric part keys come back as ints)
    def _ik(d): return {(int(k) if isinstance(k, str) and k.isdigit() else k): v for k, v in d.items()}
    OC = json.load(open(os.environ['EVE_OUTFIT_JSON'], encoding='utf-8'))
    for _k in ('split', 'hide', 'hideExtra'):
        if _k in OC: OC[_k] = _ik(OC[_k])
    if 'neckFrom' in OC: OC['neckFrom'] = tuple(OC['neckFrom'])
    if 'dropIslands' in OC: OC['dropIslands'] = [tuple(x) for x in OC['dropIslands']]
else:
    OC = OUTFITS[os.environ.get('EVE_OUTFIT_ID', '27')]
SUB = OC['sub']                                   # ch03/002/<SUB>, part files ch03_002_<SUB><n>
INNER = P + f'wilds-inner{SUB}/natives/stm/art/model/character/ch03/002/{SUB}/'
FACE = P + 'wilds-hair/natives/stm/art/model/character/ch00/001/0000/ch00_001_0000.mesh.241111606'
POSES = P + 'motion-analysis/poses/'
PART_DIR = STAGE + '/natives/stm/art/model/character/' + OC.get('odir', f'ch03/002/{SUB}') + '/'
OPRE = OC.get('opre', f'ch03_002_{SUB}')     # output part file prefix: <OPRE><part>.mesh
PFX = os.environ.get('EVE_MAT_PREFIX', OC.get('pfx', 'evo'))   # must match the outfit's mdf (10-18: bikini rebuilt with evo = whole body invisible)
KEYS = OC['keys'] + ['MI_EVE_HR_01_Tail_TypeA', 'CH_W_Sword_02_Blade_Body']   # same order as build_eve_default_tex.py EVE_OUTFIT=<id> (ponytail, folded-sword hair ornament last)
# ownHair: another Stellar Blade character (Scarlet) whose hair is in her own mesh -> no Eve ponytail / hairpin; the two
# Eve keys stay in KEYS (unused) so material numbering and the texture builder keep their order
OWN_HAIR = bool(OC.get('ownHair'))
R90 = Matrix.Rotation(math.radians(90), 4, 'X')   # game Y up -> Blender Z up (RE Mesh Editor armature space)
R90i = R90.inverted()
report = {}
mesh_col = next(c for c in bpy.data.collections if c.name.endswith('.mesh'))
for o in list(bpy.data.objects):
    if o.type in ('MESH', 'ARMATURE'):
        bpy.data.objects.remove(o, do_unlink=True)


def restore_raw_positions(path, mesh):
    """glTF importer re-skins vertices into its guessed rest pose (mirrored helper bones break it); bind = rest here, so put
    the file's own positions / normals back (same vertex order). Same as build_eve_default.py."""
    data = open(path, 'rb').read(); n = struct.unpack_from('<I', data, 12)[0]
    js = json.loads(data[20:20 + n]); bin_off = 20 + n + 8
    def acc(i):
        a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
        off = bin_off + bv.get('byteOffset', 0) + a.get('byteOffset', 0); st = bv.get('byteStride', 12)
        return [struct.unpack_from('<3f', data, off + k * st) for k in range(a['count'])]
    Pp, Nn = [], []
    for p in js['meshes'][0]['primitives']:
        Pp += acc(p['attributes']['POSITION']); Nn += acc(p['attributes']['NORMAL']) if 'NORMAL' in p['attributes'] else []
    me = mesh.data
    if len(Pp) != len(me.vertices):
        report['rawRestore'] = 'count mismatch %d/%d' % (len(Pp), len(me.vertices)); return
    moved = 0
    for v, (x, y, z) in zip(me.vertices, Pp):
        c = Vector((x, -z, y))
        if (v.co - c).length > 1e-5: moved += 1; v.co = c
    if len(Nn) == len(Pp):
        me.normals_split_custom_set_from_vertices([Vector((x, -z, y)).normalized() for x, y, z in Nn])
    report['rawRestore'] = moved


def new_objects(fn):
    before = set(bpy.data.objects); fn()
    return [o for o in bpy.data.objects if o not in before]


# ---------------- 1. Eve outfit ----------------
objs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=outfit_glb))
arm = next(o for o in objs if o.type == 'ARMATURE')
suit = next(o for o in objs if o.type == 'MESH' and not o.name.startswith('Icosphere'))
for o in objs:
    if o not in (arm, suit): bpy.data.objects.remove(o, do_unlink=True)
restore_raw_positions(outfit_glb, suit)
if suit.data.shape_keys: suit.shape_key_clear()
# faces without a material are SB's low-poly cloth simulation proxies (never drawn there); exported they showed as a plain
# grey sleeve-shaped sheet sticking out past YoRHa uniform 1's sleeves (user 10-20) -> always dropped
_nomat = {i for i, m in enumerate(suit.data.materials) if m is None or m.name.split('.')[0] == 'None'}
if OC.get('dropMats') or _nomat:
    import bmesh as _bmx
    _di = {i for i, m in enumerate(suit.data.materials) if m and m.name.split('.')[0] in OC.get('dropMats', [])} | _nomat
    _b = _bmx.new(); _b.from_mesh(suit.data)
    _kill = [f for f in _b.faces if f.material_index in _di]; report['dropMatFaces'] = len(_kill)
    _bmx.ops.delete(_b, geom=_kill, context='FACES'); _bmx.ops.delete(_b, geom=[v for v in _b.verts if not v.link_faces], context='VERTS')
    _b.to_mesh(suit.data); _b.free()
# drop whole loose pieces of a material inside a height band, centred (raw glb space: Eve faces +X, Y lateral)
if OC.get('dropIslands'):
    import bmesh as _bmd
    _b = _bmd.new(); _b.from_mesh(suit.data); _b.faces.ensure_lookup_table()
    _mn = {m.name.split('.')[0]: i for i, m in enumerate(suit.data.materials) if m}
    _seen = set(); _kill = []
    for f in _b.faces:
        if f.index in _seen: continue
        stack = [f]; comp = []; _seen.add(f.index)
        while stack:
            g = stack.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in _seen: _seen.add(h.index); stack.append(h)
        vs = {v for g in comp for v in g.verts}
        zs = [(suit.matrix_world @ v.co).z for v in vs]; ys = [(suit.matrix_world @ v.co).y for v in vs]
        for mat, z0, z1, lat in OC['dropIslands']:
            if comp[0].material_index == _mn.get(mat, -1) and min(zs) >= z0 and max(zs) <= z1 and abs(sum(ys) / len(ys)) < lat:
                _kill += comp; break
    report['dropIslandFaces'] = len(_kill)
    _bmd.ops.delete(_b, geom=_kill, context='FACES')
    _bmd.ops.delete(_b, geom=[v for v in _b.verts if not v.link_faces], context='VERTS')
    _b.to_mesh(suit.data); _b.free()
# neck skin (user 10-18, Racer's High in game: long thin neck): this outfit's body skin stops under the hood collar, so
# only the face mesh's thin neck showed. Take the neck skin of another Eve body (same Eve skeleton / bind) and join it.
if OC.get('neckAuto') and OC.get('skinMat') and not OC.get('neckFrom'):
    # graft the neck only when this outfit's own skin has (almost) no neck (Racer's High case)
    _a0 = next(o for o in objs if o.type == 'ARMATURE')
    _nk = _a0.matrix_world @ _a0.data.bones['Bip001-Neck'].head_local; _hd = _a0.matrix_world @ _a0.data.bones['Bip001-Head'].head_local
    _si0 = [i for i, m in enumerate(suit.data.materials) if m and m.name.split('.')[0] == OC['skinMat']]
    _cnt = 0
    for f in suit.data.polygons:
        if f.material_index in _si0:
            c = suit.matrix_world @ f.center
            if _nk.z - 0.02 < c.z < _hd.z and ((c.x - _nk.x) ** 2 + (c.y - _nk.y) ** 2) ** 0.5 < 0.085: _cnt += 1
    report['neckSkinFaces'] = _cnt
    if _cnt < 150: OC['neckFrom'] = ('eve63-suit/SB/Content/Art/Character/PC/CH_P_EVE_63/CH_P_EVE_63.glb', 'MI_Basebody_V02_F1', OC['skinMat'])
if OC.get('neckFrom'):
    _glb, _srcmat, _dstmat = OC['neckFrom']
    _objs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=P + _glb))
    _nm = next(o for o in _objs if o.type == 'MESH' and not o.name.startswith('Icosphere'))
    restore_raw_positions(P + _glb, _nm)
    if _nm.data.shape_keys: _nm.shape_key_clear()
    _arm = next(o for o in objs if o.type == 'ARMATURE')
    _neck = _arm.matrix_world @ _arm.data.bones['Bip001-Neck'].head_local
    _head = _arm.matrix_world @ _arm.data.bones['Bip001-Head'].head_local
    _si = next(i for i, m in enumerate(_nm.data.materials) if m and m.name.split('.')[0] == _srcmat)
    import bmesh as _bm_
    _b = _bm_.new(); _b.from_mesh(_nm.data)
    _z0 = _neck.z - float(os.environ.get('EVE_NECK_DOWN', OC.get('neckDown', '0.05')))
    def _keep(f):
        if f.material_index != _si: return False
        c = _nm.matrix_world @ f.calc_center_median()
        return _z0 < c.z < _head.z + 0.02 and ((c.x - _neck.x) ** 2 + (c.y - _neck.y) ** 2) ** 0.5 < 0.085
    _bm_.ops.delete(_b, geom=[f for f in _b.faces if not _keep(f)], context='FACES')
    _b.to_mesh(_nm.data); _b.free()
    _dst = next(i for i, m in enumerate(suit.data.materials) if m and m.name.split('.')[0] == _dstmat)
    _nm.data.materials.clear(); _nm.data.materials.append(suit.data.materials[_dst])
    report['neckGraft'] = len(_nm.data.vertices)
    for o in _objs:
        if o is not _nm: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT'); _nm.select_set(True); suit.select_set(True); bpy.context.view_layer.objects.active = suit
    bpy.ops.object.join()
orig_mats = [m for m in suit.data.materials]
# The glTF importer leaves the bones whose bind it cannot express (mirrored, negative scale: Dm-R-Breast-Point,
# Ab-R-Deltoid, Ab-R-Venter ...) posed away from their rest. With the raw (bind) positions restored, that pose collapsed
# the right breast / shoulder / belly when the limb re-pose was baked through the armature modifier. Start from rest.
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
report['outfitMaterials'] = [m.name for m in orig_mats]
# Eve faces +X; Wilds faces -Y: yaw -90
arm.matrix_world = Matrix.Rotation(math.radians(-90), 4, 'Z') @ arm.matrix_world
bpy.context.view_layer.update()
for o in (arm, suit):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
mod = next((m for m in suit.modifiers if m.type == 'ARMATURE'), None) or suit.modifiers.new('Armature', 'ARMATURE')
mod.object = arm
SPLIT_PARTS = OC.get('split')
if SPLIT_PARTS:
    def _cat(name):
        b = arm.data.bones.get(name)
        if 'Cape' in name or 'Mantle' in name: return 'body'   # capes hang from the shoulder but belong to the body part (10-19)
        while b:
            n = b.name
            if n.startswith('Bip001') and 'Head' in n: return 'head'
            if n.startswith('Bip001') and any(k in n for k in ('UpperArm', 'Forearm', 'Hand', 'Finger')): return 'arm'
            if n.startswith('Bip001') and any(k in n for k in ('Thigh', 'Calf', 'Foot', 'Toe')): return 'leg'
            if n in ('Bip001-Pelvis', 'Bip001-Spine'): return 'waist'
            if n.startswith('Bip001-Spine') or 'Neck' in n or 'Clavicle' in n: return 'body'
            b = b.parent
        return 'waist'
    _gc = {g.index: _cat(g.name) for g in suit.vertex_groups}
    _z = lambda n: (arm.matrix_world @ arm.data.bones[n].head_local).z
    _ztop, _zbot = _z('Bip001-Spine1'), _z('Bip001-L-Thigh') - 0.15
    _vc = []
    for v in suit.data.vertices:
        a_ = {}
        for g in v.groups: a_[_gc.get(g.group, 'waist')] = a_.get(_gc.get(g.group, 'waist'), 0) + g.weight
        c_ = max(a_, key=a_.get) if a_ else 'waist'
        _vz = (suit.matrix_world @ v.co).z
        if c_ in ('leg', 'body') and _zbot < _vz < _ztop: c_ = 'waist'
        elif c_ == 'waist' and _vz <= _zbot: c_ = 'leg'   # 10-18 Moran: back of the legs on helper bones fell back to 'waist'
        _vc.append(c_)
    _par = list(range(len(_vc)))
    def _f(x):
        while _par[x] != x: _par[x] = _par[_par[x]]; x = _par[x]
        return x
    for e in suit.data.edges:
        a_, b_ = _f(e.vertices[0]), _f(e.vertices[1])
        if a_ != b_: _par[a_] = b_
    _isl = {}
    for i in range(len(_vc)): _isl.setdefault(_f(i), []).append(i)
    _zs = [(suit.matrix_world @ v.co).z for v in suit.data.vertices]
    for vs in _isl.values():
        # small loose pieces only: a long thin shell (Moran's stocking layer, hip to ankle) must not take one part (10-18)
        if len(vs) < 3000 and max(_zs[i] for i in vs) - min(_zs[i] for i in vs) < 0.3:
            cnt = {}
            for i in vs: cnt[_vc[i]] = cnt.get(_vc[i], 0) + 1
            c_ = max(cnt, key=cnt.get)
            for i in vs: _vc[i] = c_
    if OC.get('bodyMats') or OC.get('zcut'):
        _bm = {i for i, m in enumerate(suit.data.materials) if m and m.name.split('.')[0] in OC.get('bodyMats', [])}
        _zknee = _z('Bip001-L-Calf')
        _zcut = _zbot + float(OC.get('zcutUp', 0))   # skin seam hidden under the dress hem
        # user 10-18: a step across the buttocks -- the seam ran through the butt-jiggle area; put it under that area
        _hg = {g.index for g in suit.vertex_groups if 'Hip-Reg' in g.name or 'Butt' in g.name or g.name.endswith('-Hip')}
        _hz = [_zs[v.index] for v in suit.data.vertices if any(g.group in _hg and g.weight > 0.05 for g in v.groups)]
        if _hz: _zcut = min(_zcut, min(_hz) - 0.01)
        _onbody = set()
        for f in suit.data.polygons:
            if f.material_index in _bm: _onbody.update(f.vertices)
        for i in range(len(_vc)):
            if _vc[i] == 'arm': continue
            if i in _onbody and _zs[i] > _zknee: _vc[i] = 'body'   # above the knee only: shoes share the dress material
            elif OC.get('zcut'): _vc[i] = 'leg' if _zs[i] <= _zcut else ('waist' if _zs[i] < _ztop else _vc[i] if _vc[i] != 'leg' else 'waist')
        report['seamRule'] = {'bodyMatVerts': len(_onbody), 'zcut': round(_zcut, 3)}
    P2N = {c: n for n, cs in SPLIT_PARTS.items() for c in cs}
    at = suit.data.attributes.new('evepart', 'INT', 'POINT')
    for i, c_ in enumerate(_vc): at.data[i].value = P2N.get(c_, 2)
    report['splitVerts'] = {n: sum(1 for c_ in _vc if P2N.get(c_, 2) == n) for n in SPLIT_PARTS}

# bigger bust (user request): scale the breast region about its base ring; the mask is Eve's own breast-helper weights,
# so skin and the outfit cups grow together. EVE_BUST_SCALE (default 1.25).
# seam weld (user 10-19 in game: skin pieces split apart where they meet -- chest, armpit; worse on some outfits): SB
# bodies come in several skin pieces whose border vertices sit on the same spot twice. The bust growth, shoulder / knee
# weight transfer and limb girth work vertex by vertex and treated the two copies differently, so the border opened in
# motion. Coincident vertices get one weld id now; after the shape edits they get one position, before export one weight set.
from mathutils.kdtree import KDTree as _KDw
_kw = _KDw(len(suit.data.vertices))
for v in suit.data.vertices: _kw.insert(v.co, v.index)
_kw.balance()
_wid = [-1] * len(suit.data.vertices); _nw = 0
for v in suit.data.vertices:
    if _wid[v.index] >= 0: continue
    near = [i for _, i, _ in _kw.find_range(v.co, float(OC.get('weldDist', 0.0003)))]
    if len(near) > 1:
        for i in near:
            if _wid[i] < 0: _wid[i] = _nw
        _nw += 1
_wa = suit.data.attributes.new('weldid', 'INT', 'POINT')
for i, w in enumerate(_wid): _wa.data[i].value = w + 1   # 0 = none (also the default for meshes joined later)
report['weldGroups'] = _nw
def weld_groups():
    g = {}
    for i, d in enumerate(suit.data.attributes['weldid'].data):
        if d.value > 0: g.setdefault(d.value, []).append(i)
    return [l for l in g.values() if len(l) > 1]
EW_PRE = {n: arm.matrix_world @ b.head_local for n, b in arm.data.bones.items()}
BUST = float(os.environ.get('EVE_BUST_SCALE', OC.get('bust', '1.25') if OC.get('bust', '1.25') != 'match' else '1.25'))   # user 10-18: 1.25 for every Eve outfit   # per outfit: same look as Ocean Maid (user 10-18)
gi = {g.index: g.name for g in suit.vertex_groups}
def breast_w(v, s_):
    return min(1.0, sum(g.weight for g in v.groups if gi[g.group] in (f'Ab-{s_}-Breast', f'Ab-{s_}-Breast-Link', f'Dm-{s_}-Breast', f'Dm-{s_}-Breast-Point')))
# user 10-18: every Eve outfit's bust should look like Ocean Maid's (type 2). Projection = how far the bust stands out in
# front of the waist (Eve faces -Y here, before the yaw). Ocean Maid keeps scale 1.25 and is the reference (EVE_BUST_TARGET, measured from
# it); other outfits solve their own scale so their projection matches.
_zw = [v.co for v in suit.data.vertices if 1.05 < v.co.z < 1.12 and abs(v.co.x) < 0.2]
waist_y = min(q.y for q in _zw) if _zw else 0.0
# one growth field for every layer (user 10-19, Moran in game: the dress tore open between the breasts): SB gives each cloth
# layer its own breast weights, so stacked panels grew by different amounts and split. Cloth vertices take the breast weight
# of the nearest body-skin vertex (within 3 cm) instead, so skin and every layer above it grow together.
from mathutils.kdtree import KDTree as _KDb
_skb = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
        any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
_vmb = {}
for f in suit.data.polygons:
    for vi in f.vertices: _vmb.setdefault(vi, f.material_index)
_skv = [v for v in suit.data.vertices if _vmb.get(v.index) in _skb]
_BWF = {}
if _skv and OC.get('bustField', True):
    _kb = _KDb(len(_skv))
    for i, v in enumerate(_skv): _kb.insert(v.co, i)
    _kb.balance()
    for s_ in 'LR':
        sw = [breast_w(v, s_) for v in _skv]
        for v in suit.data.vertices:
            if _vmb.get(v.index) in _skb: continue
            co, i, d = _kb.find(v.co)
            if i is not None and d < 0.03: _BWF[(v.index, s_)] = sw[i]
def breast_wf(v, s_):
    return _BWF.get((v.index, s_), breast_w(v, s_))
report['bustField'] = len(_BWF) // 2
bust_parts = {}
for s_ in 'LR':
    ring = [v.co.copy() for v in suit.data.vertices if 0.05 < breast_w(v, s_) < 0.3]
    core = [(v, v.co.copy(), breast_wf(v, s_)) for v in suit.data.vertices if breast_wf(v, s_) > 0.01]
    if ring: bust_parts[s_] = (sum(ring, Vector()) / len(ring), core)
def bust_proj(scale):
    best = 9.0
    for c, core in bust_parts.values():
        for v, co, w in core:
            best = min(best, (c + (co - c) * (1 + (scale - 1) * w)).y)
    return waist_y - best
if OC.get('bust', '1.25') == 'match' and bust_parts and not os.environ.get('EVE_BUST_SCALE'):
    target = float(os.environ.get('EVE_BUST_TARGET', '0.0575'))   # Ocean Maid's projection after its 1.25 scale
    lo_, hi_ = 0.8, 2.5
    for _ in range(40):
        mid = (lo_ + hi_) / 2
        if bust_proj(mid) < target: lo_ = mid
        else: hi_ = mid
    BUST = round((lo_ + hi_) / 2, 3)
# user 10-18 (bikini 1.395x): "too big, looks saggy" -- uniform growth about the centre pushes the lower half DOWN.
# EVE_BUST_LIFT (0..1): that share of the downward growth below the centre is not applied, so the bust grows forward/out
# but its underside stays where it was (1 = no drop at all).
LIFT = float(os.environ.get('EVE_BUST_LIFT', OC.get('lift', '0.6')))   # user 10-18: default for every new Eve outfit
# bust growth mask (user 10-19, Omega: the 1.25 bust came out dented in the middle and lumpy): Eve's breast helper weights
# are uneven across the surface, so growing by them dents / bumps the cups. 'radial' mode: a smooth falloff from the
# breast centre instead (full inside 60 % of the breast radius, fading to 0 at its edge)
BUST_MODE = os.environ.get('EVE_BUST_MODE', OC.get('bustMode', 'weights'))
_brad = {}
for s_, (c, core) in bust_parts.items():
    _ds = sorted(((co - c).length for v, co, w in core if w > 0.3))
    _brad[s_] = _ds[int(len(_ds) * 0.95)] if _ds else 0.1
def _radial_w(s_, c, co):
    t_ = (co - c).length / max(_brad[s_] * 1.15, 1e-3)
    if t_ >= 1: return 0.0
    t_ = max(0.0, (t_ - 0.6) / 0.4); return 1 - t_ * t_ * (3 - 2 * t_)
def bust_move(c, co, w):
    f = 1 + (BUST - 1) * w
    n = c + (co - c) * f
    if LIFT > 0 and co.z < c.z: n.z = co.z + (n.z - co.z) * (1 - LIFT)
    n.x = co.x + (n.x - co.x) * min(1.0, abs(co.x) / float(OC.get('bustMidline', '0.025')))
    return n
bust_info = {'projBefore_m': round(bust_proj(1.0), 4), 'projAfter_m': round(bust_proj(BUST), 4), 'lift': LIFT}
_BACC = {}
for s_, (c, core) in bust_parts.items():
    if BUST_MODE == 'radial':
        for v in suit.data.vertices:
            w = _radial_w(s_, c, v.co)
            if w > 0 and (v.co.x - 0) * (c.x - 0) >= -0.0001: v.co = bust_move(c, v.co.copy(), w)
    else:
        # both sides add their move (10-19: the R pass overwrote the L one -- cloth bridging the cleavage, Moran, tore)
        for v, co, w in core:
            _bd = bust_move(c, co, w) - co
            _bacc = _BACC.setdefault(v.index, [co, Vector()]); _bacc[1] += _bd
    bust_info[s_] = {'center': [round(x, 3) for x in c], 'verts': len(core)}
for _vi, (_co, _d) in _BACC.items(): suit.data.vertices[_vi].co = _co + _d
report['bust'] = {'scale': BUST, **bust_info}
# shoulder strap crease (user 10-19, Omega): smooth the cloth over the top of each shoulder (between neck and arm),
# keeping the overall shape; OC shoulderSmooth = iterations
# jagged seams (user 10-19: saw-tooth edges where cloth meets skin -- armpit, thigh band, sleeve edge): the skin under a
# cloth edge lies at (or pokes through) the cloth surface, so its triangles z-fight with the cloth and show as teeth.
# Every skin vertex covered by cloth (or by a smaller overlapping skin piece) within 'seamBand' is pushed 'seamDepth'
# behind that surface, so the cloth edge reads as a clean line.
SEAM_D = float(os.environ.get('EVE_SEAM_DEPTH', OC.get('seamDepth', '0')))   # 10-19: seam push off by default (it broke frills / pushed skin through cloth)
if SEAM_D > 0:
    from mathutils.bvhtree import BVHTree
    import bmesh as _bmz
    _skz = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
            any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    if _skz:
        _bz = _bmz.new(); _bz.from_mesh(suit.data); _bz.faces.ensure_lookup_table(); _bz.verts.ensure_lookup_table()
        # skin islands: the largest is the body, smaller ones (outfit skin pieces) count as covers
        _isl = {}; _nid = 0
        for f in _bz.faces:
            if f.material_index not in _skz or f.index in _isl: continue
            stack = [f]; _isl[f.index] = _nid
            while stack:
                g = stack.pop()
                for e in g.edges:
                    for h in e.link_faces:
                        if h.material_index in _skz and h.index not in _isl: _isl[h.index] = _nid; stack.append(h)
            _nid += 1
        _cnt = {}
        for fi, k in _isl.items(): _cnt[k] = _cnt.get(k, 0) + 1
        _main = max(_cnt, key=_cnt.get) if _cnt else -1
        cover = _bmz.new(); cover.from_mesh(suit.data)
        cover.faces.ensure_lookup_table()
        _bmz.ops.delete(cover, geom=[f for f in cover.faces if (f.material_index in _skz and _isl.get(f.index) == _main)], context='FACES')
        _bvh = BVHTree.FromBMesh(cover); cover.free()
        _band = float(OC.get('seamBand', 0.004)); _n = 0
        _mainv = {v.index for f in _bz.faces if _isl.get(f.index) == _main for v in f.verts}
        for vi in _mainv:
            v = suit.data.vertices[vi]
            hit = _bvh.find_nearest(v.co, 0.02)
            if hit[0] is None: continue
            p_, n_ = hit[0], hit[1].normalized(); dv = v.co - p_
            depth = dv.dot(n_); lat = (dv - n_ * depth).length
            if lat > 0.003 or depth < -0.015 or depth > _band: continue
            v.co = p_ - n_ * SEAM_D + (dv - n_ * depth); _n += 1
        _bz.free()
        report['seamPush'] = _n
# collar clearance (user 10-20, Racer's High: the face mesh's neck showed between the hood folds at the collarbones):
# around the neck base, cloth lying on / inside the skin surface is lifted to OC collarClear metres outside it, so the
# face mesh's lower neck (same surface) stays hidden behind the cloth
if OC.get('collarClear'):
    from mathutils.bvhtree import BVHTree
    import bmesh as _bmq
    _skq = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
            any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    _bq = _bmq.new(); _bq.from_mesh(suit.data)
    _bmq.ops.delete(_bq, geom=[f for f in _bq.faces if f.material_index not in _skq], context='FACES')
    _bvq = BVHTree.FromBMesh(_bq); _bq.free()
    _vmq = {}
    for f in suit.data.polygons:
        for vi in f.vertices: _vmq.setdefault(vi, f.material_index)
    _nk = EW_PRE.get('Bip001-Neck'); _off = float(OC['collarClear']); _nq = 0
    for v in suit.data.vertices:
        if _vmq.get(v.index) in _skq or _nk is None: continue
        if not (_nk.z - 0.06 < v.co.z < _nk.z + 0.08): continue
        hit = _bvq.find_nearest(v.co, 0.03)
        if hit[0] is None: continue
        nrm = hit[1].normalized(); d_ = (v.co - hit[0]).dot(nrm)
        if d_ < _off * 0.5: v.co = v.co + nrm * (_off - d_); _nq += 1   # only cloth that touches / sinks into the skin
    report['collarClear'] = _nq
# skin under cloth (user 10-19 in game: cracks where cloth meets skin -- bikini chest, armpits of Gothura / Harvest /
# Orion, Ceremonial chest): the game's skinning moves the body skin and the cloth a little differently, so skin lying just
# under the cloth pokes through in motion. Body-skin faces fully covered by opaque cloth (a ray along each vertex normal
# hits cloth within EVE_SKIN_CULL m) are deleted, so there is nothing left under the cloth to poke through. Faces at a
# cloth edge (partly covered) stay, so no hole shows. See-through layers (veil, lace, hair) do not count as cover.
SKC = float(os.environ.get('EVE_SKIN_CULL', OC.get('skinCull', '0.012')))   # 3 cm reached the arm / sleeve at the armpit (hole, 10-19)
if SKC > 0:
    from mathutils.bvhtree import BVHTree
    import bmesh as _bmc
    _skc = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
            any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    _see = tuple(OC.get('skinCullSkip', [])) + ('Plastic', 'Veil', 'veil', 'Cape', 'HR_', 'Hair', 'lace', 'Lace', 'Glass', 'Emissive', 'Decal', 'decal')
    _thru = {i for i, m in enumerate(suit.data.materials) if m and any(k in m.name for k in _see)}
    if _skc:
        _bc = _bmc.new(); _bc.from_mesh(suit.data); _bc.faces.ensure_lookup_table(); _bc.verts.ensure_lookup_table()
        _isl = {}; _nid = 0
        for f in _bc.faces:
            if f.material_index not in _skc or f.index in _isl: continue
            stack = [f]; _isl[f.index] = _nid
            while stack:
                g = stack.pop()
                for e in g.edges:
                    for h in e.link_faces:
                        if h.material_index in _skc and h.index not in _isl: _isl[h.index] = _nid; stack.append(h)
            _nid += 1
        _cnt = {}
        for fi, k in _isl.items(): _cnt[k] = _cnt.get(k, 0) + 1
        _main = max(_cnt, key=_cnt.get) if _cnt else -1
        cov = _bmc.new(); cov.from_mesh(suit.data); cov.faces.ensure_lookup_table()
        _bmc.ops.delete(cov, geom=[f for f in cov.faces if f.material_index in _skc or f.material_index in _thru], context='FACES')   # skin pieces never count as cover
        _bvc = BVHTree.FromBMesh(cov); cov.free()
        _covered = {}
        def _cv(v):
            if v.index not in _covered:
                n_ = v.normal.normalized()
                hit = _bvc.ray_cast(v.co + n_ * 0.0005, n_, SKC)
                # cover = a cloth layer lying along the skin (normals agree), not an arm or sleeve crossing in front
                _covered[v.index] = hit[0] is not None and abs(hit[1].normalized().dot(n_)) > 0.7
            return _covered[v.index]
        # every skin piece, not only the main body (10-20, Racer's High: the grafted neck skin showed through the hood folds)
        _del = [f for f in _bc.faces if (f.index in _isl if OC.get('skinCullAll') else _isl.get(f.index) == _main) and all(_cv(v) for v in f.verts)]
        _bmc.ops.delete(_bc, geom=_del, context='FACES')
        _bc.to_mesh(suit.data); suit.data.update(); _bc.free()
        report['skinCull'] = len(_del)
if OC.get('shoulderFlat'):
    # (smoothing collapsed the strap, 10-19) In SB the strap lies as a flat band over the shoulder (runtime cloth settles
    # the gathered hood). Lay the cloth on top of each shoulder onto the skin surface + offset, fading out at the edge.
    from mathutils.bvhtree import BVHTree
    import bmesh as _bms
    _skn = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
            any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    _sb = _bms.new(); _sb.from_mesh(suit.data)
    _bms.ops.delete(_sb, geom=[f for f in _sb.faces if f.material_index not in _skn], context='FACES')
    _bvh = BVHTree.FromBMesh(_sb); _sb.free()
    _vm = {}
    for f in suit.data.polygons:
        for vi in f.vertices: _vm.setdefault(vi, f.material_index)
    _R = float(OC.get('shoulderR', 0.08)); _off = float(OC.get('shoulderOff', 0.004)); _n = 0
    for s_ in 'LR':
        cl = EW_PRE.get(f'Bip001-{s_}-Clavicle'); ua = EW_PRE.get(f'Bip001-{s_}-UpperArm')
        if cl is None or ua is None: continue
        c_ = cl * 0.4 + ua * 0.6; c_.z += 0.03
        for v in suit.data.vertices:
            if _vm.get(v.index) in _skn: continue
            d_ = (v.co - c_).length
            if d_ >= _R: continue
            hit = _bvh.find_nearest(v.co)
            if hit[0] is None or hit[3] > 0.05: continue
            nrm = hit[1].normalized()
            tgt = hit[0] + nrm * _off
            if (v.co - hit[0]).dot(nrm) < _off * 0.5 and (v.co - tgt).length < 0.002: continue
            t_ = d_ / _R; w = 1 - t_ * t_ * (3 - 2 * t_)
            v.co = v.co.lerp(tgt, w); _n += 1
    report['shoulderFlat'] = _n
# cleavage under clothes (user 10-19, Breakcat: the larger bust left the suit sunk deep between the breasts -- cloth would
# bridge the gap): cloth vertices (not skin) in front between the two breast centres are pulled toward the line joining
# the breast fronts at the same height, EVE_CLEAVAGE_FILL of the way (1 at the midline, fading out at the breast centre)
CF = float(os.environ.get('EVE_CLEAVAGE_FILL', OC.get('cleavageFill', '0.6')))
if OC.get('skinUnderCloth') and bust_parts:
    from mathutils.kdtree import KDTree
    _sk = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
           any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    _vm = {}
    for f in suit.data.polygons:
        for vi in f.vertices: _vm.setdefault(vi, f.material_index)
    suit.data.update()
    _cl = [v for v in suit.data.vertices if _vm.get(v.index) not in _sk and v.co.z > 1.0]
    _kd = KDTree(len(_cl))
    for i, v in enumerate(_cl): _kd.insert(v.co, i)
    _kd.balance(); _np = 0
    for v in suit.data.vertices:
        if _vm.get(v.index) not in _sk or max(breast_w(v, 'L'), breast_w(v, 'R')) < 0.01: continue
        if abs(v.co.x) < float(OC.get('skinUnderClothMinX', 0.06)): continue   # not the cleavage / lace V (10-19: holes there)
        co, i, d = _kd.find(v.co)
        if d > 0.03: continue
        cv = _cl[i]; nrm = cv.normal
        depth = (v.co - cv.co).dot(nrm)
        if depth > -0.004:
            v.co = v.co - nrm * (depth + 0.004); _np += 1
    report['skinUnderCloth'] = _np
if CF > 0 and len(bust_parts) == 2:
    _skin = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
             any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
    _cz = sum(c.z for c, _ in bust_parts.values()) / 2; _cy = sum(c.y for c, _ in bust_parts.values()) / 2
    _cx = sum(abs(c.x) for c, _ in bust_parts.values()) / 2
    _vm = {}
    for f in suit.data.polygons:
        for vi in f.vertices: _vm.setdefault(vi, f.material_index)
    _cl = [v for v in suit.data.vertices if _vm.get(v.index) not in _skin and abs(v.co.z - _cz) < 0.11 and v.co.y < _cy + 0.03]
    env = {}
    for v in _cl:
        if 0.5 * _cx < abs(v.co.x) < 1.4 * _cx:
            k = int((v.co.z - _cz) * 100); env[k] = min(env.get(k, 9.0), v.co.y)
    # smooth the envelope over height (1 cm bins were noisy -> bumps)
    ks = sorted(env); env = {k: sum(env[j] for j in ks if abs(j - k) <= 2) / sum(1 for j in ks if abs(j - k) <= 2) for k in ks}
    disp = {}
    for v in _cl:
        if abs(v.co.x) >= _cx: continue
        k = int((v.co.z - _cz) * 100)
        if k not in env: continue
        tgt = env[k] + 0.012
        if v.co.y <= tgt: continue
        t_ = 1 - abs(v.co.x) / _cx; zf = max(0.0, 1 - abs(v.co.z - _cz) / 0.11)
        disp[v.index] = (tgt - v.co.y) * CF * (t_ * t_ * (3 - 2 * t_)) * zf
    # cloth vertices touching skin (the top edge of a strapless top) stay put, else the skin shows behind (user 10-19, Cyber Bunny)
    _edge = set()
    for f in suit.data.polygons:
        if f.material_index in _skin:
            for f2v in f.vertices: _edge.add(f2v)
    _ring = set(i for i in disp if i in _edge)
    for _ in range(2):
        nxt = set()
        for e in suit.data.edges:
            a_, b_ = e.vertices
            if a_ in _ring and b_ in disp: nxt.add(b_)
            if b_ in _ring and a_ in disp: nxt.add(a_)
        _ring |= nxt
    for i in _ring: disp[i] = 0.0
    # relax the displacement along the mesh (moved and neighbouring cloth vertices) so the fabric stays smooth
    nb = {}
    for e in suit.data.edges:
        a_, b_ = e.vertices
        if a_ in disp or b_ in disp: nb.setdefault(a_, []).append(b_); nb.setdefault(b_, []).append(a_)
    for _ in range(6):
        disp = {i: 0.5 * disp.get(i, 0.0) + 0.5 * sum(disp.get(j, 0.0) for j in nb[i]) / len(nb[i]) for i in nb}
    for i, d in disp.items():
        if d < 0: suit.data.vertices[i].co.y += d
    moved = len(disp)
    report['cleavageFill'] = {'k': CF, 'moved': moved, 'cloth': len(_cl)}

# hunter reference rig (rest = the game's bind, armature space = Blender world, identity object matrix)
with bpy.data.libraries.load(P + 'wilds-reference/eve-and-wilds-rigs.blend', link=False) as (src, dst):
    dst.objects = ['Wilds_Female_Reference']
ref = dst.objects[0]; bpy.context.scene.collection.objects.link(ref)
assert ref.matrix_world == Matrix.Identity(4)
HW = {b.name: b.matrix_local.copy() for b in ref.data.bones}          # Blender world
HG = {n: R90i @ m for n, m in HW.items()}                             # game world
HPAR = {b.name: (b.parent.name if b.parent else None) for b in ref.data.bones}
def depth(n): return 0 if HPAR[n] is None else 1 + depth(HPAR[n])
HORDER = sorted(HW, key=depth)

E2W = {'Root': 'root', 'Bip001': 'COG', 'Bip001-Pelvis': 'Hip', 'Bip001-Spine': 'Spine_0', 'Bip001-Spine1': 'Spine_1',
       'Bip001-Spine2': 'Spine_2', 'Bip001-Neck': 'Neck_0', 'Bip001-Head': 'Head'}
FING = [('Thumb', 0), ('IndexF', 1), ('MiddleF', 2), ('RingF', 3), ('PinkyF', 4)]
for s in 'LR':
    for w, e in [('Shoulder', 'Clavicle'), ('UpperArm', 'UpperArm'), ('Forearm', 'Forearm'), ('Hand', 'Hand'),
                 ('Thigh', 'Thigh'), ('Knee', 'Calf'), ('Foot', 'Foot'), ('Toe', 'Toe0')]:
        E2W[f'Bip001-{s}-{e}'] = f'{s}_{w}'
    for f, i in FING:
        for j, suf in [(1, ''), (2, '1'), (3, '2')]:
            E2W[f'Bip001-{s}-Finger{i}{suf}'] = f'{s}_{f}{j}'
E2W = {k: v for k, v in E2W.items() if k in arm.data.bones and v in HW}
W2E = {v: k for k, v in E2W.items()}
report['mappedBones'] = len(E2W)

# ---------------- 2. re-pose limbs to the hunter's rest directions ----------------
PAIRS = []
for s in 'LR':
    PAIRS += [(f'{s}_Thigh', f'{s}_Knee'), (f'{s}_Knee', f'{s}_Foot'),
              (f'{s}_UpperArm', f'{s}_Forearm'), (f'{s}_Forearm', f'{s}_Hand'), (f'{s}_Hand', f'{s}_MiddleF1')]
    for f, _ in FING:
        PAIRS += [(f'{s}_{f}1', f'{s}_{f}2'), (f'{s}_{f}2', f'{s}_{f}3')]
    PAIRS += [(f'{s}_Foot', f'{s}_Toe')]
# feet: Eve's rest foot is in high heels (toes far below the ankle); with the hunter's ankle motion on top the swinging
# foot pointed down too far (user). Turn the foot EVE_FOOT_ALIGN (default 0.5) of the way to the hunter's flat foot.
FOOT_ALIGN = float(os.environ.get('EVE_FOOT_ALIGN', '0.7'))
# EVE_FOOT_MODE=flat (default): instead of a fixed fraction, turn the foot (about the ankle, pitch only) until the sandal's
# sole is level, like the hunter's flat shoe: the 0.7 fraction left the heel up and the walking foot pointed down (user, game).
FOOT_MODE = os.environ.get('EVE_FOOT_MODE', 'orig')   # user 10-18: original SB foot angle, forefoot on the ground


def sole_pitch(s, parts=('Foot', 'Toe')):
    dg = bpy.context.evaluated_depsgraph_get(); ev = suit.evaluated_get(dg).data
    gi = {suit.vertex_groups[n].index for n in (W2E.get(f'{s}_{p_}') for p_ in parts) if n and n in suit.vertex_groups}
    pts = [suit.matrix_world @ ev.vertices[v.index].co for v in suit.data.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)]
    ys = [p.y for p in pts]; y0, y1 = min(ys), max(ys); nb = 14; low = {}
    for p in pts:
        k = min(nb - 1, int((p.y - y0) / (y1 - y0 + 1e-9) * nb)); low[k] = min(low.get(k, 9.0), p.z)
    use = [(y0 + (k + 0.5) * (y1 - y0) / nb, z) for k, z in low.items() if 1 <= k <= nb - 2]
    my = sum(y for y, _ in use) / len(use); mz = sum(z for _, z in use) / len(use)
    m = sum((y - my) * (z - mz) for y, z in use) / sum((y - my) ** 2 for y, _ in use)
    return math.atan(m)          # >0: sole rises toward the heel (+Y, Eve faces -Y)


PAIRS = [(a, b) for a, b in PAIRS if a in W2E and b in W2E]
PAIRS.sort(key=lambda ab: depth(ab[0]))
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
repose = {}
for a, b in PAIRS:
    pa, pbn = arm.pose.bones[W2E[a]], arm.pose.bones[W2E[b]]
    h = arm.matrix_world @ pa.head; c = arm.matrix_world @ pbn.head
    de = c - h; dh = HW[b].translation - HW[a].translation
    rot = de.rotation_difference(dh)
    if a.endswith('_Foot'):
        if FOOT_MODE == 'orig':
            rot = Quaternion()          # Eve's original foot angle (heel up as in SB); only the toes are laid flat below
            # user 10-18 (Ocean Maid sandal in game, sole 35.6 deg): "too bent, at least level it" -> EVE_FOOT_FRAC of the turn
            # that levels the heel-to-ball sole (0 = original SB angle, 1 = level like flat2)
            FFRAC = float(os.environ.get('EVE_FOOT_FRAC', OC.get('footFrac', '0')))
            if FFRAC > 0:
                pitch = sole_pitch(a[0], ('Foot',)); rot = Quaternion((1.0, 0.0, 0.0), -pitch * FFRAC)
                report.setdefault('footFracDeg', {})[a] = round(math.degrees(pitch * FFRAC), 1)
        elif FOOT_MODE in ('flat', 'flat2'):
            pitch = sole_pitch(a[0], ('Foot',) if FOOT_MODE == 'flat2' else ('Foot', 'Toe')); rot = Quaternion((1.0, 0.0, 0.0), -pitch)
            report.setdefault('solePitchDeg', {})[a] = round(math.degrees(pitch), 1)
        else:
            rot = Quaternion().slerp(rot, FOOT_ALIGN)
    repose[a] = round(math.degrees(rot.angle), 1)
    M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ rot.to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
    pa.matrix = M @ pa.matrix
    bpy.context.view_layer.update()
report['reposeDeg'] = repose
# the sole is not one straight line (toe spring): a few more small turns until it is level.
# flat2: level only the heel-to-ball part (Foot-weighted sole), then turn the toe joint so the toe part lies flat too
# (levelling the whole sole as one line turned the ankle 53 deg and lifted the toes -- user: looks wrong)
FOOT_PARTS = ('Foot',) if FOOT_MODE == 'flat2' else ('Foot', 'Toe')
if FOOT_MODE in ('flat', 'flat2'):
    for f in 'LR':
        if f'{f}_Foot' not in W2E: continue
        for _ in range(4):
            pitch = sole_pitch(f, FOOT_PARTS)
            if abs(pitch) < math.radians(0.5): break
            pa = arm.pose.bones[W2E[f'{f}_Foot']]; h = arm.matrix_world @ pa.head
            M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
            pa.matrix = M @ pa.matrix; bpy.context.view_layer.update()
            report['solePitchDeg'][f'{f}_Foot'] = round(report['solePitchDeg'][f'{f}_Foot'] + math.degrees(pitch), 1)
if FOOT_MODE in ('flat2', 'orig'):
    for f in 'LR':
        if f'{f}_Toe' not in W2E: continue
        for _ in range(4):
            pitch = sole_pitch(f, ('Toe',))
            if abs(pitch) < math.radians(0.5): break
            pt = arm.pose.bones[W2E[f'{f}_Toe']]; h = arm.matrix_world @ pt.head
            M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
            pt.matrix = M @ pt.matrix; bpy.context.view_layer.update()
            report.setdefault('toePitchDeg', {})[f] = round(report.get('toePitchDeg', {}).get(f, 0) + math.degrees(pitch), 1)
# user 10-18: "shape of the half step (frac 0.5) is right, but the angle is off -- the sole must lie on the ground": keep
# that foot shape and turn the WHOLE foot (toes follow) about the ankle until the whole sole (heel..toe) is level.
# EVE_FOOT_LEVEL is the share of that turn (1 = level; user 10-18 picked "only a bit": heel stays up, forefoot flatter)
FLEVEL = float(os.environ.get('EVE_FOOT_LEVEL', OC.get('footLevel', '0')))
if FOOT_MODE == 'orig' and FLEVEL > 0:
    for f in 'LR':
        if f'{f}_Foot' not in W2E: continue
        full = sole_pitch(f, ('Foot', 'Toe'))
        for _ in range(6 if FLEVEL >= 1 else 1):
            pitch = sole_pitch(f, ('Foot', 'Toe')) if FLEVEL >= 1 else full * FLEVEL
            if abs(pitch) < math.radians(0.5): break
            pa = arm.pose.bones[W2E[f'{f}_Foot']]; h = arm.matrix_world @ pa.head
            M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
            pa.matrix = M @ pa.matrix; bpy.context.view_layer.update()
            report.setdefault('footLevelDeg', {})[f] = round(report.get('footLevelDeg', {}).get(f, 0) + math.degrees(pitch), 1)
    # partial turn: lay the toe sole flat on the ground again (the forefoot pad touches, heel stays up)
    if FLEVEL < 1:
        for f in 'LR':
            if f'{f}_Toe' not in W2E: continue
            for _ in range(4):
                pitch = sole_pitch(f, ('Toe',))
                if abs(pitch) < math.radians(0.5): break
                pt = arm.pose.bones[W2E[f'{f}_Toe']]; h = arm.matrix_world @ pt.head
                M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
                pt.matrix = M @ pt.matrix; bpy.context.view_layer.update()
                report.setdefault('toePitchDeg2', {})[f] = round(report.get('toePitchDeg2', {}).get(f, 0) + math.degrees(pitch), 1)
# user 10-18 (own edited picture): "not the foot, not the ankle -- the TOES": raise the toe joint EVE_TOE_EXTRA degrees more
# than the automatic toe step, so the sandal's front sole under the toes lies flat on the ground (foot / ankle unchanged).
_te = os.environ.get('EVE_TOE_EXTRA', OC.get('toeExtra', '-12'))
if _te == 'auto':
    # sandals (skin toes visible) get the -12 toe lift, closed shoes / boots 0 (Racer's High boots, user 10-18)
    _gt = {g.index for g in suit.vertex_groups if g.name in ('Bip001-L-Toe0', 'Bip001-R-Toe0')}
    _sk = {i for i, m in enumerate(suit.data.materials) if m and m.name.split('.')[0] == OC.get('skinMat')}
    _tot = _skc = 0
    for f in suit.data.polygons:
        vs = [suit.data.vertices[i] for i in f.vertices]
        if any(any(g.group in _gt and g.weight > 0.3 for g in v.groups) for v in vs):
            _tot += 1; _skc += f.material_index in _sk
    _te = '-12' if _tot and _skc / _tot > 0.3 else '0'
    report['toeAuto'] = [_tot, _skc, _te]
TOE_EXTRA = float(_te)   # user 10-18: default for every new Eve outfit
if TOE_EXTRA:
    for f in 'LR':
        if f'{f}_Toe' not in W2E: continue
        pt = arm.pose.bones[W2E[f'{f}_Toe']]; h = arm.matrix_world @ pt.head
        M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -math.radians(TOE_EXTRA)).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
        pt.matrix = M @ pt.matrix; bpy.context.view_layer.update()
    report['toeExtraDeg'] = TOE_EXTRA
# heelGround (Scarlet's tall block heels, user 10-25: "the toes still float -- the front must lie flat on the floor"): her heel
# is taller than the levelled foot allows, so the ball of the foot hung in the air. Turn the whole foot toes-down about the
# ankle until the forefoot's lowest point is level with the heel's, then lay the toe part flat (twice: each step moves the other)
def _foot_lows(f):
    dg = bpy.context.evaluated_depsgraph_get(); ev = suit.evaluated_get(dg).data
    gi = {suit.vertex_groups[n].index for n in (W2E.get(f'{f}_Foot'), W2E.get(f'{f}_Toe')) if n and n in suit.vertex_groups}
    ay = (arm.matrix_world @ arm.pose.bones[W2E[f'{f}_Foot']].head).y
    pts = [suit.matrix_world @ ev.vertices[v.index].co for v in suit.data.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)]
    return min((p.z for p in pts if p.y < ay - 0.05), default=0.0), min((p.z for p in pts if p.y > ay), default=0.0)
if OC.get('heelGround'):
    _hg = OC['heelGround']
    for f in 'LR':
        if f'{f}_Foot' not in W2E or f'{f}_Toe' not in W2E: continue
        if not isinstance(_hg, bool):
            # a number: turn the foot exactly that many degrees toes-down (user 10-25 picks from previews), then the toe flat
            pa = arm.pose.bones[W2E[f'{f}_Foot']]; h = arm.matrix_world @ pa.head
            M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), math.radians(float(_hg))).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
            pa.matrix = M @ pa.matrix; bpy.context.view_layer.update()
            for _ in range(4):
                pitch = sole_pitch(f, ('Toe',))
                if abs(pitch) < math.radians(0.5): break
                pt = arm.pose.bones[W2E[f'{f}_Toe']]; h = arm.matrix_world @ pt.head
                M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
                pt.matrix = M @ pt.matrix; bpy.context.view_layer.update()
            report.setdefault('heelGroundDeg', {})[f] = float(_hg)
            report.setdefault('heelGroundGap_cm', {})[f] = round((_foot_lows(f)[0] - _foot_lows(f)[1]) * 100, 2)
            continue
        # heelGroundFlat False (user 10-25 previews): keep the toe angle (toeExtra), only tilt the foot until the toe reaches the floor
        for _round in range(2 if OC.get('heelGroundFlat', True) else 1):
            for _ in range(8):
                fz, hz = _foot_lows(f); d = fz - hz
                if abs(d) < 0.002: break
                pa = arm.pose.bones[W2E[f'{f}_Foot']]; h = arm.matrix_world @ pa.head
                M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), math.atan(d / 0.16)).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
                pa.matrix = M @ pa.matrix; bpy.context.view_layer.update()
                report.setdefault('heelGroundDeg', {})[f] = round(report.get('heelGroundDeg', {}).get(f, 0) + math.degrees(math.atan(d / 0.16)), 1)
            for _ in range(4 if OC.get('heelGroundFlat', True) else 0):
                pitch = sole_pitch(f, ('Toe',))
                if abs(pitch) < math.radians(0.5): break
                pt = arm.pose.bones[W2E[f'{f}_Toe']]; h = arm.matrix_world @ pt.head
                M = arm.matrix_world.inverted() @ Matrix.Translation(h) @ Quaternion((1.0, 0.0, 0.0), -pitch).to_matrix().to_4x4() @ Matrix.Translation(-h) @ arm.matrix_world
                pt.matrix = M @ pt.matrix; bpy.context.view_layer.update()
        report.setdefault('heelGroundGap_cm', {})[f] = round((_foot_lows(f)[0] - _foot_lows(f)[1]) * 100, 2)
report['solePitchAfterDeg'] = {f: [round(math.degrees(sole_pitch(f, FOOT_PARTS)), 1), round(math.degrees(sole_pitch(f, ('Toe',))), 1)] for f in 'LR' if f'{f}_Foot' in W2E}
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT'); suit.select_set(True); bpy.context.view_layer.objects.active = suit
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.armature_apply(selected=False); bpy.ops.object.mode_set(mode='OBJECT')
# flattening the heel lifts the shoe soles off the ground: put the lowest point of the re-posed outfit back on z = 0
sole = min(v.co.z for v in suit.data.vertices)
if abs(sole) > 0.002:
    suit.data.transform(Matrix.Translation((0, 0, -sole))); arm.data.transform(Matrix.Translation((0, 0, -sole)))
report['soleDrop_cm'] = round(sole * 100, 2)
EW = {n: arm.matrix_world @ b.head_local for n, b in arm.data.bones.items()}   # Eve joints, Blender world, re-posed
# dropBones (Scarlet without her hat, user 10-25: "make a version without the hat first, fix the hair, then put it back"):
# the vertices weighted mostly to these bones and their children are removed (the hat's chains then find no vertices)
if OC.get('dropBones'):
    import bmesh as _bm
    _drop = set()
    for _r in OC['dropBones']:
        if _r in arm.data.bones: _drop |= {_r} | {d.name for d in arm.data.bones[_r].children_recursive}
    _gd = {suit.vertex_groups[n].index for n in _drop if n in suit.vertex_groups}
    _kill = [v.index for v in suit.data.vertices if sum(g.weight for g in v.groups if g.group in _gd) > 0.5]
    _b = _bm.new(); _b.from_mesh(suit.data); _b.verts.ensure_lookup_table()
    _bm.ops.delete(_b, geom=[_b.verts[i] for i in _kill], context='VERTS'); _b.to_mesh(suit.data); _b.free(); suit.data.update()
    report['dropBones'] = [len(_drop), len(_kill)]
# meshRotate [{match, exclude, pivot, deg}] (Scarlet's leg drape, user 10-25: "still in the middle, in SB it hangs more to the
# side"): swings the vertices weighted to the matching bones (and those bones) outward about the pivot bone, round the
# body's forward axis; deg > 0 = the lower end away from the body's middle
for _mr in OC.get('meshRotate', []):
    _bn = [n for n in EW if _mr['match'] in n and not (_mr.get('exclude') and _mr['exclude'] in n)]
    if not _bn or _mr['pivot'] not in EW: continue
    _sx = 1.0 if sum(EW[n].x for n in _bn) >= 0 else -1.0
    _R = Matrix.Rotation(-_sx * math.radians(float(_mr['deg'])), 4, 'Y'); _pv = EW[_mr['pivot']].copy()
    _T = Matrix.Translation(_pv) @ _R @ Matrix.Translation(-_pv)
    _gi = {suit.vertex_groups[n].index for n in _bn if n in suit.vertex_groups}
    _mw = suit.matrix_world; _mi = _mw.inverted(); _nv = 0
    for v in suit.data.vertices:
        w_ = min(1.0, sum(g.weight for g in v.groups if g.group in _gi))
        if w_ > 0.001:
            p_ = _mw @ v.co; v.co = _mi @ (p_.lerp(_T @ p_, w_)); _nv += 1
    for n in _bn: EW[n] = _T @ EW[n]
    report.setdefault('meshRotate', []).append([_mr['match'], _mr['deg'], len(_bn), _nv])
# meshShift {bone substring: [back, out, up] m} (Scarlet's purple strip, user 10-25: "put it under the white cloth"): moves
# the vertices weighted to those bones (by weight) and the bones themselves; out = away from the body's middle on its side
# A 4th item 'island' (user 10-25: moved by weight the strip bent where its weights fade): the whole connected mesh
# piece(s) holding those vertices moves as one, as long as it is a small separate piece (under 5000 vertices)
for _sub, _ms in OC.get('meshShift', {}).items():
    _bk, _out, _up = _ms[:3]
    _bn = [n for n in EW if _sub in n]
    if not _bn: continue
    _sx = 1.0 if sum(EW[n].x for n in _bn) >= 0 else -1.0
    _off = Vector((_sx * _out, _bk, _up))          # Eve faces -Y: back = +Y
    _gi = {suit.vertex_groups[n].index for n in _bn if n in suit.vertex_groups}
    _mi3 = suit.matrix_world.inverted().to_3x3(); _nv = 0
    _wv = {v.index: min(1.0, sum(g.weight for g in v.groups if g.group in _gi)) for v in suit.data.vertices}
    if len(_ms) > 3 and _ms[3] == 'island':
        _adj = {}
        for e_ in suit.data.edges:
            a_, b_ = e_.vertices; _adj.setdefault(a_, []).append(b_); _adj.setdefault(b_, []).append(a_)
        _isl = set(); _todo = [i for i, w_ in _wv.items() if w_ > 0.3]
        while _todo:
            i = _todo.pop()
            if i in _isl: continue
            _isl.add(i); _todo.extend(j for j in _adj.get(i, ()) if j not in _isl)
            if len(_isl) > 5000: break
        if len(_isl) <= 5000: _wv = {i: (1.0 if i in _isl else 0.0) for i in _wv}
        report.setdefault('meshShiftIsland', []).append([_sub, len(_isl)])
    for v in suit.data.vertices:
        w_ = _wv[v.index]
        if w_ > 0.001: v.co += _mi3 @ (_off * w_); _nv += 1
    for n in _bn: EW[n] = EW[n] + _off
    report.setdefault('meshShift', []).append([_sub, len(_bn), _nv])
# limb thickness (user 10-19: arms / legs looked thicker or thinner from outfit to outfit -- every SB costume carries its own
# body sculpt): measure the mean skin radius around each limb segment; with a reference file (Diver / Blue Monsoon, row 149)
# every outfit's limbs (skin and the cloth on them) are scaled radially to the reference
LIMB_SEG = [('UpperArm', 'UpperArm', 'Forearm'), ('Forearm', 'Forearm', 'Hand'), ('Thigh', 'Thigh', 'Calf'), ('Calf', 'Calf', 'Foot')]
_skm = {i for i, m in enumerate(suit.data.materials) if m and (m.name.split('.')[0] == OC.get('skinMat') or
        any(k in m.name for k in ('Basebody', 'BaseBody', '_BB', 'Skin', 'Body')))}
_vmat = {}
for f in suit.data.polygons:
    for vi in f.vertices: _vmat.setdefault(vi, f.material_index)
_mw = suit.matrix_world; _mi = _mw.inverted()
_gn = {g.index: g.name for g in suit.vertex_groups}
def _seg(s_, a_, b_):
    A = EW.get(f'Bip001-{s_}-{a_}'); B = EW.get(f'Bip001-{s_}-{b_}')
    return (A, B) if A is not None and B is not None else (None, None)
girth = {}
for key, a_, b_ in LIMB_SEG:
    rs = []
    for s_ in 'LR':
        A, B = _seg(s_, a_, b_)
        if A is None: continue
        d_ = B - A; L2 = d_.length_squared
        for v in suit.data.vertices:
            if _vmat.get(v.index) not in _skm: continue
            if not any(f'{s_}-{a_}' in _gn[g.group] and g.weight > 0.3 for g in v.groups): continue
            co = _mw @ v.co; t = (co - A).dot(d_) / L2
            if 0.25 < t < 0.75: rs.append((co - (A + d_ * t)).length)
    if rs: girth[key] = round(sum(rs) / len(rs), 4)
report['limbGirth'] = girth
LREF = EP.DATA + 'eve_limb_ref.json'
if OC.get('limbRefWrite'):
    json.dump(girth, open(LREF, 'w')); report['limbRef'] = 'written'
elif OC.get('limbNormalize', True) and os.path.exists(LREF):
    _lref = json.load(open(LREF)); ratios = {}
    for key, a_, b_ in LIMB_SEG:
        if key not in _lref or key not in girth: continue
        k_ = max(0.85, min(1.15, _lref[key] / girth[key])); ratios[key] = round(k_, 3)
        # 10-19 (Denim jeans: thighs came out too thick): a ratio at the clamp means the skin measurement failed
        # (limb mostly covered by clothing) -> leave that limb as it is
        if abs(k_ - 1) < 0.01 or abs(k_ - 1) > 0.149: continue
        for s_ in 'LR':
            A, B = _seg(s_, a_, b_)
            if A is None: continue
            d_ = B - A; L2 = d_.length_squared
            for v in suit.data.vertices:
                w_ = min(1.0, sum(g.weight for g in v.groups if f'{s_}-{a_}' in _gn[g.group]))
                if w_ < 0.01: continue
                co = _mw @ v.co; t = (co - A).dot(d_) / L2
                if t < -0.1 or t > 1.1: continue
                fade = min(1.0, (t + 0.1) / 0.15, (1.1 - t) / 0.15)
                # 10-20 (user, game: a crescent lump under the buttocks on every outfit whose thighs were made thinner):
                # the buttock / shoulder end was scaled fully right next to vertices left alone -> a step. Fade in over the
                # upper third of the segment and out with the distance from the limb axis instead of a hard cut.
                if a_ in ('Thigh', 'UpperArm'): fade = min(fade, max(0.0, t / 0.35))
                c_ = A + d_ * t; rv = co - c_
                if rv.length > 0.2: continue
                rfade = min(1.0, max(0.0, (girth[key] * 1.35 - rv.length) / (girth[key] * 0.3)))   # loose layers (skirts) stay: scaling them by their own weights split the layers (Blossom, 10-19)
                if rfade <= 0 or fade <= 0: continue
                v.co = _mi @ (c_ + rv * (1 + (k_ - 1) * w_ * fade * rfade))
    report['limbRatio'] = ratios
for _gl in weld_groups():
    _c = sum((suit.data.vertices[i].co for i in _gl), Vector()) / len(_gl)
    for i in _gl: suit.data.vertices[i].co = _c
# residual roll of the hands (palm facing) after the swing-only re-pose
for s in 'LR':
    try:
        eh = (EW[f'Bip001-{s}-Finger1'] - EW[f'Bip001-{s}-Finger4']).normalized()
        hh = (HW[f'{s}_IndexF1'].translation - HW[f'{s}_PinkyF1'].translation).normalized()
        report.setdefault('handRollDeg', {})[s] = round(math.degrees(eh.angle(hh)), 1)
    except KeyError:
        pass

# ---------------- 3. new skeleton: hunter rotations, Eve positions ----------------
def gpos(blender_world_vec): return R90i @ blender_world_vec
mid_e = (EW['Bip001-L-Thigh'] + EW['Bip001-R-Thigh']) / 2
mid_h = (HW['L_Thigh'].translation + HW['R_Thigh'].translation) / 2
POS = {}                                        # Blender-world target positions for placed bones
for e, w in E2W.items():
    if w not in ('root', 'COG'): POS[w] = EW[e]
POS['Hip'] = mid_e + (HW['Hip'].translation - mid_h)
for mid, a, b in [('Neck_1', 'Neck_0', 'Head')] + [(f'{s}_Shin', f'{s}_Knee', f'{s}_Foot') for s in 'LR']:
    if mid in HW and a in POS and b in POS:
        ha, hm, hb = HW[a].translation, HW[mid].translation, HW[b].translation
        f = (hm - ha).length / max(1e-6, (hm - ha).length + (hb - hm).length)
        POS[mid] = POS[a] + (POS[b] - POS[a]) * f
NG = {}                                         # new game-world bind matrices
for n in HORDER:
    p = HPAR[n]
    if n in POS:
        NG[n] = Matrix.Translation(gpos(POS[n])) @ HG[n].to_quaternion().to_matrix().to_4x4()
    elif p is None:
        NG[n] = HG[n].copy()
    else:
        NG[n] = NG[p] @ (HG[p].inverted() @ HG[n])
# part-specific jiggle bones (the hunter innerwear body has L/R_BustJGL_CH_00 under *_Bust_HJ_01, driven by its chain2);
# butt jiggle bones are new, under Hip, driven by our chain2
EXTRA = {}
for s in 'LR':
    if f'Ab-{s}-Breast' in EW and f'{s}_Bust_HJ_01' in NG: EXTRA[f'{s}_BustJGL_CH_00'] = (f'{s}_Bust_HJ_01', EW[f'Ab-{s}-Breast'])
    # butt: Eve has no butt helper (Ab-*-Hip sits on the hip joint), so find the cheek: the most posterior skin behind the
    # pelvis on this side; the jiggle joint goes 5 cm inside it
    sg = 1 if s == 'L' else -1
    back = [v.co for v in suit.data.vertices if v.co.x * sg > 0.02 and 0.84 < v.co.z < 1.04 and v.co.y > EW['Bip001-Pelvis'].y + 0.04]
    if back:
        back.sort(key=lambda c_: -c_.y); top = back[:max(20, len(back) // 10)]
        cheek = sum(top, Vector()) / len(top)
        EXTRA[f'{s}_HipJGL_CH_00'] = ('Hip', cheek - Vector((0, 0.05, 0)))
        report.setdefault('buttCheek', {})[s] = [round(x, 3) for x in cheek]
# the jiggle joints keep the orientation the innerwear's own JGL joints have under their parent: the chain2 jiggle range /
# offset are in that frame (with the parent's orientation the 3 cm jiggle offset pushed the breasts into the chest)
vb = new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=INNER + f'2/ch03_002_{SUB}2.mesh.241111606', files=[{'name': f'ch03_002_{SUB}2.mesh.241111606'}], directory=INNER + '2'))
varm = next(o for o in vb if o.type == 'ARMATURE')
JGL_ROT = {}
for s in 'LR':
    pn, cn = f'{s}_Bust_HJ_01', f'{s}_BustJGL_CH_00'
    if pn in varm.data.bones and cn in varm.data.bones:
        JGL_ROT[cn] = (varm.data.bones[pn].matrix_local.inverted() @ varm.data.bones[cn].matrix_local).to_quaternion()
for o in vb: bpy.data.objects.remove(o, do_unlink=True)
if not JGL_ROT:      # type 1 innerwear has no bust jiggle joints: take their orientation from the type 2 body
    _d = P + 'wilds-inner101/natives/stm/art/model/character/ch03/002/101/2/'
    vb = new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=_d + 'ch03_002_1012.mesh.241111606', files=[{'name': 'ch03_002_1012.mesh.241111606'}], directory=_d))
    varm = next(o for o in vb if o.type == 'ARMATURE')
    for s in 'LR':
        pn, cn = f'{s}_Bust_HJ_01', f'{s}_BustJGL_CH_00'
        if pn in varm.data.bones and cn in varm.data.bones:
            JGL_ROT[cn] = (varm.data.bones[pn].matrix_local.inverted() @ varm.data.bones[cn].matrix_local).to_quaternion()
    for o in vb: bpy.data.objects.remove(o, do_unlink=True)
report['jglLocalRotDeg'] = {k: round(math.degrees(q.angle), 1) for k, q in JGL_ROT.items()}
for n, (par, pos) in EXTRA.items():
    rot = NG[par].to_quaternion() @ JGL_ROT[n] if n in JGL_ROT else NG[par].to_quaternion()
    NG[n] = Matrix.Translation(gpos(pos)) @ rot.to_matrix().to_4x4()
report['extraBones'] = {n: [par, [round(x, 3) for x in pos]] for n, (par, pos) in EXTRA.items()}
# ---------------- ponytail: in the body part, rigged like the vanilla Wilds ponytail (hairstyle 31) ----------------
# (moved out of the face mesh: only the body part has a chain2 the game loads for us)
import numpy as np
if not OWN_HAIR:
    PT_GLB = P + 'eve-hair/SB/Content/Art/Character/PC/CH_P_EVE_Hair/CH_P_EVE_Hair_PonyTail_2.glb'
    pobjs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=PT_GLB))
    pt_arm = next(o for o in pobjs if o.type == 'ARMATURE')
    pt = next(o for o in pobjs if o.type == 'MESH' and not o.name.startswith('Icosphere'))
    for pb in pt_arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    _rr = report.get('rawRestore'); restore_raw_positions(PT_GLB, pt); report['ptRaw'] = report.get('rawRestore'); report['rawRestore'] = _rr
    if pt.data.shape_keys: pt.shape_key_clear()
    # same placement as the outfit: yaw -90 deg, then the sole drop
    # EVE_PT_SHIFT (forward, down in m): the SB tie sits ~4 cm behind the skull; hanging under gravity from there the tail left a
    # gap to the back of the head in game (user 10-18) -> pull the whole ponytail onto the crown (Eve faces -Y)
    _ptf, _ptd = (float(x) for x in os.environ.get('EVE_PT_SHIFT', '0.035,0.015').split(','))
    PT_PLACE = Matrix.Translation((0, -_ptf, (-sole if abs(sole) > 0.002 else 0) - _ptd)) @ Matrix.Rotation(math.radians(-90), 4, 'Z')
    Bpts = [PT_PLACE @ (pt_arm.matrix_world @ pt_arm.data.bones[f'Ab-TL-HairB0{i}'].head_local) for i in range(1, 10)]
    pt.data.transform(PT_PLACE @ pt.matrix_world); pt.parent = None; pt.matrix_world = Matrix.Identity(4)
    for m_ in list(pt.modifiers): pt.modifiers.remove(m_)
    for o in pobjs:
        if o is not pt: bpy.data.objects.remove(o, do_unlink=True)
    pt.vertex_groups.clear()
    K_PT, PT_SIDE, PT_STEP, PT_W = 3, (-0.02, 0.0, 0.02), float(os.environ.get('EVE_PT_STEP', '0.10')), 0.035
    # vanilla Wilds ponytail rig (hairstyle 31, ch01_001_0518): 3 chains side by side (left / centre / right, 2 cm apart, linked
    # in the chain2), every bone unrotated (world-aligned, like all vanilla hair joints), evenly spaced down the tail.
    # (the earlier 8 overlapping chains with bones rolled along the tail stood the ponytail up / fanned it out in game)
    PL = np.array([list(b) for b in Bpts] + [list(Bpts[-1] + (Bpts[-1] - Bpts[-2]))])
    tv = np.array([list(v.co) for v in pt.data.vertices])
    segs = PL[1:] - PL[:-1]
    bt = np.full(len(tv), 1e9); bd = np.full(len(tv), 1e9)
    for i, (a, sv) in enumerate(zip(PL[:-1], segs)):
        u = np.clip(((tv - a) @ sv) / (sv @ sv), 0, 1); d = np.linalg.norm(tv - (a + u[:, None] * sv), axis=1)
        mm = d < bd; bd[mm] = d[mm]; bt[mm] = i + u[mm]
    tpar = bt


    def P_at(t):
        i = int(min(max(math.floor(t), 0), len(PL) - 2)); return PL[i] + (t - i) * (PL[i + 1] - PL[i])


    def T_at(t):
        i = int(min(max(math.floor(t), 0), len(PL) - 2)); v = PL[i + 1] - PL[i]; return v / np.linalg.norm(v)


    def side_axis(t):                                   # world X (Eve's left-right) made square to the tail
        T = T_at(t); x = np.array([1.0, 0, 0]) - T[0] * T; return x / np.linalg.norm(x)


    # user 10-18 (SB side shot): the original tail reads thinner than ours (it hid the hair ornament) -> scale the hair's
    # distance from the tail centre line by EVE_PT_THIN (1 at the tie -> full factor 0.25 m down)
    _thin = float(os.environ.get('EVE_PT_THIN', '0.7'))
    if _thin < 0.999:
        _c = np.array([P_at(t) for t in tpar])
        _arc = np.array([np.linalg.norm(P_at(t) - P_at(1.0)) if t > 1.0 else 0.0 for t in tpar])
        _f = 1.0 - (1.0 - _thin) * np.clip(_arc / 0.25, 0, 1)
        tv = _c + (tv - _c) * _f[:, None]
        for v_, p_ in zip(pt.data.vertices, tv): v_.co = Vector(list(p_))
        bd = bd * _f
        report['ptThin'] = _thin
    t_end = float(np.percentile(tpar, 99.5))
    tf = np.linspace(1.0, t_end, 2000)
    cum = np.concatenate([[0], np.cumsum([np.linalg.norm(P_at(b) - P_at(a)) for a, b in zip(tf[:-1], tf[1:])])])
    n_seg = max(3, int(round(cum[-1] / PT_STEP)))
    tn = np.interp(np.linspace(0, cum[-1], n_seg + 1), cum, tf); M_PT = len(tn)


    def ptname(k, j): return f'evePT{k:02d}_CH_{j:02d}' if j < M_PT - 1 else f'evePT{k:02d}_CH_end'


    PT_BONES = []                                    # (name, head, parent) in Blender world; bones get no rotation
    for k in range(K_PT):
        par = 'Head'
        for j, t in enumerate(tn):
            PT_BONES.append((ptname(k, j), Vector(list(P_at(t) + PT_SIDE[k] * side_axis(t))), par)); par = ptname(k, j)
    ptg = {}


    def ptvg(n):
        if n not in ptg: ptg[n] = pt.vertex_groups.new(name=n)
        return ptg[n]


    for idx in range(len(tv)):
        t = tpar[idx]
        u = float(np.clip((tv[idx] - P_at(t)) @ side_axis(t) / PT_W, -1, 1))
        kw = {0: max(-u, 0.0), 1: 1 - abs(u), 2: max(u, 0.0)}
        wh = 0.0
        if t < tn[0]: wh = 1.0 if t < tn[0] - 0.5 else (tn[0] - t) / 0.5
        # along the tail: linear between the two nearest nodes (each bone carries the hair from its joint to the next)
        j = int(np.clip(np.searchsorted(tn, t) - 1, 0, M_PT - 2)); f = float(np.clip((t - tn[j]) / (tn[j + 1] - tn[j]), 0, 1))
        out = {}
        if wh > 0: out['Head'] = wh
        for k, wk in kw.items():
            if wk <= 0: continue
            for jj, wj in ((j, 1 - f), (j + 1, f)):
                if wj > 0: out[ptname(k, jj)] = out.get(ptname(k, jj), 0) + (1 - wh) * wk * wj
        top = sorted(out.items(), key=lambda kv: -kv[1])[:6]; tot = sum(w for _, w in top) or 1
        for nm, w in top:
            if w > 1e-4: ptvg(nm).add([idx], w / tot, 'REPLACE')
    report['ponytail'] = {'verts': len(tv), 'chains': K_PT, 'nodes': M_PT, 'length_m': round(float(cum[-1]), 3),
                          'spacing_m': [round(float(np.linalg.norm(P_at(b) - P_at(a))), 3) for a, b in zip(tn[:-1], tn[1:])]}
else:
    # own hair (Scarlet): her hair is part of the character mesh; no Eve ponytail bones / mesh / chains
    pt = None; PT_BONES = []; K_PT = 0; M_PT = 0
    def ptname(k, j): return ''
    report['ponytail'] = 'own hair'

# ---- hair ornament: Eve's folded sword (SB reference shots, user 10-18): its hilt (black cylinder with the gear disc and the
# blue clip) sits on the ponytail tie with the hair running through it; the folded blades stand out straight, back and down
# at about 40 deg, wide faces to the sides. Rigid on the head (like a hair clip).
HP_GLB = P + 'eve-sword01-full/SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01/CH_W_Sword_01_Folded.glb'
hpin = None
if os.environ.get('EVE_HAIRPIN', '1') == '1' and not OWN_HAIR:
    hobjs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=HP_GLB))
    hsrc = next(o for o in hobjs if o.type == 'MESH' and not o.name.startswith('Icosphere'))
    # hilt = vertices mostly on the gear / panel / grip bones (from the source weights; same vertex order after evaluation)
    gname = {g.index: g.name for g in hsrc.vertex_groups}
    hilt_mask = np.array([bool(v.groups) and any(k in gname[max(v.groups, key=lambda g: g.weight).group] for k in ('Gear',))
                          for v in hsrc.data.vertices])
    # the file's skeleton reference pose is what folds the sword (its bind mesh is the open 1.3 m sword): take the posed mesh
    bpy.context.view_layer.update(); dg_ = bpy.context.evaluated_depsgraph_get()
    hme = bpy.data.meshes.new_from_object(hsrc.evaluated_get(dg_), depsgraph=dg_); hme.transform(hsrc.matrix_world)
    hpin = bpy.data.objects.new('hairpin', hme); bpy.context.scene.collection.objects.link(hpin)
    for o in hobjs: bpy.data.objects.remove(o, do_unlink=True)
    hpin.data.transform(Matrix.Scale(float(os.environ.get('EVE_HAIRPIN_SCALE', '0.9')), 4))
    hpin.vertex_groups.clear()
    hv = np.array([list(v.co) for v in hpin.data.vertices]); hc = hv.mean(axis=0)
    ev, evec = np.linalg.eigh(np.cov((hv - hc).T))
    a_len, a_wid, a_thk = evec[:, 2], evec[:, 1], evec[:, 0]          # longest / middle / thinnest
    hilt_c = hv[hilt_mask].mean(axis=0) if hilt_mask.sum() > 20 else hc
    if (hilt_c - hc) @ a_len > 0: a_len = -a_len                       # hilt at the low end of a_len (= the top)
    if os.environ.get('EVE_HAIRPIN_FLIP') == '1': a_len = -a_len
    tie = np.array(P_at(float(os.environ.get('EVE_HAIRPIN_T', '0.6'))))
    ang = math.radians(float(os.environ.get('EVE_HAIRPIN_DEG', '6')))  # from straight down toward the back
    dirv = np.array([0.0, math.sin(ang), -math.cos(ang)])               # Eve faces -Y: back = +Y, down = -Z
    perp = np.array([0.0, math.cos(ang), math.sin(ang)])               # in the side plane, square to dirv
    side = np.cross(dirv, perp)
    # blue clip (SB: a crest on top of the hub, facing up-back): find its vertices by the base colour texture and turn the model
    # so the hub->clip direction becomes 'perp' (up-back in the side plane); the hub's cylinder axis then lies left-right
    blue = np.zeros(len(hv), bool)
    try:
        _im = bpy.data.images.load(P + 'eve-sword01-full/SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01/Textures/CH_W_Sword_02_D.png')
        _W, _H = _im.size; _px = np.array(_im.pixels[:], dtype=np.float32).reshape(_H, _W, 4); bpy.data.images.remove(_im)
        _uv = hpin.data.uv_layers[0].data
        for poly in hpin.data.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                u_, v_ = _uv[li].uv; c_ = _px[min(_H - 1, max(0, int((v_ % 1) * _H))), min(_W - 1, max(0, int((u_ % 1) * _W)))]
                if c_[2] > 0.3 and c_[2] > c_[0] + 0.15 and c_[2] > c_[1] + 0.05: blue[vi] = True
    except Exception as e_:
        report['hairpinBlueErr'] = str(e_)
    if blue.sum() > 30:
        bdir = hv[blue].mean(axis=0) - hilt_c; a_wid = bdir
    a_wid = a_wid - (a_wid @ a_len) * a_len; a_wid /= np.linalg.norm(a_wid); a_thk = np.cross(a_len, a_wid)
    report['hairpinBlueVerts'] = int(blue.sum())
    if os.environ.get('EVE_HAIRPIN_ROLL') == '1': a_wid, a_thk = a_thk, -a_wid
    Rsrc = np.stack([a_len, a_wid, a_thk], axis=1); Rdst = np.stack([dirv, perp, side], axis=1)   # wide faces to the sides
    R = Rdst @ Rsrc.T
    if np.linalg.det(R) < 0: Rsrc[:, 2] = -Rsrc[:, 2]; R = Rdst @ Rsrc.T
    loc = (hv - hc) @ R.T; hilt_l = (hilt_c - hc) @ R.T
    # the reference pose is a straight line: thin blades one way from the gear hub, the main blades the other. In SB the hub
    # (black cylinder + gear disc, blue clip) wraps the tie and both blade sets hang: main blades back-and-down (EVE_HAIRPIN_DEG),
    # thin blades nearly straight down (EVE_HAIRPIN_THIN_DEG). Fold the thin side about the hub.
    sl = (loc - hilt_l) @ dirv
    hub_r = float(np.percentile(np.abs(sl[hilt_mask]), 90)) if hilt_mask.sum() > 20 else 0.03
    tang = math.radians(float(os.environ.get('EVE_HAIRPIN_THIN_DEG', '4')))
    thin_dir = np.array([0.0, math.sin(tang), -math.cos(tang)])
    src = -dirv; ax = np.cross(src, thin_dir); sa = np.linalg.norm(ax); ca = float(src @ thin_dir)
    if sa > 1e-6:
        ax = ax / sa; K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        Rt = np.eye(3) + sa * K + (1 - ca) * (K @ K)
        thin = (sl < -hub_r) & ~hilt_mask
        loc[thin] = (loc[thin] - hilt_l) @ Rt.T + hilt_l
        report['hairpinThinVerts'] = int(thin.sum())
    # hub on the tie, a little up and behind (the tie is on the tail's front/top side)
    # SB back shot (user 10-18): the blades hang on Eve's right side of the tail (Eve faces -Y, her right = -X)
    newv = loc - hilt_l + tie + np.array([float(os.environ.get('EVE_HAIRPIN_SIDE', '-0.005')), float(os.environ.get('EVE_HAIRPIN_BACKOFF', '-0.01')),
                                           float(os.environ.get('EVE_HAIRPIN_UP', '0.0'))])
    # SB side view (user 10-18): from the hub the sword arm runs back-down at ~45 deg, then the blades hang almost vertically
    # BEHIND the ponytail -- placed straight from the hub they sat inside the thick hair near the tie and were hidden.
    # Dogleg: below the hub every vertex is pushed back by min(depth * EVE_HAIRPIN_KINK, EVE_HAIRPIN_CLEAR).
    s_dn = (loc - hilt_l) @ dirv
    kink = float(os.environ.get('EVE_HAIRPIN_KINK', '1.3')); clear = float(os.environ.get('EVE_HAIRPIN_CLEAR', '0.15'))
    push = np.clip(s_dn * kink, 0.0, clear)
    newv = newv + push[:, None] * np.array([0.0, 1.0, 0.0])
    # user 10-18: the black gear ring is its own piece, fixed exactly on the ponytail tie (SB: the ring wraps the tie);
    # the rest (blue clip, arm, blades) is placed separately and does not follow the hair (rigid on the head)
    ring = hilt_mask.copy()
    if ring.sum() > 20:
        rc = newv[ring].mean(axis=0)
        newv[ring] = newv[ring] - rc + tie + np.array([0.0, float(os.environ.get('EVE_RING_BACK', '0.0')), float(os.environ.get('EVE_RING_UP', '0.0'))])
        rest = ~ring
        newv[rest] = newv[rest] + np.array([float(os.environ.get('EVE_ORN_SIDE', '0.0')), float(os.environ.get('EVE_ORN_BACK', '0.015')),
                                            float(os.environ.get('EVE_ORN_UP', '0.02'))])
        report['hairpinRing'] = {'verts': int(ring.sum()), 'diam_m': round(float(np.ptp((newv[ring] - tie) @ perp)), 3)}
    report['hairpinDogleg'] = {'kink': kink, 'clear_m': clear}
    for v, p_ in zip(hpin.data.vertices, newv): v.co = Vector(list(p_))
    # user 10-18: the hanging sword part swings in SB -> its own small physics chain (eveORN_CH_*, not tied to the hair):
    # Head-rigid down to the hub (ring, blue clip), then the arm / blades on 3 chain joints along the dogleg path
    base = tie + np.array([float(os.environ.get('EVE_HAIRPIN_SIDE', '-0.005')), float(os.environ.get('EVE_HAIRPIN_BACKOFF', '-0.01')),
                           float(os.environ.get('EVE_HAIRPIN_UP', '0.0'))]) + np.array([float(os.environ.get('EVE_ORN_SIDE', '0.0')),
                           float(os.environ.get('EVE_ORN_BACK', '0.015')), float(os.environ.get('EVE_ORN_UP', '0.02'))])
    def orn_at(sv): return base + sv * dirv + min(sv * kink, clear) * np.array([0.0, 1.0, 0.0])
    s_max = float(s_dn[~hilt_mask].max()) if (~hilt_mask).any() else float(s_dn.max())
    s_k = clear / kink
    ORN_S = [0.0, min(s_k, 0.5 * s_max), 0.5 * (min(s_k, 0.5 * s_max) + s_max), s_max]
    ORN_BONES = []
    _par = 'Head'
    for j, sv in enumerate(ORN_S):
        nm = f'eveORN_CH_{j:02d}' if j < len(ORN_S) - 1 else 'eveORN_CH_end'
        ORN_BONES.append((nm, Vector(list(orn_at(sv))), _par)); _par = nm
    swing = os.environ.get('EVE_ORN_PHYS', '1') == '1'
    gh = hpin.vertex_groups.new(name='Head'); og = {}
    for i in range(len(newv)):
        sv = float(s_dn[i])
        if not swing or hilt_mask[i] or sv <= ORN_S[0]:
            gh.add([i], 1.0, 'REPLACE'); continue
        j = int(np.clip(np.searchsorted(ORN_S, sv) - 1, 0, len(ORN_S) - 2)); f = float(np.clip((sv - ORN_S[j]) / (ORN_S[j + 1] - ORN_S[j]), 0, 1))
        for jj, w in ((j, 1 - f), (j + 1, f)):
            if w <= 1e-4: continue
            nm = ORN_BONES[jj][0]
            if nm not in og: og[nm] = hpin.vertex_groups.new(name=nm)
            og[nm].add([i], w, 'ADD')
    if swing: PT_BONES += ORN_BONES
    report['ornChain'] = {'s': [round(x, 3) for x in ORN_S], 'on': swing}
    pr = loc @ dirv
    report['hairpin'] = {'verts': len(newv), 'length_m': round(float(pr.max() - pr.min()), 3), 'hiltVerts': int(hilt_mask.sum()),
                         'deg': round(math.degrees(ang), 1)}

# skirt chains (user 10-18, Moran: the dress panels did not move and the legs went through them when running): each SB
# skirt chain (<root>-01..0n, parented to the pelvis) becomes eveSK_<k>_<j> joints on Hip + one end joint, weights follow
SKIRT = []
SKIRT_KIND = {}      # chain index -> mech / tie / cloth / drape (autoChains); skirts default
for k, root in enumerate(OC.get('skirtChains', [])):
    names = []
    j = 1
    while f'{root}-{j:02d}' in EW: names.append(f'{root}-{j:02d}'); j += 1
    if len(names) < 2: continue
    par = 'Hip'; bones = []
    for j, en in enumerate(names):
        nm = f'eveSK_{k}_{j}'; PT_BONES.append((nm, EW[en].copy(), par)); HELPER_SK = globals().setdefault('HELPER_SK', {}); HELPER_SK[en] = nm
        bones.append(nm); par = nm
    tip = EW[names[-1]] + (EW[names[-1]] - EW[names[-2]]) * 0.8
    PT_BONES.append((f'eveSK_{k}_end', tip, par)); bones.append(f'eveSK_{k}_end')
    SKIRT.append(bones)
report['skirtChains'] = [len(b) for b in SKIRT]
DRAPE_W = {}
for dr in OC.get('drapes', []):
    gi_ = suit.vertex_groups.get(dr['bone'])
    if gi_ is None: continue
    bh = EW[dr['bone']]; bt = EW[arm.data.bones[dr['bone']].parent.name] if arm.data.bones[dr['bone']].parent else bh
    ax = (bh - bt).normalized() if (bh - bt).length > 1e-4 else Vector((0, 0, 1))
    pts = []
    for v in suit.data.vertices:
        w = next((g.weight for g in v.groups if g.group == gi_.index), 0)
        if w < 0.5: continue
        co = suit.matrix_world @ v.co; rel = co - bh; off = rel - ax * rel.dot(ax)
        if off.length > dr.get('min_dist', 0.07): pts.append((v.index, co, off.length))
    if len(pts) < 50: continue
    if OC.get('drapeHang'):
        # 10-19 (Blue Samurai): the SB sleeve is modelled lying flat straight back from the forearm (runtime cloth lets it
        # fall). In game the arms hang at the sides most of the time, so the sleeve is re-shaped to hang parallel to the
        # forearm (slightly behind it): in this A-pose that is along the upper-arm direction. Rotation about the cuff,
        # growing smoothly over 'hangBend' metres from the arm so the top curves instead of folding.
        _md = dr.get('min_dist', 0.07); _bend = float(OC.get('hangBend', 0.25))
        _sd = 'L' if '-L-' in dr['bone'] else 'R'
        _ua = EW.get(f'Bip001-{_sd}-UpperArm'); _fa = EW.get(f'Bip001-{_sd}-Forearm')
        _r0 = [p_[1] for p_ in pts if p_[2] < _md + 0.03]
        _r0 = sum(_r0, Vector()) / len(_r0) if _r0 else bh
        _f0 = max(pts, key=lambda p_: p_[2])[1]
        _D = (_f0 - _r0).normalized()
        _u = (_fa - _ua).normalized() if _ua is not None and _fa is not None else Vector((0.0, 0.0, -1.0))
        _T = (_u + _D * float(OC.get('hangBack', 0.25))).normalized()
        _axr = _D.cross(_T); _ang = _D.angle(_T)
        if _axr.length > 1e-4:
            _axr.normalize(); _mi = suit.matrix_world.inverted(); _np = []
            # 'hangFar' (10-20): cloth that far from the arm turns fully too, wherever it sits along the sleeve -- the bag of
            # the kimono sleeve next to the elbow stayed pointing back (a balloon behind the arm in game)
            _far = float(OC.get('hangFar', 0)); _S = {}
            for vi, co, dist in pts:
                t_ = max(0.0, min(1.0, (co - _r0).dot(_D) / _bend))
                if _far: t_ = max(t_, max(0.0, min(1.0, (dist - _md) / _far)))
                s_ = t_ * t_ * (3 - 2 * t_); _S[vi] = s_
                nco = _r0 + Quaternion(_axr, _ang * s_) @ (co - _r0)
                suit.data.vertices[vi].co = _mi @ nco; _np.append((vi, nco, dist))
            pts = _np
            report.setdefault('drapeHang', []).append([dr['bone'], round(math.degrees(_ang), 1)])
            # 10-20 (user, YoRHa uniform 1 next to the running SB original): hung like that the sleeve's wide face points
            # sideways (a fan behind the arm from the side, a thin edge from behind); in SB the cloth folds so the face
            # (and its pattern) is seen from behind, the sleeve hanging behind the hip toward the middle and narrowing to
            # the tip. Chains cannot fold cloth, so the rest shape is made that way: turn the panel about its hanging axis
            # until its width runs across the back ('hangTwist' = share of that turn, 1 = full), then narrow it toward the
            # tip ('hangTaper' = width left at the tip). Both grow over 'hangBend' from the cuff so the top stays attached.
            _tw = float(OC.get('hangTwist', 0)); _tp = float(OC.get('hangTaper', 1.0))
            if _tw or _tp < 1.0:
                _len = max((co - _r0).dot(_T) for _, co, _ in pts) or 1.0
                _perp = [(co - _r0) - _T * (co - _r0).dot(_T) for _, co, _ in pts]
                # panel width direction: principal axis of the points across the hanging axis
                _e1 = _T.orthogonal().normalized(); _e2 = _T.cross(_e1).normalized()
                _sxx = sum(p_.dot(_e1) ** 2 for p_ in _perp); _syy = sum(p_.dot(_e2) ** 2 for p_ in _perp)
                _sxy = sum(p_.dot(_e1) * p_.dot(_e2) for p_ in _perp)
                _th = 0.5 * math.atan2(2 * _sxy, _sxx - _syy)
                _W = (_e1 * math.cos(_th) + _e2 * math.sin(_th)).normalized()
                if sum(p_.dot(_W) for p_ in _perp) < 0: _W = -_W          # pointing from the seam into the panel
                _in = Vector((-1.0 if _r0.x > 0 else 1.0, 0.0, 0.0))        # toward the body's middle
                _Wt = Vector((0.0, 1.0, 0.0)).cross(_T).normalized()        # across the back once the arm hangs
                if _Wt.dot(_in) < 0: _Wt = -_Wt
                _full = math.atan2(_T.dot(_W.cross(_Wt)), _W.dot(_Wt))
                # 10-20 (user, game: "a flag standing up" -- in SB the cloth runs down in one strand, like hair): roll the
                # width up as it goes down ('hangCurlTop' -> 'hangCurl' degrees of arc from cuff to tip) and add soft folds
                # across it ('hangPleats' half waves of 'hangPleatAmp' m), so the cross-section is a gathered curl, not a sheet
                _cu0 = math.radians(float(OC.get('hangCurlTop', 0))); _cu1 = math.radians(float(OC.get('hangCurl', 0)))
                _pn = int(OC.get('hangPleats', 0)); _pa = float(OC.get('hangPleatAmp', 0.0))
                _N = _T.cross(_W).normalized()
                if (Quaternion(_T, _full * _tw) @ _N).y < 0: _N = -_N           # the rolled edge curls backward, off the body
                _Wm = max(p_.dot(_W) for p_ in _perp) or 1.0
                _mi = suit.matrix_world.inverted(); _np = []
                for (vi, co, dist), p_ in zip(pts, _perp):
                    a_ = (co - _r0).dot(_T)
                    t_ = max(0.0, min(1.0, a_ / _bend)); s_ = max(t_ * t_ * (3 - 2 * t_), _S.get(vi, 0.0))
                    q_ = Quaternion(_T, _full * _tw * s_)
                    fr_ = max(0.0, min(1.0, a_ / _len))
                    w_ = 1.0 - (1.0 - _tp) * fr_
                    wc, nc = p_.dot(_W), p_.dot(_N); rest = p_ - _W * wc - _N * nc
                    wc *= w_; wm = _Wm * w_
                    if _pn and wc > 0: nc += _pa * s_ * math.sin(math.pi * _pn * min(1.0, wc / wm))
                    phi = (_cu0 + (_cu1 - _cu0) * fr_) * s_
                    if phi > 1e-3 and wc > 0:
                        R_ = wm / phi; th_ = wc / R_
                        x_, y_ = (R_ - nc) * math.sin(th_), R_ - (R_ - nc) * math.cos(th_)
                    else:
                        x_, y_ = wc, nc
                    nco = _r0 + _T * a_ + q_ @ (_W * x_ + _N * y_ + rest)
                    suit.data.vertices[vi].co = _mi @ nco; _np.append((vi, nco, dist))
                pts = _np
                report.setdefault('drapeTwist', []).append([dr['bone'], round(math.degrees(_full * _tw), 1), _tp])
    far = max(pts, key=lambda p_: p_[2])[1]
    root = sum((p_[1] for p_ in pts if p_[2] < dr.get('min_dist', 0.07) + 0.03), Vector()) / max(1, sum(1 for p_ in pts if p_[2] < dr.get('min_dist', 0.07) + 0.03))
    d_ = far - root; L_ = d_.length; n_b = int(OC.get('drapeBones', 4))
    k = len(SKIRT); par = W2E.get(dr['bone']) and E2W.get(dr['bone']) or E2W.get(arm.data.bones[dr['bone']].parent.name, 'Hip')
    bones = []
    for j in range(n_b):
        nm = f'eveSK_{k}_{j}'; PT_BONES.append((nm, root + d_ * (j / n_b), par)); bones.append(nm); par = nm
    PT_BONES.append((f'eveSK_{k}_end', far, par)); bones.append(f'eveSK_{k}_end')
    for vi, co, dist in pts:
        t = max(0.0, min(0.999, (co - root).dot(d_) / (L_ * L_))) * n_b; j = int(t); f = t - j
        ws = {bones[j]: 1 - f}; ws[bones[min(j + 1, n_b - 1)]] = ws.get(bones[min(j + 1, n_b - 1)], 0) + f
        fade = min(1.0, (dist - dr.get('min_dist', 0.07)) / float(OC.get('drapeFade', 0.04)))
        DRAPE_W[vi] = (ws, fade)
    SKIRT_KIND[len(SKIRT)] = 'drape'; SKIRT.append(bones)
    report.setdefault('drapes', []).append([dr['bone'], len(pts), round(L_, 2)])
# hanging cloth / blade chains (user 10-19: Blue Samurai sleeve cloth, Cosmoloid back blades, capes did not move): SB helper
# bone chains (not Bip001, single line of >= 3 bones, >= 12 cm long, not a body / bust / skirt corrective) become eveSK
# physics joints on their mapped ancestor; their side branches follow the nearest chain joint
# hanging panels that should fall closer to the body (user 10-19 / SB check: Planet Dive 7th's sheer panels start at the
# shoulder blades and hang down behind the back, ours flared out past the hips): below the panel root the sideways
# offset shrinks to k (full effect 'depth' m below the root), for the panel vertices and its helper bones alike
for _cn in OC.get('capeNarrow', []):
    _roots = [b for b in arm.data.bones if _cn['match'] in b.name and (not b.parent or _cn['match'] not in b.parent.name)]
    _k, _dp = float(_cn.get('k', 0.55)), float(_cn.get('depth', 0.35))
    _t0, _clr = float(_cn.get('rootT', 0.0)), float(_cn.get('clear', 0.02))
    _mw = suit.matrix_world; _mi = _mw.inverted(); _nv = 0
    # body back profile (largest y = back, Eve faces -Y) per 2 cm of height, without the panel vertices themselves
    _allp = set()
    for _rb in _roots: _allp |= {_rb.name} | {d.name for d in _rb.children_recursive}
    _gp = {g.index for g in suit.vertex_groups if g.name in _allp}
    _back = {}
    for v in suit.data.vertices:
        if any(g.group in _gp and g.weight > 0.01 for g in v.groups): continue
        c_ = _mw @ v.co
        if abs(c_.x) < 0.2: _bz = int(c_.z * 50); _back[_bz] = max(_back.get(_bz, -9.0), c_.y)
    for _rb in _roots:
        _z0 = EW[_rb.name].z
        _names = {_rb.name} | {d.name for d in _rb.children_recursive}
        def _nar(co, w=1.0):
            t_ = (_t0 + (1 - _t0) * max(0.0, min(1.0, (_z0 - co.z) / _dp))) * w
            co.x = co.x + (co.x * _k - co.x) * t_
            _by = max(_back.get(int(co.z * 50) + d_, -9.0) for d_ in (-1, 0, 1))
            if _by > -9 and co.y < _by + _clr: co.y = co.y + (_by + _clr - co.y) * min(1.0, w * 2)   # stay behind the body
            return co
        for _n in _names: EW[_n] = _nar(EW[_n].copy())
        _gi = {g.index for g in suit.vertex_groups if g.name in _names}
        for v in suit.data.vertices:
            w_ = min(1.0, sum(g.weight for g in v.groups if g.group in _gi))
            if w_ > 0.01:
                v.co = _mi @ _nar(_mw @ v.co, w_); _nv += 1
    report.setdefault('capeNarrow', []).append([_cn['match'], len(_roots), _nv])
if OC.get('autoChains', True):
    _skip = ('Breast', 'Hip', 'Thigh', 'Calf', 'Knee', 'Elbow', '-Tw', 'Pectro', 'Trape', 'Deltoid', 'Becep', 'Tricep', 'Venter',
             'Ankle', 'Toe', 'Finger', 'Hand', 'Neck', 'Head', 'Clavicle', 'Hair', 'Pony', 'Brochi', 'Butt', 'Pelvis', 'Shoes', 'Side', 'Shoulder')
    if OC.get('hairChains'):   # own hair (Scarlet): her hair strands become physics chains like the cloth ones
        # ('-Side' still skips the arm helper Ab-R-Side, but her front locks Ab_Hair_Side_* become chains, user 10-25)
        _skip = tuple(('-Side' if x == 'Side' else x) for x in _skip if x != 'Hair')
    # chainLongest (Scarlet's back ornaments / leg drape, 10-25): at a fork follow the branch with the most bones, so the
    # whole strip is one chain; the side pieces (bows, tabs) ride on the node they branch from
    _long = lambda b: any(x in b.name for x in OC.get('chainLongest', []))
    _vcount = {}
    for v in suit.data.vertices:
        for g in v.groups:
            if g.weight > 0.05: _vcount[suit.vertex_groups[g.group].name] = _vcount.get(suit.vertex_groups[g.group].name, 0) + 1
    HELPER_SK = globals().setdefault('HELPER_SK', {})
    def _anc(b):
        while b and b.name not in E2W: b = b.parent
        return E2W[b.name] if b else 'Hip'
    k0 = len(SKIRT); found = []
    lines = []; BRANCH = set()
    def _walk(b):
        # a single line of bones from b; where it forks, every branch is walked as its own line (ribbon fans)
        line = [b]
        if _long(b) or b.name in BRANCH:
            while line[-1].children:
                # ties: the branch that is not a branchSkip side piece stays on the main line (Scarlet's drape end vs its flare)
                line.append(max(line[-1].children, key=lambda c: (len(c.children_recursive), not any(z in c.name for z in OC.get('branchSkip', [])),
                                                                  'Acc' not in c.name)))
            if len(line) >= 2: lines.append(line)
            # side pieces of 2+ bones (tabs, ribbons, the flare) hang as their own chains from the node they branch at: held
            # rigidly on that node they stuck out sideways in game (user 10-25); branchSkip ones (bow loops) stay on the node
            for x in line[:-1]:
                for c in x.children:
                    if c not in line and c.children and not any(z in c.name for z in OC.get('branchSkip', [])):
                        BRANCH.add(c.name); _walk(c)
            return
        while len(line[-1].children) == 1 and not any(x in line[-1].children[0].name for x in _skip): line.append(line[-1].children[0])
        if len(line) >= 2: lines.append(line)
        for c in line[-1].children:
            if not any(x in c.name for x in _skip): _walk(c)
    def _skipped_helper(b):
        return b and not b.name.startswith('Bip001') and any(x in b.name for x in _skip)
    for b in arm.data.bones:
        if b.name.startswith('Bip001') or any(x in b.name for x in _skip) or not b.parent: continue
        if b.parent.name in E2W or (_skipped_helper(b.parent) and b.parent.parent and b.parent.parent.name in E2W): _walk(b)
    for line in lines:
        b = line[0]
        if b.name in HELPER_SK: continue
        _inl = {x.name for l_ in lines if l_ is not line and l_[0].name in BRANCH for x in l_}
        if b.name in BRANCH:
            if b.parent.name not in HELPER_SK: continue
            L_ = sum(((EW[line[i + 1].name] - EW[line[i].name]).length for i in range(len(line) - 1)))
            if L_ < 0.04 or sum(_vcount.get(x.name, 0) for x in line) < 60:   # too small: back onto its node
                for x in line + [d for x in line for d in x.children_recursive]: HELPER_SK.setdefault(x.name, HELPER_SK[b.parent.name])
                continue
        elif 'Skirt' in b.name and len(line) < 6 and not _long(b): continue   # cloth skirts stay skinned (user, Moran); long ones are mechanical tassets
        if any(x in b.name for x in OC.get('chainSkip', [])): continue   # per outfit: stays skinned (Holiday Rabbit hood strings, 10-19)
        L_ = sum(((EW[line[i + 1].name] - EW[line[i].name]).length for i in range(len(line) - 1)))
        if b.name not in BRANCH and (L_ < 0.10 or sum(_vcount.get(x.name, 0) for x in line) < 120): continue
        k = k0 + len(found); par = HELPER_SK[b.parent.name] if b.name in BRANCH else _anc(b); bones = []
        par = next((v for x, v in OC.get('chainRoot', {}).items() if x in b.name), par)   # per outfit root (Planet Dive 7th cape: Spine_2)
        _deep = _long(b) or b.name in BRANCH
        for j, x in enumerate(line):
            nm = f'eveSK_{k}_{j}'; PT_BONES.append((nm, EW[x.name].copy(), par)); HELPER_SK[x.name] = nm; bones.append(nm); par = nm
            if _deep: continue
            for d in x.children_recursive:
                if d not in line and d.name not in HELPER_SK and d.name not in _inl: HELPER_SK[d.name] = nm
        if _deep:
            # chainLongest lines (10-25 bug: side pieces landed on node 0 -- the drape's top -- and stretched in game): each side
            # piece rides the node it branches from, so the deepest node first
            for j in range(len(line) - 1, -1, -1):
                for d in line[j].children_recursive:
                    if d not in line and d.name not in HELPER_SK and d.name not in _inl: HELPER_SK[d.name] = f'eveSK_{k}_{j}'
        tip = EW[line[-1].name] + (EW[line[-1].name] - EW[line[-2].name]) * 0.8
        PT_BONES.append((f'eveSK_{k}_end', tip, par)); bones.append(f'eveSK_{k}_end')
        kind = 'mech' if any(x in b.name for x in ('Spring', 'Blade', 'Wing', 'Tail', 'Hose', 'Cable', 'Skirt', 'Sword', 'Mech')) else \
               ('tie' if any(x in b.name.lower() for x in ('neck', 'tie', 'string')) else 'cloth')
        kind = next((v for x, v in OC.get('chainKind', {}).items() if x in b.name), kind)
        SKIRT_KIND[len(SKIRT)] = kind
        SKIRT.append(bones); found.append([b.name, len(line), round(L_, 2), kind])
    report['autoChains'] = found

# Eve helper / corrective bones -> the hunter helper joints the game drives for the same muscles (instead of merging them
# rigidly into Spine_2 / the clavicle, which flattened the chest when the arms moved)
HELPER = {}
for s in 'LR':
    for e, w in [('Pectro0', 'Pec_HJ_00'), ('Pectro1', 'Pec_HJ_01'), ('Trape0', 'Traps_HJ_00'), ('Trape1', 'Traps_HJ_01'),
                 ('Deltoid', 'Deltoid_HJ_00'), ('Becep', 'Biceps_HJ_00'), ('Tricep', 'Triceps_HJ_00')]:
        if f'Ab-{s}-{e}' in EW and f'{s}_{w}' in NG: HELPER[f'Ab-{s}-{e}'] = f'{s}_{w}'
    for e in ('Ab-{}-Breast', 'Ab-{}-Breast-Link', 'Dm-{}-Breast', 'Dm-{}-Breast-Point'):
        if e.format(s) in EW and f'{s}_BustJGL_CH_00' in NG: HELPER[e.format(s)] = f'{s}_BustJGL_CH_00'
report['helperMap'] = HELPER
joints = {}
changed = 0
for n in HORDER:
    p = HPAR[n]
    if p is None: continue
    l_new = (NG[p].inverted() @ NG[n]).translation; l_old = (HG[p].inverted() @ HG[n]).translation
    joints[n] = {'x': l_new.x, 'y': l_new.y, 'z': l_new.z}
    if (l_new - l_old).length > 1e-4: changed += 1
report['jointsChanged'] = changed
os.makedirs(OUTD, exist_ok=True)
json.dump(joints, open(os.path.join(OUTD, 'eve_outfit_joints.json'), 'w'), indent=1)
json.dump({'bind': {n: [list(r) for r in m] for n, m in NG.items()}, 'hunter': {n: [list(r) for r in m] for n, m in HG.items()},
           'parent': HPAR, 'eveHeadBlender': list(EW['Bip001-Head'])}, open(os.path.join(OUTD, 'eve_outfit_bind.json'), 'w'))
report['restCheck'] = {k: [round(x, 3) for x in (R90 @ NG[k]).translation] for k in ('COG', 'Hip', 'L_Thigh', 'L_Knee', 'L_Foot', 'Head', 'L_UpperArm', 'L_Hand')}
report['hunterRest'] = {k: [round(x, 3) for x in HW[k].translation] for k in report['restCheck']}

# ---------------- 4. weights -> hunter names ----------------
# Eve's twist helpers (Ab-*-UpperArm/Forearm/Thigh/Calf-Tw0/1) -> the hunter's own twist joints (*Twist_HJ_*, *_Shin_HJ_*),
# which the game drives from the limb every frame (the hunter innerwear skin uses them: calf = L_Shin_HJ_00/01).
# Version 1 split them onto the limb and the NEXT bone (calf 30 % onto the foot), which bent the mid shin with the ankle.
SPLIT = {}
TW = {'UpperArm': 'UpperArmTwist_HJ_0{}', 'Forearm': 'ForearmTwist_HJ_0{}', 'Thigh': 'ThighTwist_HJ_0{}', 'Calf': 'Shin_HJ_0{}'}
twist_map = {}
for s in 'LR':
    for limb, pat in TW.items():
        cands = [f'{s}_' + pat.format(i) for i in range(3) if f'{s}_' + pat.format(i) in NG]
        for t in (0, 1):
            hb = f'Ab-{s}-{limb}-Tw{t}'
            if hb not in arm.data.bones or not cands: continue
            pe = EW[hb]
            best = min(cands, key=lambda c: ((R90 @ NG[c]).translation - pe).length)
            SPLIT[hb] = {best: 1.0}
            twist_map[hb] = [best, round(((R90 @ NG[best]).translation - pe).length * 100, 1)]
report['twistMap_cm'] = twist_map
for root in OC.get('skirtThigh', []):
    sd = root.split('-')[1]; j = 1
    while f'{root}-{j:02d}' in arm.data.bones:
        t = min(0.75, 0.25 * (j - 1)); SPLIT[f'{root}-{j:02d}'] = {'Hip': 1.0 - t, f'{sd}_Thigh': t}; j += 1
# boneTo [[bone substring, joint], ...] (Scarlet's leg drape and back strip, user 10-25: "in game it never matches -- show me
# previews first"): those bones ride a body joint instead of physics, so the game shows what the preview shows. First match wins.
for _bn in arm.data.bones:
    _t = next((j_ for x_, j_ in OC.get('boneTo', []) if x_ in _bn.name), None)
    if _t and _t in NG: SPLIT[_bn.name] = {_t: 1.0}
# elbow correctives (Elbow / Elbow-Point / BrochiUp sit on the upper arm and follow half the elbow bend in the original;
# merged whole into the upper arm they left a sharp crease): half upper arm, half forearm = a half-angle elbow
for s in 'LR':
    ua, fa = E2W.get(f'Bip001-{s}-UpperArm'), E2W.get(f'Bip001-{s}-Forearm')
    for e in ('Ab-{}-Elbow', 'Dm-{}-Elbow', 'Dm-{}-Elbow-Point', 'Ab-{}-BrochiUp', 'Dm-{}-BrochiUp'):
        if e.format(s) in arm.data.bones: SPLIT[e.format(s)] = {ua: 0.5, fa: 0.5}
    for e in ('Ab-{}-BrochiDn', 'Dm-{}-BrochiDn'):
        if e.format(s) in arm.data.bones: SPLIT[e.format(s)] = {fa: 0.75, ua: 0.25}
eparent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
def mapped_ancestor(n):
    while n and n not in E2W: n = eparent.get(n)
    return n or 'Bip001-Pelvis'
SHB = float(os.environ.get('EVE_SHOULDER_BLEND', OC.get('shoulderBlend', '0')))
shb_n = [0]
weights = {}
merged = set()
for v in suit.data.vertices:
    acc = {}
    for vg in v.groups:
        if vg.weight <= 0: continue
        n = suit.vertex_groups[vg.group].name
        if n in SPLIT:
            for t, part in SPLIT[n].items(): acc[t] = acc.get(t, 0) + vg.weight * part
            continue
        if n in HELPER:
            acc[HELPER[n]] = acc.get(HELPER[n], 0) + vg.weight; continue
        if n in globals().get('HELPER_SK', {}):
            t_ = HELPER_SK[n]; acc[t_] = acc.get(t_, 0) + vg.weight; continue
        if n not in E2W: merged.add(n)
        t = E2W[n] if n in E2W else E2W[mapped_ancestor(n)]
        acc[t] = acc.get(t, 0) + vg.weight
    # heightBlend [[bone prefix, [[z, joint], ...]], ...] (Scarlet's drape / back strip, user 10-25: "still awkward, smooth it"):
    # a vertex mostly on those bones gets its joints from its height, blended linearly between the listed heights, so the
    # cloth bends smoothly from the hip over the thigh to the shin instead of breaking at each SB bone
    for _pre, _zs in OC.get('heightBlend', []):
        _sh = sum(vg.weight for vg in v.groups if suit.vertex_groups[vg.group].name.startswith(_pre))
        if _sh < 0.5: continue
        _z = (suit.matrix_world @ v.co).z
        if _z >= _zs[0][0]: _bl = {_zs[0][1]: 1.0}
        elif _z <= _zs[-1][0]: _bl = {_zs[-1][1]: 1.0}
        else:
            i_ = next(i for i in range(len(_zs) - 1) if _zs[i][0] >= _z >= _zs[i + 1][0])
            (z0, j0), (z1, j1) = _zs[i_], _zs[i_ + 1]; t_ = (z0 - _z) / max(1e-6, z0 - z1)
            _bl = {}; _bl[j0] = _bl.get(j0, 0) + 1 - t_; _bl[j1] = _bl.get(j1, 0) + t_
        acc = _bl; _hbz = report.setdefault('heightBlend', {}).setdefault(_pre, [0, 9.0, -9.0])
        _hbz[0] += 1; _hbz[1] = round(min(_hbz[1], _z), 3); _hbz[2] = round(max(_hbz[2], _z), 3)
        break
    # The hunter knee is a double hinge: the motion turns L_Knee AND its child L_Shin by the same angle (jog: 56.5 deg each,
    # 113 deg in total) and the hunter calf skin rides L_Shin. Eve's calf therefore goes to *_Shin (full bend, same as the
    # foot); only where her skin blends thigh -> calf (the knee) half of the calf share stays on *_Knee.
    for s_ in 'LR':
        k = acc.pop(f'{s_}_Knee', 0.0)
        if k > 0:
            if acc.get(f'{s_}_Thigh', 0) > 0:
                acc[f'{s_}_Knee'] = k * 0.5; acc[f'{s_}_Shin'] = acc.get(f'{s_}_Shin', 0) + k * 0.5
            else:
                acc[f'{s_}_Shin'] = acc.get(f'{s_}_Shin', 0) + k
    # shoulder (user 10-18, bikini running: shoulder pinches when the arm swings; Ocean Maid's frills hid it): Eve blends
    # the clavicle straight into the upper arm, the hunter skins that zone to Deltoid_HJ_* helpers the game drives between
    # the two. Move the overlap (min of clavicle share and upper-arm share) x EVE_SHOULDER_BLEND onto *_UpperArmDouble_HJ_00
    # (measured in game 10-18: it turns ~40 % of the upper arm; Deltoid_HJ_00 turns 100 %, Shoulder_HJ_00 ~0 %).
    if SHB > 0:
        for s_ in 'LR':
            sh = acc.get(f'{s_}_Shoulder', 0.0)
            ak = [k for k in (f'{s_}_UpperArm', f'{s_}_UpperArmTwist_HJ_00', f'{s_}_UpperArmTwist_HJ_01') if acc.get(k, 0) > 0]
            am = sum(acc[k] for k in ak)
            if sh > 0 and am > 0 and f'{s_}_UpperArmDouble_HJ_00' in NG:
                m = min(sh, am) * SHB
                acc[f'{s_}_Shoulder'] = sh - m
                for k in ak: acc[k] -= m * acc[k] / am
                acc[f'{s_}_UpperArmDouble_HJ_00'] = acc.get(f'{s_}_UpperArmDouble_HJ_00', 0.0) + 2 * m
                shb_n[0] += 1
    if v.index in DRAPE_W:
        ws, fade = DRAPE_W[v.index]
        acc = {k_: w_ * (1 - fade) for k_, w_ in acc.items()}
        for k_, w_ in ws.items(): acc[k_] = acc.get(k_, 0) + w_ * fade
    weights[v.index] = acc
# shoulder weights from the hunter (user 10-18, bikini in game: shoulder corner looks square / sticks out when moving; the
# FK preview looks fine, so it is the game-driven shoulder helpers Eve's weights don't fit). The hunter innerwear body is
# skinned for exactly those helpers (Shoulder_HJ_00, Deltoid_HJ_01/02, UpperArmTwist_HJ_01 ...): within EVE_SHOULDER_R of the
# shoulder joint, blend each Eve vertex toward the weights of the nearest hunter-body vertices (positions compared relative to
# each side's own shoulder joint), full at the joint, fading to Eve's own at the radius. Breast vertices are left alone.
SHT = float(os.environ.get('EVE_SHOULDER_XFER', OC.get('shoulderXfer', '1.0')))   # user 10-18: bikini shoulder better in game -> default for every Eve outfit
if SHT > 0:
    from mathutils import kdtree
    hf = INNER + f'2/ch03_002_{SUB}2.mesh.241111606'
    before = set(bpy.data.objects); before_c = set(bpy.data.collections)
    bpy.ops.re_mesh.importfile(filepath=hf, files=[{'name': os.path.basename(hf)}], directory=os.path.dirname(hf))
    hobjs = [o for o in set(bpy.data.objects) - before if o.type == 'MESH']
    HV = []
    for o in hobjs:
        if 'LOD_' in o.name and 'LOD_0' not in o.name: continue
        gn = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            w = {gn[g.group]: g.weight for g in v.groups if g.weight > 0 and gn[g.group] in NG}
            if w: HV.append((o.matrix_world @ v.co, w))
    for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
    for c in set(bpy.data.collections) - before_c: bpy.data.collections.remove(c)
    kd = kdtree.KDTree(len(HV))
    for i, (co, _) in enumerate(HV): kd.insert(co, i)
    kd.balance()
    RAD = float(os.environ.get('EVE_SHOULDER_R', '0.13'))
    nx = 0
    for v in suit.data.vertices:
        acc = weights.get(v.index)
        if not acc or any('Bust' in k for k in acc): continue
        co = suit.matrix_world @ v.co
        for s_ in 'LR':
            je, jh = POS.get(f'{s_}_UpperArm'), HW[f'{s_}_UpperArm'].translation
            if je is None: continue
            d = (co - je).length
            if d >= RAD: continue
            t = 1 - d / RAD; f = SHT * t * t * (3 - 2 * t)
            hw = {}; tot = 0
            for (hco, hi, hd) in kd.find_n(co - je + jh, 4):
                k = 1 / (hd + 1e-4); tot += k
                for n_, w_ in HV[hi][1].items(): hw[n_] = hw.get(n_, 0) + w_ * k
            new = {k: w_ * (1 - f) for k, w_ in acc.items()}
            for n_, w_ in hw.items(): new[n_] = new.get(n_, 0) + f * w_ / tot
            weights[v.index] = new; nx += 1
            break
    report['shoulderXfer'] = {'k': SHT, 'r': RAD, 'verts': nx, 'hunterVerts': len(HV)}
# knee weights from the hunter (user 10-18, sitting: knees fold / ridges on the boots): same idea as the shoulder -- the hunter
# leg part is skinned to the knee helpers the game drives (Knee_HJ_00, KneeRX_HJ_00, Shin_HJ_00, ThighTwist_HJ_02); within
# EVE_KNEE_R of each knee joint, blend toward the nearest hunter leg vertices' weights (relative to each side's knee).
KNT = float(os.environ.get('EVE_KNEE_XFER', OC.get('kneeXfer', '1.0')))
if KNT > 0:
    from mathutils import kdtree
    hf = INNER + f'4/ch03_002_{SUB}4.mesh.241111606'
    before = set(bpy.data.objects); before_c = set(bpy.data.collections)
    bpy.ops.re_mesh.importfile(filepath=hf, files=[{'name': os.path.basename(hf)}], directory=os.path.dirname(hf))
    HV = []
    for o in [o for o in set(bpy.data.objects) - before if o.type == 'MESH']:
        if 'LOD_' in o.name and 'LOD_0' not in o.name: continue
        gn = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            w = {gn[g.group]: g.weight for g in v.groups if g.weight > 0 and gn[g.group] in NG}
            if w: HV.append((o.matrix_world @ v.co, w))
    for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
    for c in set(bpy.data.collections) - before_c: bpy.data.collections.remove(c)
    kd = kdtree.KDTree(len(HV))
    for i, (co, _) in enumerate(HV): kd.insert(co, i)
    kd.balance()
    # zones: knee, and (user 10-18, sitting: ridges where the thigh folds at the hip) the thigh root -- hunter Hip_HJ_00,
    # ThighTwist_HJ_00, Hip_HJ_01, ThighRZ/RX_HJ_01. Jiggle (bust / butt) vertices keep Eve's own weights.
    ZONES = [('Knee', float(os.environ.get('EVE_KNEE_R', '0.12')))]
    if float(os.environ.get('EVE_HIP_XFER', OC.get('hipXfer', '1.0'))) > 0: ZONES.append(('Thigh', float(os.environ.get('EVE_HIP_R', '0.15'))))
    nx = 0; nh = 0
    for v in suit.data.vertices:
        acc = weights.get(v.index)
        if not acc or any('JGL' in k or 'eveSK' in k for k in acc): continue
        co = suit.matrix_world @ v.co
        done = False
        for jn, RAD in ZONES:
          for s_ in 'LR':
            if done: break
            je, jh = POS.get(f'{s_}_{jn}'), HW[f'{s_}_{jn}'].translation
            if je is None: continue
            d = (co - je).length
            if d >= RAD: continue
            t = 1 - d / RAD; f = KNT * t * t * (3 - 2 * t)
            hw = {}; tot = 0
            for (hco, hi, hd) in kd.find_n(co - je + jh, 4):
                k = 1 / (hd + 1e-4); tot += k
                for n_, w_ in HV[hi][1].items(): hw[n_] = hw.get(n_, 0) + w_ * k
            new = {k: w_ * (1 - f) for k, w_ in acc.items()}
            for n_, w_ in hw.items(): new[n_] = new.get(n_, 0) + f * w_ / tot
            weights[v.index] = new; acc = new; done = True
            if jn == 'Knee': nx += 1
            else: nh += 1
    report['kneeXfer'] = {'k': KNT, 'zones': ZONES, 'kneeVerts': nx, 'hipVerts': nh, 'hunterVerts': len(HV)}
# physics joints (eveSK chains, drapes, bust / butt jiggle) only move inside the body part's own skeleton: every vertex they
# carry goes to the body part (10-19: Blue Samurai sleeve drapes sat on the arm part)
DRAPE_BONES = {b_ for i_, bl_ in enumerate(SKIRT) if SKIRT_KIND.get(i_) == 'drape' for b_ in bl_}
if OC.get('split') and suit.data.attributes.get('evepart'):
    _at = suit.data.attributes['evepart']; _mv = 0
    for vi, acc in weights.items():
        _dw = sum(w_ for k_, w_ in acc.items() if k_ in DRAPE_BONES)
        if OC.get('drapePart') and _dw > 0.01:
            if _at.data[vi].value != int(OC['drapePart']): _at.data[vi].value = int(OC['drapePart']); _mv += 1
            continue
        if _at.data[vi].value != 2 and sum(w_ for k_, w_ in acc.items() if k_.startswith('eveSK') or 'JGL' in k_) > 0.15:
            _at.data[vi].value = 2; _mv += 1
    report['physToBody'] = _mv
# cleavage seam (user 10-19, Cyber Bunny: the corset tore open down the middle in game): near the midline the left / right
# bust jiggle weights are evened out, so both sides of the seam follow the same (average) jiggle and cannot split
_BS = float(OC.get('bustSeam', '0.02'))
if _BS > 0:
    _ns = 0
    for vi, acc in weights.items():
        x_ = abs(suit.data.vertices[vi].co.x)
        if x_ >= _BS: continue
        l_, r_ = acc.get('L_BustJGL_CH_00', 0.0), acc.get('R_BustJGL_CH_00', 0.0)
        if l_ + r_ <= 0: continue
        t_ = 1 - x_ / _BS; m_ = (l_ + r_) / 2
        acc['L_BustJGL_CH_00'] = l_ + (m_ - l_) * t_; acc['R_BustJGL_CH_00'] = r_ + (m_ - r_) * t_; _ns += 1
    report['bustSeam'] = _ns
_nwl = 0
for _gl in weld_groups():
    _gl = [i for i in _gl if i in weights]
    if len(_gl) < 2: continue
    _avg = {}
    for i in _gl:
        for k_, w_ in weights[i].items(): _avg[k_] = _avg.get(k_, 0.0) + w_ / len(_gl)
    for i in _gl: weights[i] = dict(_avg)
    _nwl += 1
report['weldWeights'] = _nwl
suit.vertex_groups.clear()
vgs = {}
for vi, acc in weights.items():
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:6]; tot = sum(w for _, w in top) or 1
    for t, w in top:
        if t not in vgs: vgs[t] = suit.vertex_groups.new(name=t)
        vgs[t].add([vi], w / tot, 'REPLACE')
# butt jiggle weights: around each cheek centre move up to 45 % of the vertex's weight onto the jiggle joint (smooth falloff)
BUTT_R = 0.09
for s in 'LR':
    n = f'{s}_HipJGL_CH_00'
    if n not in EXTRA: continue
    cheek = Vector(report['buttCheek'][s]); g = suit.vertex_groups.new(name=n); vgs[n] = g; cnt = 0
    for v in suit.data.vertices:
        d = (v.co - cheek).length
        if d >= BUTT_R or v.co.y < cheek.y - 0.08: continue
        x = 1 - d / BUTT_R; a = 0.45 * x * x * (3 - 2 * x)
        if a < 0.01: continue
        for ge in v.groups: ge.weight *= (1 - a)
        g.add([v.index], a, 'REPLACE'); cnt += 1
    report.setdefault('buttVerts', {})[s] = cnt
for v in suit.data.vertices:                     # keep max 6 influences (Wilds limit) after adding the jiggle share
    gs = sorted(v.groups, key=lambda g_: -g_.weight)
    if len(gs) > 6:
        for g_ in gs[6:]: suit.vertex_groups[g_.group].remove([v.index])
        tot = sum(g_.weight for g_ in gs[:6]) or 1
        for g_ in gs[:6]: suit.vertex_groups[g_.group].add([v.index], g_.weight / tot, 'REPLACE')
report['shoulderBlend'] = {'k': SHB, 'verts': shb_n[0]}; report['mergedHelpers'] = len(merged); report['twistSplit'] = len(SPLIT); report['skinBones'] = sorted(vgs)
bpy.data.objects.remove(arm, do_unlink=True)

# ---------------- 5. export ----------------
bind = ref.copy(); bind.data = ref.data.copy(); bind.name = 'EveOutfitBind'; mesh_col.objects.link(bind)
bpy.ops.object.select_all(action='DESELECT'); bind.select_set(True); bpy.context.view_layer.objects.active = bind
bpy.ops.object.mode_set(mode='EDIT')
for eb in bind.data.edit_bones: eb.use_connect = False
for eb in bind.data.edit_bones:
    L = max(eb.length, 0.01); eb.matrix = R90 @ NG[eb.name]; eb.length = L
for n, (par, pos) in EXTRA.items():
    eb = bind.data.edit_bones.new(n); eb.head = Vector((0, 0, 0)); eb.tail = Vector((0, 0.03, 0))
    eb.matrix = R90 @ NG[n]; eb.length = 0.03; eb.parent = bind.data.edit_bones[par]
for n, h, par in PT_BONES:
    eb = bind.data.edit_bones.new(n); eb.head = Vector((0, 0, 0)); eb.tail = Vector((0, 0.03, 0))
    eb.matrix = Matrix.Translation(h) @ R90; eb.length = 0.03; eb.parent = bind.data.edit_bones[par]; eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
if pt is not None:
    for c in list(pt.users_collection): c.objects.unlink(pt)
    mesh_col.objects.link(pt)
if hpin:
    for c in list(hpin.users_collection): c.objects.unlink(hpin)
    mesh_col.objects.link(hpin)
    while len(hpin.data.uv_layers) > 1: hpin.data.uv_layers.remove(hpin.data.uv_layers[-1])
    for ca in list(hpin.data.color_attributes): hpin.data.color_attributes.remove(ca)
if pt is not None:
    while len(pt.data.uv_layers) > 1: pt.data.uv_layers.remove(pt.data.uv_layers[-1])
    for ca in list(pt.data.color_attributes): pt.data.color_attributes.remove(ca)
while len(suit.data.uv_layers) > 1: suit.data.uv_layers.remove(suit.data.uv_layers[-1])
for ca in list(suit.data.color_attributes): suit.data.color_attributes.remove(ca)
for c in list(suit.users_collection): c.objects.unlink(suit)
mesh_col.objects.link(suit)
import bmesh
def keep_part(ob, n):
    # by face (majority of its corners' part), then drop vertices left without faces -- deleting by vertex left loose
    # vertices on the seam, which the mesh exporter refuses (10-18, Moran)
    bm = bmesh.new(); bm.from_mesh(ob.data); lay = bm.verts.layers.int.get('evepart')
    def fpart(f):
        c = {}
        for v in f.verts: c[v[lay]] = c.get(v[lay], 0) + 1
        return max(c, key=c.get)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if fpart(f) != n], context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(ob.data); bm.free()
extra_parts = []
if SPLIT_PARTS:
    # user 10-18: a shading step at the seam between body and leg parts -- each cut mesh got normals from its own faces only
    suit.data.normals_split_custom_set_from_vertices([tuple(v.normal) for v in suit.data.vertices])
def drop_loose(col):
    # vertices without faces (some SB meshes carry loose points / wire edges): the mesh exporter refuses them
    n_ = 0
    for o in col.objects:
        if o.type != 'MESH': continue
        bm = bmesh.new(); bm.from_mesh(o.data)
        lv = [v for v in bm.verts if not v.link_faces]; n_ += len(lv)
        if lv: bmesh.ops.delete(bm, geom=lv, context='VERTS'); bm.to_mesh(o.data)
        bm.free()
    return n_
if SPLIT_PARTS:
    _short = {m: f'{PFX}{i:02d}' for i, m in enumerate(KEYS)}
    for n in sorted(SPLIT_PARTS):
        if n == 2: continue
        ob = suit.copy(); ob.data = suit.data.copy(); keep_part(ob, n)
        col = bpy.data.collections.new(f'{OPRE}{n}.mesh'); bpy.context.scene.collection.children.link(col); col.objects.link(ob)
        bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='MATERIAL'); bpy.ops.object.mode_set(mode='OBJECT')
        si = 0
        for o in sorted([o for o in col.objects if o.type == 'MESH'], key=lambda o: KEYS.index(o.data.materials[o.data.polygons[0].material_index].name) if o.data.polygons else 99):
            if not o.data.polygons: bpy.data.objects.remove(o, do_unlink=True); continue
            m = o.data.materials[o.data.polygons[0].material_index]; key = _short[m.name]
            o.data.materials.clear(); o.data.materials.append(bpy.data.materials.get(key) or bpy.data.materials.new(key))
            o.name = f'Group_0_Sub_{si}__{key}'; si += 1
            o.parent = bind
            for md in list(o.modifiers): o.modifiers.remove(md)
            md = o.modifiers.new('Armature', 'ARMATURE'); md.object = bind
            extra_parts.append(o); report.setdefault('splitParts', {}).setdefault(n, []).append([key, m.name, len(o.data.vertices)])
        col.objects.link(bind)
        out = PART_DIR + f'{n}/{OPRE}{n}.mesh.241111606'; os.makedirs(os.path.dirname(out), exist_ok=True)
        report.setdefault('looseDropped', {})[n] = drop_loose(col)
        report[f'exportPart{n}'] = list(bpy.ops.re_mesh.exportfile(filepath=out, targetCollection=col.name, exportAllLODs=False, exportBoundingBoxes=True))
        col.objects.unlink(bind)
        for o in col.objects: o.name = f'Part{n}_' + o.name   # free the Group_0_Sub_* names for the body part (else it gets .001)
    keep_part(suit, 2)
bpy.ops.object.select_all(action='DESELECT'); suit.select_set(True); bpy.context.view_layer.objects.active = suit
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.separate(type='MATERIAL'); bpy.ops.object.mode_set(mode='OBJECT')
short = {m: f'{PFX}{i:02d}' for i, m in enumerate(KEYS)}
parts, preview_mat = [], {}
sub = 0
for o in sorted([o for o in mesh_col.objects if o.type == 'MESH'], key=lambda o: KEYS.index(o.data.materials[o.data.polygons[0].material_index].name) if o.data.polygons else 99):
    if not o.data.polygons:
        bpy.data.objects.remove(o, do_unlink=True); continue
    m = o.data.materials[o.data.polygons[0].material_index]
    key = short[m.name]
    preview_mat[o.name] = m
    o.data.materials.clear(); o.data.materials.append(bpy.data.materials.get(key) or bpy.data.materials.new(key))
    newname = f'Group_0_Sub_{sub}__{key}'; preview_mat[newname] = preview_mat.pop(o.name); o.name = newname; sub += 1
    o.parent = bind
    for md in list(o.modifiers): o.modifiers.remove(md)
    md = o.modifiers.new('Armature', 'ARMATURE'); md.object = bind
    parts.append(o); report.setdefault('parts', []).append([o.name, m.name, len(o.data.vertices)])
body_out = PART_DIR + f'2/{OPRE}2.mesh.241111606'
os.makedirs(os.path.dirname(body_out), exist_ok=True)
report.setdefault('looseDropped', {})[2] = drop_loose(mesh_col)
report['exportBody'] = list(bpy.ops.re_mesh.exportfile(filepath=body_out, targetCollection=mesh_col.name, exportAllLODs=False, exportBoundingBoxes=True))
# body part chain2: keep the innerwear's own bust jiggle groups (same joint names, larger range for the larger bust),
# add butt jiggle groups, drop the necklace chain (its bones are not in this mesh)
import importlib, copy, addon_utils
addon_utils.enable('RE_Chain_Editor', default_set=True, handle_error=None)
fc2 = importlib.import_module('RE_Chain_Editor.modules.file_re_chain2')
hash_wide = importlib.import_module('RE_Chain_Editor.modules.pymmh3').hash_wide
VC = P + f'wilds-inner{SUB}/extra/ch03_002_{SUB}2.chain2.14'
c2 = fc2.Chain2File(); f_ = open(VC, 'rb'); c2.read(f_); f_.close()
busts = [g for g in c2.ChainGroupList if g.terminateNodeNameHash in (hash_wide('L_BustJGL_CH_00'), hash_wide('R_BustJGL_CH_00'))]
if not busts:
    # type 1 innerwear (100) has no bust jiggle groups: start from the type 2 body chain (same joint names) instead
    VC = P + 'wilds-inner101/extra/ch03_002_1012.chain2.14'
    c2 = fc2.Chain2File(); f_ = open(VC, 'rb'); c2.read(f_); f_.close()
    busts = [g for g in c2.ChainGroupList if g.terminateNodeNameHash in (hash_wide('L_BustJGL_CH_00'), hash_wide('R_BustJGL_CH_00'))]
    report['chainBase'] = 'ch03_002_1012 (no bust groups in the part chain)'
# user 10-18: "bust physics must not differ much from the original" -> the innerwear's own jiggle range and damping by
# default (was range x1.4, damping 0.08). EVE_BUST_JIGGLE / EVE_BUST_DAMP still override.
JIG = float(os.environ.get('EVE_BUST_JIGGLE', '1.0'))
DAMP = os.environ.get('EVE_BUST_DAMP')
for g in busts:
    for n_ in g.nodeList:
        if n_.jiggleData:
            report.setdefault('bustJiggleOrig', []).append({'rangeX': round(n_.jiggleData.rangeX, 4), 'damping': round(n_.jiggleData.damping, 4)})
            n_.jiggleData.rangeX *= JIG
            if DAMP: n_.jiggleData.damping = float(DAMP)
            # the innerwear's jiggle centre sits 3 cm off its joint (its JGL joint is not at the breast centre); ours is at the
            # breast centre, so centre the range on the joint (with the offset the breasts were pulled into the chest in game)
            n_.jiggleData.rangeOffsetX = n_.jiggleData.rangeOffsetY = n_.jiggleData.rangeOffsetZ = 0.0
groups = list(busts)
for s in 'LR':
    if f'{s}_HipJGL_CH_00' not in EXTRA or not busts: continue
    g = copy.deepcopy(busts[0]); g.terminateNodeNameHash = hash_wide(f'{s}_HipJGL_CH_00')
    for n_ in g.nodeList:
        if n_.jiggleData: n_.jiggleData.rangeX = 0.025; n_.jiggleData.springForce = 0.05; n_.jiggleData.damping = 0.12
    groups.append(g)
# ponytail chains: the vanilla Wilds ponytail's own physics (hairstyle 31, ch01_001_0518): its setting 1 (gravity -9.8,
# damping 0.074, no spring, wind 0.5), its Ponytail2 group / node values, links between neighbouring chains, and its
# collisions (two head capsules, the shoulder-to-shoulder capsule behind the neck); plus the long-ponytail mod's Spine_2
# back capsule, since Eve's tail reaches the mid back. Node angle-limit frames point at the next node in the unrotated game
# frame, like the vanilla ones (-90 deg about Z = straight down).
VPC = P + 'wilds-hair/natives/stm/art/model/character/ch01/001/0/518/ch01_001_0518.chain2.14'
vpc = fc2.Chain2File(); f_ = open(VPC, 'rb'); vpc.read(f_); f_.close()
# back capsule on Spine_2 for the long ponytail (values measured once from a long-ponytail hair mod's chain2 so the
# builder does not need that mod's file; shape 5, both ends on Spine_2)
def _spine2_back_capsule():
    c_ = copy.deepcopy(vpc.ChainCollisionList[0])
    for k_, v_ in dict(posX=-0.004, posY=-0.002, posZ=0.07, pairPosX=0.004, pairPosY=-0.296, pairPosZ=0.003,
                       rotOffsetX=0.0, rotOffsetY=0.0, rotOffsetZ=0.0, rotOffsetW=1.0, rotationOrder=0,
                       radius=0.20326045, endRadius=0.198, lerp=0.0, chainCollisionShape=5, div=0,
                       collisionFilterFlags=-1).items():
        setattr(c_, k_, v_)
    c_.jointNameHash = c_.pairJointNameHash = hash_wide('Spine_2')
    return c_
s_pt = copy.deepcopy(next(s for s in vpc.ChainSettingsList if s.id == 1)); s_pt.id = len(c2.ChainSettingsList)
c2.ChainSettingsList.append(s_pt); c2.Header.chainSettingsCount = len(c2.ChainSettingsList)
vg = next(g for g in vpc.ChainGroupList if g.terminateNodeNameHash == hash_wide('Ponytail2_CH_end'))
pt_pos = {n: h for n, h, _ in PT_BONES}
for k in range(K_PT):
    names = [ptname(k, j) for j in range(M_PT)]
    g = copy.deepcopy(vg); g.settingID = s_pt.id; g.terminateNodeNameHash = hash_wide(names[-1])
    nodes = []
    for j, nm in enumerate(names):
        n_ = copy.deepcopy(vg.nodeList[min(j, len(vg.nodeList) - 2)] if j < M_PT - 1 else vg.nodeList[-1])
        n_.windCoef = 0.5 + 0.5 * j / (M_PT - 1)
        if j < M_PT - 1:
            dg = (R90i.to_3x3() @ (pt_pos[names[j + 1]] - pt_pos[nm])).normalized()
            q = Vector((1.0, 0.0, 0.0)).rotation_difference(dg)
        else:
            q = Quaternion()
        n_.angleLimitDirectionX, n_.angleLimitDirectionY, n_.angleLimitDirectionZ, n_.angleLimitDirectionW = q.x, q.y, q.z, q.w
        nodes.append(n_)
    g.nodeList = nodes; g.nodeCount = len(nodes)
    for sg in g.subGroupList: sg.nodeList = copy.deepcopy(nodes)
    groups.append(g)
# ornament chain: the ponytail group's node values, its own setting (damping 0.05, small spring like the hair mod) and no hair link
# (first try damping 0.15 / spring 0.02 / limit 35 / collisions on: did not move in game, user video 10-18)
if any(n == 'eveORN_CH_00' for n, _, _ in PT_BONES):
    s_orn = copy.deepcopy(s_pt); s_orn.id = len(c2.ChainSettingsList)
    s_orn.damping = float(os.environ.get('EVE_ORN_DAMP', '0.05')); s_orn.minDamping = s_orn.damping
    s_orn.springForce = float(os.environ.get('EVE_ORN_SPRING', '0.006')); s_orn.windEffectCoef = 0.3; s_orn.envWindEffectCoef = 0.2
    c2.ChainSettingsList.append(s_orn); c2.Header.chainSettingsCount = len(c2.ChainSettingsList)
    onames = [n for n, _, _ in PT_BONES if n.startswith('eveORN_CH_')]
    g = copy.deepcopy(vg); g.settingID = s_orn.id; g.terminateNodeNameHash = hash_wide(onames[-1])
    nodes = []
    for j, nm in enumerate(onames):
        n_ = copy.deepcopy(vg.nodeList[min(j, len(vg.nodeList) - 2)] if j < len(onames) - 1 else vg.nodeList[-1])
        n_.windCoef = 0.6; n_.angleLimitRad = math.radians(float(os.environ.get('EVE_ORN_LIMIT', '50')))
        # no collision: the blades hang inside the mod's large Spine_2 back capsule and were held still by it
        n_.collisionRadius = 0.0; n_.collisionFilterFlags = 0; n_.gravityCoef = 1.0
        if j < len(onames) - 1:
            dg = (R90i.to_3x3() @ (pt_pos[onames[j + 1]] - pt_pos[nm])).normalized(); q = Vector((1.0, 0.0, 0.0)).rotation_difference(dg)
        else:
            q = Quaternion()
        n_.angleLimitDirectionX, n_.angleLimitDirectionY, n_.angleLimitDirectionZ, n_.angleLimitDirectionW = q.x, q.y, q.z, q.w
        nodes.append(n_)
    g.nodeList = nodes; g.nodeCount = len(nodes)
    for sg in g.subGroupList: sg.nodeList = copy.deepcopy(nodes)
    groups.append(g)
    report['ornGroup'] = len(nodes)
links = []
for a, b in (((0, 1), (1, 2)) if K_PT else ()):
    L_ = copy.deepcopy(vpc.ChainLinkList[0])
    L_.terminateNodeNameHashA = hash_wide(ptname(a, M_PT - 1)); L_.terminateNodeNameHashB = hash_wide(ptname(b, M_PT - 1))
    links.append(L_)
c2.ChainLinkList = links; c2.Header.chainLinkCount = len(links)
bone_hashes = {hash_wide(b.name) for b in bind.data.bones}
# backCapsule False (Scarlet's own hair, 10-25): the big Spine_2 capsule made for Eve's ponytail pushed her back hair out
cols = [copy.deepcopy(c_) for c_ in vpc.ChainCollisionList] + ([_spine2_back_capsule()] if OC.get('backCapsule', True) else [])
c2.ChainCollisionList = [c_ for c_ in cols if c_.jointNameHash in bone_hashes and c_.pairJointNameHash in bone_hashes]
if OC.get('fitCollisions') and SKIRT:
    # Scarlet's own hair (user 10-25: front locks stood out forward, the back hair floated off the back): the vanilla hunter
    # hair capsules (head + the shoulder capsule behind the neck) sat right where her strands start and pushed them out.
    # Instead, capsules fitted to her own strands at rest: a torso capsule from Spine_1 to the neck, shifted forward so its
    # surface lies just inside both the back hair and the front locks, and a neck -> head capsule just inside the strands
    # round the head. At rest nothing is pushed; moving, the strands slide over her back / chest instead of going through.
    _tpl = next(c_ for c_ in vpc.ChainCollisionList if c_.chainCollisionShape == 2)
    _pp = {n: h for n, h, _ in PT_BONES}
    _hn = lambda kinds: [_pp[n] for i_, b_ in enumerate(SKIRT) if SKIRT_KIND.get(i_) in kinds for n in b_[1:]]
    def _cap(ja, wa, jb, wb, r):
        c_ = copy.deepcopy(_tpl)
        la = (R90 @ NG[ja]).inverted() @ wa; lb = (R90 @ NG[jb]).inverted() @ wb
        for k_, v_ in dict(posX=la.x, posY=la.y, posZ=la.z, pairPosX=lb.x, pairPosY=lb.y, pairPosZ=lb.z, rotOffsetX=0.0, rotOffsetY=0.0,
                           rotOffsetZ=0.0, rotOffsetW=1.0, radius=r, endRadius=r, lerp=0.0, chainCollisionShape=2, div=0, collisionFilterFlags=-1).items():
            setattr(c_, k_, v_)
        c_.jointNameHash = hash_wide(ja); c_.pairJointNameHash = hash_wide(jb)
        return c_
    def _segd(p, a, b):
        ab = b - a; t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared)); return (p - (a + ab * t)).length, (p - a).dot(ab) / ab.length_squared
    A, B, H = [(R90 @ NG[n]).translation.copy() for n in ('Spine_1', 'Neck_0', 'Head')]
    ax = (B - A).normalized()
    perp = lambda p: (p - A) - ax * (p - A).dot(ax)
    fr, bk = _hn(('hairF',)), _hn(('hairL',))
    _cols = []
    _mg = float(OC.get('hairColRadius', 0.02)) + 0.004 if OC.get('fitCollisions') == 2 else 0.015   # clearance to the strands at rest
    if fr and bk:
        fwd = (sum((perp(p) for p in fr), Vector()) / len(fr) - sum((perp(p) for p in bk), Vector()) / len(bk)).normalized()
        inr = lambda p: 0.0 <= (p - A).dot(ax) <= (B - A).length
        db = min((-perp(p).dot(fwd) for p in bk if inr(p)), default=0.1); df = min((perp(p).dot(fwd) for p in fr if inr(p)), default=0.1)
        f_ = (df - db) / 2; r_ = (df + db) / 2 - 0.02
        wa, wb = A + fwd * f_, B + fwd * f_
        r_ = min(r_, min(_segd(p, wa, wb)[0] for p in _hn(('hairF', 'hairL', 'hairS')) if 0 <= _segd(p, wa, wb)[1] <= 1) - _mg)
        r_ = max(0.04, min(0.16, r_))
        _cols.append(_cap('Spine_1', wa, 'Neck_0', wb, r_)); report['fitTorso'] = [round(f_, 3), round(r_, 3), round(db, 3), round(df, 3)]
    hb = H + (H - B).normalized() * 0.08
    rh = min((_segd(p, B, hb)[0] for p in _hn(('hairF', 'hairL', 'hairS'))), default=0.06) - _mg
    rh = max(0.03, min(0.08, rh))
    _cols.append(_cap('Neck_0', B, 'Head', hb, rh)); report['fitHead'] = round(rh, 3)
    # the torso one stays thin (her front locks start close to the neck); the locks also rest on the shoulders and the
    # bust: one capsule per clavicle and one across the bust, each just inside the strands at rest
    _all = _hn(('hairF', 'hairL', 'hairS'))
    _pairs = (('L_Shoulder', 'L_UpperArm'), ('R_Shoulder', 'R_UpperArm'), ('L_BustJGL_CH_00', 'R_BustJGL_CH_00'))
    if OC.get('fitCollisions') == 2:
        # v2 (user 10-25: the strands now hang right but go through her back / chest when she moves): the hair nodes get a
        # bigger collision radius (hairColRadius, the strand cards are wider than 1 cm) and more body parts are covered --
        # the upper arms and each breast on its own; every capsule still stops that radius + 4 mm short of the strands at
        # rest, so nothing floats
        _nr = float(OC.get('hairColRadius', 0.02))
        _pairs = (('L_Shoulder', 'L_UpperArm'), ('R_Shoulder', 'R_UpperArm'), ('L_UpperArm', 'L_Forearm'), ('R_UpperArm', 'R_Forearm'),
                  ('L_BustJGL_CH_00', 'L_BustJGL_CH_00'), ('R_BustJGL_CH_00', 'R_BustJGL_CH_00'))
        _cl = lambda wa, wb: min(_segd(p, wa, wb)[0] for p in _all) - _nr - 0.004
    for ja, jb in _pairs:
        if ja not in NG or jb not in NG: continue
        wa, wb = (R90 @ NG[ja]).translation.copy(), (R90 @ NG[jb]).translation.copy()
        if ja == jb: wb = wa + Vector((0.0, 0.0, 0.001))   # one breast: a sphere on its jiggle joint
        r_ = (_cl(wa, wb) if OC.get('fitCollisions') == 2 else min(_segd(p, wa, wb)[0] for p in _all) - 0.015)
        report.setdefault('fitExtra', []).append([ja, jb, round(r_, 3)])
        if r_ >= 0.025: _cols.append(_cap(ja, wa, jb, wb, min(r_, 0.10)))
    c2.ChainCollisionList = _cols
c2.Header.chainModelCollisionCount = len(c2.ChainCollisionList)
report['ptCollisions'] = [[c_.chainCollisionShape, round(c_.radius, 3), round(c_.endRadius, 3)] for c_ in c2.ChainCollisionList]
report['ptCollisionsDropped'] = len(cols) - len(c2.ChainCollisionList)
# the bust / butt jiggle nodes must not collide with the hair collisions
for g in groups:
    if g.settingID != s_pt.id:
        for n_ in g.nodeList: n_.collisionFilterFlags = 0; n_.collisionRadius = 0.0
report['ptGroups'] = K_PT
if SKIRT:
    # 10-20 (game test, Angpa / Planet Dive 7th): every extra chain SETTING made the ponytail nearly freeze (tip moved 1-3 cm
    # instead of ~1 m; same groups with only the 4 base settings -> hair free). So no new settings: skirts and cloth-like kinds
    # share the ponytail setting, stiff kinds (mech / tie) the ornament one; the per-kind feel stays in the node angle limits
    # (and drape gravity). kindSet's damping / spring are no longer used.
    s_sk = s_pt
    s_orn_ = next((s_ for s_ in c2.ChainSettingsList if s_ is not s_pt and s_.id == s_pt.id + 1), s_pt)
    KSET = {}
    _kinds = {'mech': (0.45, 0.25, 8), 'tie': (0.3, 0.08, 30), 'cloth': (0.2, 0.03, 45), 'drape': (0.25, 0.0, 75), 'veil': (0.4, 0.15, 15)}
    for _k, _l in OC.get('kindLimit', {}).items(): _kinds[_k] = (_kinds.get(_k, _kinds['cloth'])[0], _kinds.get(_k, _kinds['cloth'])[1], _l)   # new kinds: cloth-like
    for _k, _v in OC.get('kindSet', {}).items(): _kinds[_k] = tuple(_v)
    for kind, (damp, spring, lim) in _kinds.items():
        KSET[kind] = (s_orn_ if kind in ('mech', 'tie') else s_pt, lim)
    report['chainSettingsShared'] = {k: v[0].id for k, v in KSET.items()}
    for gi_, bones in enumerate(SKIRT):
        kind = SKIRT_KIND.get(gi_)
        g = copy.deepcopy(vg); g.settingID = KSET[kind][0].id if kind else s_sk.id; g.terminateNodeNameHash = hash_wide(bones[-1])
        # noClsp kinds (Scarlet's hair, user 10-25: front locks stood out forward, back hair off the back with any limits or
        # capsules): clspFlags -1 also collides with the game's own body collision presets, sized for the hunter in bulky
        # armour, which pushed the strands outward round the neck; off -> only this file's capsules (fitCollisions) count
        if kind in OC.get('noClsp', []): g.clspFlags0 = g.clspFlags1 = 0
        nodes = []
        for j, nm in enumerate(bones):
            n_ = copy.deepcopy(vg.nodeList[min(j, len(vg.nodeList) - 2)] if j < len(bones) - 1 else vg.nodeList[-1])
            n_.windCoef = float(OC.get('kindWind', {}).get(kind, 0.4)); n_.angleLimitRad = math.radians(KSET[kind][1] if kind else float(os.environ.get('EVE_SKIRT_LIMIT', '25')))
            if kind == 'drape' and j > 0 and OC.get('drapeNodeLimit'): n_.angleLimitRad = math.radians(float(OC['drapeNodeLimit']))
            if kind == 'drape': n_.gravityCoef = float(OC.get('drapeGravity', 1.0))
            if kind in OC.get('kindGravity', {}): n_.gravityCoef = float(OC['kindGravity'][kind])   # low: holds its rest shape   # Blue Samurai sleeves stood out like paper (user 10-20)
            n_.collisionRadius = 0.01
            if OC.get('fitCollisions') == 2 and kind in OC.get('noClsp', []): n_.collisionRadius = float(OC.get('hairColRadius', 0.02))
            if j < len(bones) - 1:
                dg = (R90i.to_3x3() @ (pt_pos[bones[j + 1]] - pt_pos[nm])).normalized(); q = Vector((1.0, 0.0, 0.0)).rotation_difference(dg)
            else:
                q = Quaternion()
            n_.angleLimitDirectionX, n_.angleLimitDirectionY, n_.angleLimitDirectionZ, n_.angleLimitDirectionW = q.x, q.y, q.z, q.w
            nodes.append(n_)
        g.nodeList = nodes; g.nodeCount = len(nodes)
        for sg in g.subGroupList: sg.nodeList = copy.deepcopy(nodes)
        groups.append(g)
    cap = next((c_ for c_ in c2.ChainCollisionList if c_.chainCollisionShape == 2), None)
    if cap is not None and (OC.get('skirtChains') or OC.get('legCaps')):
        # legCaps (Scarlet's leg drape, 10-25): the shin too, so the drape lies on the leg instead of sinking into it
        _lc = (('{}_Thigh', '{}_Knee', 0.06, 0.05),) + ((('{}_Knee', '{}_Foot', 0.05, 0.04),) if OC.get('legCaps') else ())
        # drapeCap (Scarlet's leg drape, user 10-25: "too far to the middle, in SB it hangs more to the side"): on that side the
        # leg capsules stand out sideways by 'out' and are fatter -- they play the sword her cloth hung over in SB
        _dc = OC.get('drapeCap')
        if _dc:
            _sd = _dc['side']; _ox = 1.0 if (R90 @ NG[f'{_sd}_Thigh']).translation.x >= 0 else -1.0
            for ja, jb, rr, k_ in ((f'{_sd}_Thigh', f'{_sd}_Knee', _dc['thigh'], 1.0), (f'{_sd}_Knee', f'{_sd}_Foot', _dc['shin'], 0.8)):
                o_ = Vector((_ox * _dc['out'] * k_, 0.0, 0.0))
                la = (R90 @ NG[ja]).inverted() @ ((R90 @ NG[ja]).translation + o_); lb = (R90 @ NG[jb]).inverted() @ ((R90 @ NG[jb]).translation + o_)
                c_ = copy.deepcopy(cap); c_.jointNameHash = hash_wide(ja); c_.pairJointNameHash = hash_wide(jb)
                c_.posX, c_.posY, c_.posZ, c_.pairPosX, c_.pairPosY, c_.pairPosZ = la.x, la.y, la.z, lb.x, lb.y, lb.z; c_.radius = c_.endRadius = rr
                c2.ChainCollisionList.append(c_)
        for sd in 'LR':
            if _dc and sd == _dc['side']: continue
            for a_, b_, r0, r1 in ((a.format(sd), b.format(sd), r0_, r1_) for a, b, r0_, r1_ in _lc):   # inside the thigh surface: pushes only when a leg swings into a panel
                c_ = copy.deepcopy(cap); c_.jointNameHash = hash_wide(a_); c_.pairJointNameHash = hash_wide(b_)
                c_.posX = c_.posY = c_.posZ = c_.pairPosX = c_.pairPosY = c_.pairPosZ = 0.0; c_.radius = r0; c_.endRadius = r1
                c2.ChainCollisionList.append(c_)
        c2.Header.chainModelCollisionCount = len(c2.ChainCollisionList)
    report['skirtGroups'] = [len(b) for b in SKIRT]

if OC.get('drapePart'):
    _dh = {hash_wide(b_[-1]) for i_, b_ in enumerate(SKIRT) if SKIRT_KIND.get(i_) == 'drape'}
    _dg = [g for g in groups if g.terminateNodeNameHash in _dh]
    groups = [g for g in groups if g.terminateNodeNameHash not in _dh]
    if _dg:
        _c2d = copy.deepcopy(c2); _c2d.ChainGroupList = _dg; _c2d.Header.chainGroupCount = len(_dg)
        _dn = int(OC['drapePart']); _do = PART_DIR + f'{_dn}/{OPRE}{_dn}.chain2.14'
        os.makedirs(os.path.dirname(_do), exist_ok=True); fc2.writeREChain2(_c2d, _do)
        _nb = bytearray(open(_do, 'rb').read()); _nb[112:128] = open(VC, 'rb').read()[112:128]; open(_do, 'wb').write(_nb)
        report['drapeChain'] = [_do, len(_dg)]
c2.ChainGroupList = groups; c2.Header.chainGroupCount = len(groups)
chain_out = PART_DIR + f'2/{OPRE}2.chain2.14'
fc2.writeREChain2(c2, chain_out)
nb = bytearray(open(chain_out, 'rb').read()); nb[112:128] = open(VC, 'rb').read()[112:128]; open(chain_out, 'wb').write(nb)
chk = fc2.Chain2File(); f_ = open(chain_out, 'rb'); chk.read(f_); f_.close()
report['chain2'] = [[g.terminateNodeNameHash, g.settingID, [(round(n_.jiggleData.rangeX, 3), round(n_.jiggleData.rangeOffsetY, 3), n_.jiggleData.springForce, n_.jiggleData.damping) for n_ in g.nodeList if n_.jiggleData]] for g in chk.ChainGroupList]

# hidden parts: one degenerate triangle on the hip, using a material the original part's mdf2 already has
hip_w = R90 @ NG['Hip']
# every material of the original part's mdf2 gets one tiny triangle (mesh and mdf2 material lists must match)
HIDE = dict(OC['hide']); HIDE.update(OC.get('hideExtra', {}))
for n, mats in HIDE.items():
    col = bpy.data.collections.new((f'{OPRE}{n}' if isinstance(n, int) else n.split('/')[-1]) + '.mesh'); bpy.context.scene.collection.children.link(col)
    for si, mat in enumerate(mats):
        me = bpy.data.meshes.new(f'hide{n}_{si}'); c0 = hip_w.translation
        me.from_pydata([c0, c0 + Vector((0.0005, 0, 0)), c0 + Vector((0, 0.0005, 0))], [], [(0, 1, 2)])
        me.uv_layers.new(name='UV0')
        me.materials.append(bpy.data.materials.get(mat) or bpy.data.materials.new(mat))
        ob = bpy.data.objects.new(f'Group_0_Sub_{si}__{mat}', me); col.objects.link(ob)
        g = ob.vertex_groups.new(name='Hip'); g.add([0, 1, 2], 1.0, 'REPLACE')
        ob.parent = bind; md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = bind
    col.objects.link(bind)
    out = PART_DIR + (f'{n}/{OPRE}{n}' if isinstance(n, int) else n) + '.mesh.241111606'; os.makedirs(os.path.dirname(out), exist_ok=True)
    report[f'exportHidden{n}'] = list(bpy.ops.re_mesh.exportfile(filepath=out, targetCollection=col.name, exportAllLODs=False, exportBoundingBoxes=True))
    col.objects.unlink(bind)

# parts whose original has GPU cloth (gpuc): an empty gpuc (signature only, as the game ships for parts without cloth),
# else the cloth simulated on the replaced / hidden mesh drew streaks and noise round Eve
for n in OC.get('emptyGpuc', []):
    for ver in ('241111734', '241111744', '241111747', '241111760'):   # the game list has all four; the field used a newer one
        gp = PART_DIR + f'{n}/{OPRE}{n}.gpuc.{ver}'; os.makedirs(os.path.dirname(gp), exist_ok=True)
        open(gp, 'wb').write(b'GCLO')
    report.setdefault('emptyGpuc', []).append(n)

# ---------------- 7. preview ----------------
if not (EP.PREVIEWS or os.environ.get('EVE_PREVIEW') == '1'):   # installer: no preview renders (motion poses are not extracted)
    json.dump(report, open(REPORT, 'w'), indent=1, default=str)
    print('done'); raise SystemExit(0)
def import_re(path):
    return new_objects(lambda: bpy.ops.re_mesh.importfile(filepath=path, files=[{'name': os.path.basename(path)}], directory=os.path.dirname(path)))
hunter = []
for n in (1, 2, 4, 5):
    hunter += import_re(INNER + f'{n}/ch03_002_{SUB}{n}.mesh.241111606')
face_h = import_re(FACE); face_e = import_re(FACE)
LH = {n: (HG[HPAR[n]].inverted() @ HG[n]) if HPAR[n] else HG[n] for n in HORDER}
LE = {n: (NG[HPAR[n]].inverted() @ NG[n]) if HPAR[n] else NG[n] for n in HORDER}
for n, (par, pos) in EXTRA.items(): LE[n] = NG[par].inverted() @ NG[n]; HPAR[n] = par


def fk(local, pose, fi):
    out = {}
    for n in local:
        L = local[n]
        tr = pose.get(n) if pose else None
        t = L.translation.copy(); r = L.to_quaternion()
        if tr and tr.get('r') and n != 'root': w, x, y, z = tr['r'][fi]; r = Quaternion((w, x, y, z))
        if tr and tr.get('t') and n == 'COG': t = Vector(tr['t'][fi])
        m = Matrix.Translation(t) @ r.to_matrix().to_4x4()
        out[n] = (out[HPAR[n]] @ m) if HPAR[n] else Matrix.Identity(4)
    return out


def apply_pose(armobj, G, offset):
    armobj.location = offset
    bpy.context.view_layer.update()
    names = sorted([b.name for b in armobj.data.bones if b.name in G], key=lambda n: depth(n) if n in HPAR else 0)
    for n in names:
        armobj.pose.bones[n].matrix = R90 @ G[n]
        bpy.context.view_layer.update()


EVE_X, HUN_X = Vector((-0.45, 0, 0)), Vector((0.45, 0, 0))
arms_h = [o for o in hunter + face_h if o.type == 'ARMATURE']
arms_e = [bind] + [o for o in face_e if o.type == 'ARMATURE']
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'TEXTURE'; scene.display.shading.show_cavity = True
for o in hunter + face_h + face_e:
    if o.type == 'MESH': o.color = (0.75, 0.62, 0.55, 1)
# preview materials: original Stellar Blade base colours (the glb carries no images)
TEXD = P + OC['texd']
BASE = {short[m]: f for m, f in OC['base'].items()}
HAIRK, SWORDK = short['MI_EVE_HR_01_Tail_TypeA'], short['CH_W_Sword_02_Blade_Body']
for o in parts + extra_parts:
    key = o.name.split('__')[-1]
    pm = bpy.data.materials.new('prev_' + key)
    pm.use_nodes = True
    if key == HAIRK:
        pm.diffuse_color = (0.10, 0.075, 0.055, 1); pm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.10, 0.075, 0.055, 1)
    elif key in BASE or key == SWORDK:
        tn = pm.node_tree.nodes.new('ShaderNodeTexImage')
        tn.image = bpy.data.images.load(TEXD + BASE[key] + '.png' if key in BASE else P + 'eve-sword01-full/SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01/Textures/CH_W_Sword_02_D.png')
        pm.node_tree.links.new(tn.outputs['Color'], pm.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
        pm.node_tree.nodes.active = tn
    else:
        pm.diffuse_color = (0.32, 1.0, 1.0, 1)
    o.data.materials[0] = pm
grey = bpy.data.materials.new('prev_hunter'); grey.diffuse_color = (0.72, 0.66, 0.62, 1)
for o in hunter + face_h + face_e:
    if o.type == 'MESH':
        for i in range(len(o.data.materials)): o.data.materials[i] = grey
plane = bpy.data.objects.new('ground', bpy.data.meshes.new('ground')); scene.collection.objects.link(plane)
plane.data.from_pydata([(-1.5, -1.5, 0), (1.5, -1.5, 0), (1.5, 1.5, 0), (-1.5, 1.5, 0)], [], [(0, 1, 2, 3)]); plane.color = (0.3, 0.3, 0.32, 1)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(cam); scene.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.3
renders = []


def shot(tag, d):
    scene.render.resolution_x, scene.render.resolution_y = 1100, 1000
    c = Vector((0, 0, 0.9)); cam.location = c + d * 5
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUTD, f"{OC['name']}_{tag}.png"); bpy.ops.render.render(write_still=True)
    renders.append(scene.render.filepath)


FWD, LEFT = Vector((0, -1, 0)), Vector((1, 0, 0))
poses = [('rest', None, 0)]
for name in ('idle', 'jog', 'sprint', 'dodge', 'attack201', 'attack211'):
    pj = json.load(open(POSES + name + '.json'))
    for fi in range(len(pj['frames'])): poses.append((f'{name}{fi}' if len(pj['frames']) > 1 else name, pj['bones'], fi))
pose_report = {}
for tag, pb, fi in poses:
    Gh = fk(LH, pb, fi); Ge = fk(LE, pb, fi)
    for a in arms_h: apply_pose(a, Gh, HUN_X)
    for a in arms_e: apply_pose(a, Ge, EVE_X)
    pose_report[tag] = {'eveFootZ': [round((R90 @ Ge[f'{s}_Foot']).translation.z, 3) for s in 'LR'],
                        'hunterFootZ': [round((R90 @ Gh[f'{s}_Foot']).translation.z, 3) for s in 'LR']}
    if tag in ('rest',):
        shot('rest_front', FWD); shot('rest_back', -FWD)
        cam.data.ortho_scale = 0.55; c = R90 @ NG['Spine_2'].translation + EVE_X + Vector((0, 0, -0.02)); cam.location = c + FWD * 5
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(OUTD, OC['name'] + '_rest_chest.png'); bpy.ops.render.render(write_still=True); renders.append(scene.render.filepath)
        cam.data.ortho_scale = 2.3
        for a_ in arms_h: apply_pose(a_, Gh, Vector((0, 0.6, 0)))
        for a_ in arms_e: apply_pose(a_, Ge, Vector((0, -0.6, 0)))
        shot('rest_side', LEFT)
        cam.data.ortho_scale = 1.7; c = Vector((0, 0, 0.3)); cam.location = c + LEFT * 5
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(OUTD, OC['name'] + '_rest_feet.png'); bpy.ops.render.render(write_still=True); renders.append(scene.render.filepath)
        cam.data.ortho_scale = 2.3
    else:
        shot(f'{tag}_front', (FWD + LEFT * 0.35).normalized())
        if tag.startswith(('jog', 'sprint', 'dodge', 'attack')):
            for a_ in arms_h: apply_pose(a_, Gh, Vector((0, 0.6, 0)))      # side view: hunter behind Eve along the view line
            for a_ in arms_e: apply_pose(a_, Ge, Vector((0, -0.6, 0)))
            shot(f'{tag}_side', LEFT)
            if tag.startswith('jog'):
                cam.data.ortho_scale = 1.3
                c = Vector((0, 0, 0.5)); cam.location = c + LEFT * 5
                cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
                scene.render.filepath = os.path.join(OUTD, f"{OC['name']}_{tag}_legs.png"); bpy.ops.render.render(write_still=True); renders.append(scene.render.filepath)
                cam.data.ortho_scale = 2.3
report['poses'] = pose_report
report['renders'] = renders
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTD, OC['name'] + '.blend'))
json.dump(report, open(REPORT, 'w'), indent=1, default=str)
print('done')
