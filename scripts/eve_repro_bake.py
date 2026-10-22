"""Bake an eve-material-recipe-v1 (data/repro/<key>.recipe.json) onto a built mesh and write its ALBD / NRRO .tex
(Blender + Cycles; called by eve_repro.textures).
usage: blender -b -P eve_repro_bake.py -- <built mesh> <recipe json> <work dir> <stage tex dir> <builder TGA dir> <report json> [keep keys]
The recipe's node graphs are rebuilt with their images from the work folder (the user's own Stellar Blade extraction) and
the per-vertex values they read; per material an EMIT bake of what feeds the Principled BSDF gives
  Base Color -> ALBD RGB (sRGB), Metallic -> ALBD A (= 1 - metal), Roughness -> NRRO R
NRRO G/B/A (normal, AO) and the texture size come from the builder's own TGA; texels outside the UV islands are filled
from inside (push-pull). Placeholder materials (no image, only a flat preview colour, e.g. hair) keep the builder texture."""
import bpy, sys, os, json, addon_utils
import numpy as np
a = sys.argv[sys.argv.index('--') + 1:]; MESH, RECIPE, WORK, TEXDIR, TGA, REP = a[:6]
KEEP = set(a[6].split(',')) if len(a) > 6 and a[6] else set()   # keys whose builder texture is the approved one
addon_utils.enable('RE_Mesh_Editor', default_set=True)
import ctypes; ctypes.windll.ole32.CoInitializeEx(None, 0)
from RE_Mesh_Editor.modules.ddsconv.directx.texconv import Texconv, unload_texconv
from RE_Mesh_Editor.modules.tex.re_tex_utils import DDSToTex
from RE_Mesh_Editor.modules.tex.file_re_tex import getTexVersionFromGameName
R = json.load(open(RECIPE)); REPORT = {'textures': {}}


def l2s(x): x = np.clip(x, 0, 1); return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
def key_of(name): return name.split('__')[-1].split('.')[0]


for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.re_mesh.importfile(files=[{'name': os.path.basename(MESH)}], directory=os.path.dirname(MESH), loadMaterials=False)
objs = {key_of(o.name): o for o in bpy.data.objects if o.type == 'MESH' and ('LOD' not in o.users_collection[0].name or 'LOD_0' in o.users_collection[0].name)}
IMG = {}


def image(ref):
    if not ref.get('work_rel'): return None
    p = os.path.join(WORK, ref['work_rel'])
    k = (p, ref['colorspace'], ref.get('alpha_mode', 'STRAIGHT'))   # one file can be read as colour and as data
    if k not in IMG:
        if not os.path.exists(p): raise FileNotFoundError(ref['work_rel'])
        im = bpy.data.images.load(p, check_existing=False); im.colorspace_settings.name = k[1]; im.alpha_mode = k[2]; IMG[k] = im
    return IMG[k]


def build(mname, rec):
    m = bpy.data.materials.new(mname + '_recipe'); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    made = {}
    for d in rec['nodes']:
        n = nt.nodes.new(d['type']); n.name = d['name']; made[d['name']] = n
        for p, v in d['props'].items():
            try: setattr(n, p, v)
            except Exception: pass
        if d.get('image'): n.image = image(d['image'])
        if d.get('ramp'):
            cr = n.color_ramp; cr.interpolation = d['ramp']['interpolation']
            while len(cr.elements) < len(d['ramp']['elements']): cr.elements.new(0.5)
            for e, (pos, col) in zip(cr.elements, d['ramp']['elements']): e.position = pos; e.color = col
        for ident, v in d['inputs'].items():
            s = next((x for x in n.inputs if x.identifier == ident), None)
            if s is not None and hasattr(s, 'default_value'):
                try: s.default_value = v
                except Exception: pass
        if 'Value' in d.get('outputs', {}): n.outputs[0].default_value = d['outputs']['Value']
        if 'Color' in d.get('outputs', {}): n.outputs[0].default_value = d['outputs']['Color']
    for fn, fs, tn, ts in rec['links']:
        nt.links.new(next(x for x in made[fn].outputs if x.identifier == fs), next(x for x in made[tn].inputs if x.identifier == ts))
    return m


# materials and the vertex values they read, per submesh (matched by material key: submesh order can differ)
users = {}
MISSING = {}
for oname, mrec in R['meshes'].items():
    o = objs.get(key_of(oname))
    if o is None: raise SystemExit('recipe submesh not in the built mesh: ' + oname)
    if len(o.data.vertices) != mrec['verts']: raise SystemExit('vertex count differs: ' + oname)
    for an, at in mrec['attributes'].items():
        if not at: continue
        ca = o.data.attributes.new(an, at['data_type'], 'POINT' if at['domain'] == 'VERTEX' else at['domain'])
        vals = np.array(at['values'] if at['values'] is not None else [at['constant']] * len(ca.data), np.float32)
        if at['data_type'] in ('FLOAT_COLOR', 'BYTE_COLOR'):
            ca.data.foreach_set('color', np.pad(vals, ((0, 0), (0, 4 - vals.shape[1])), constant_values=1).reshape(-1))
        else: ca.data.foreach_set('value', vals[:, 0])
    o.data.materials.clear()
    for mn in mrec['materials']:
        rec = R['materials'][mn]
        if rec['placeholder_material']: o.data.materials.append(bpy.data.materials.new(mn + '_kept')); continue
        try: m = None if mn in MISSING else (bpy.data.materials.get(mn + '_recipe') or build(mn, rec))
        except FileNotFoundError as e:   # a source image this PC's extraction does not have: keep the builder texture
            MISSING[mn] = str(e); print('MISSING', e, flush=True)
            half = bpy.data.materials.get(mn + '_recipe')
            if half: bpy.data.materials.remove(half)
            m = None
        if m is None:
            REPORT['textures'][key_of(oname)] = f'missing source image {MISSING[mn]}: builder texture kept'
            o.data.materials.append(bpy.data.materials.new(mn + '_kept')); continue
        o.data.materials.append(m)
        users.setdefault(mn, []).append(o)

sc = bpy.context.scene; sc.render.engine = 'CYCLES'
try:
    cp = bpy.context.preferences.addons['cycles'].preferences
    for dt in ('OPTIX', 'CUDA'):
        try:
            cp.compute_device_type = dt; cp.get_devices()
            if any(d.type == dt for d in cp.devices):
                for d in cp.devices: d.use = (d.type == dt)
                sc.cycles.device = 'GPU'; break
        except Exception: pass
except Exception: pass
sc.cycles.samples = 1; sc.cycles.use_denoising = False
sc.render.bake.margin = 16; sc.render.bake.margin_type = 'EXTEND'; sc.render.bake.use_clear = True


def bake(mat, objs_, socket, w, h, const=None):
    nt = mat.node_tree; bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output), None) or \
          next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 1.0; inp = bsdf.inputs[socket]
    if const is not None: em.inputs['Color'].default_value = (const, const, const, 1)
    elif inp.is_linked: nt.links.new(inp.links[0].from_socket, em.inputs['Color'])
    else:
        v = inp.default_value; em.inputs['Color'].default_value = (v[0], v[1], v[2], 1) if hasattr(v, '__len__') else (v, v, v, 1)
    old = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].is_linked else None
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    img = bpy.data.images.new('bake', w, h, alpha=True, float_buffer=True); img.colorspace_settings.name = 'Non-Color'
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img
    for n in nt.nodes: n.select = False
    tn.select = True; nt.nodes.active = tn
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs_: o.hide_render = False; o.select_set(True)
    bpy.context.view_layer.objects.active = objs_[0]; bpy.ops.object.bake(type='EMIT')
    arr = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(arr)
    nt.nodes.remove(tn); nt.nodes.remove(em); bpy.data.images.remove(img)
    if old: nt.links.new(old, out.inputs['Surface'])
    return arr.reshape(h, w, 4)


def pushpull(arr, mask):
    """fill every texel outside mask with a smooth extension of the texels inside (mip-safe padding, no black border)"""
    if mask.all(): return arr
    levels = [(arr * mask[..., None], mask.astype(np.float32))]
    while min(levels[-1][1].shape) > 1:
        a_, m_ = levels[-1]; h_, w_ = m_.shape
        levels.append((a_[:h_ // 2 * 2, :w_ // 2 * 2].reshape(h_ // 2, 2, w_ // 2, 2, -1).sum((1, 3)),
                       m_[:h_ // 2 * 2, :w_ // 2 * 2].reshape(h_ // 2, 2, w_ // 2, 2).sum((1, 3))))
    fill = levels[-1][0] / np.maximum(levels[-1][1][..., None], 1e-6)
    for a_, m_ in reversed(levels[:-1]):
        h_, w_ = m_.shape
        up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
        up = np.pad(up, ((0, h_ - up.shape[0]), (0, w_ - up.shape[1]), (0, 0)), mode='edge')[:h_, :w_]
        fill = np.where(m_[..., None] > 0, a_ / np.maximum(m_[..., None], 1e-6), up)
    out = arr.copy(); out[~mask] = fill[~mask]
    return out


def load_tga(p):
    im = bpy.data.images.load(p); im.colorspace_settings.name = 'Non-Color'; im.alpha_mode = 'CHANNEL_PACKED'
    w, h = im.size; b = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(b); bpy.data.images.remove(im)
    return b.reshape(h, w, 4)


tex_ver = getTexVersionFromGameName('MHWILDS'); tc = Texconv()
tmp = os.path.join(os.path.dirname(REP), 'tmp'); os.makedirs(tmp, exist_ok=True)
for mn, os_ in sorted(users.items()):
    key = key_of(os_[0].name)               # texture key = the submesh's material key (face: evf00 ...)
    if key in KEEP: REPORT['textures'][key] = 'builder texture kept'; continue
    nrro_src = os.path.join(TGA, f'{key}_NRRO.tga')
    if not os.path.exists(nrro_src): REPORT['textures'][key] = 'no builder TGA: kept'; continue
    nr = load_tga(nrro_src); h, w = nr.shape[:2]
    mat = bpy.data.materials[mn + '_recipe']
    base = bake(mat, os_, 'Base Color', w, h); rough = bake(mat, os_, 'Roughness', w, h); metal = bake(mat, os_, 'Metallic', w, h)
    cov = bake(mat, os_, 'Base Color', w, h, const=1.0)[..., 0] > 0.5      # texels the bake wrote (incl. its 16 px margin)
    base = pushpull(base, cov); rough = pushpull(rough, cov); metal = pushpull(metal, cov)
    albd = np.dstack([l2s(base[..., :3]), 1.0 - np.clip(metal[..., 0], 0, 1)]).astype(np.float32)
    nrro = nr.copy(); nrro[..., 0] = np.clip(rough[..., 0], 0, 1)
    for suffix, arr, fmt in (('ALBD', albd, 'BC7_UNORM_SRGB'), ('NRRO', nrro, 'BC7_UNORM')):
        tga = os.path.join(tmp, f'{key}_{suffix}.tga')
        im = bpy.data.images.new(os.path.basename(tga), w, h, alpha=True); im.colorspace_settings.name = 'Non-Color'
        im.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).reshape(-1)); im.filepath_raw = tga; im.file_format = 'TARGA_RAW'; im.save(); bpy.data.images.remove(im)
        tc.convert_to_dds(file=tga, dds_fmt=fmt, out=tmp, no_mip=False, verbose=False)
        DDSToTex([os.path.join(tmp, f'{key}_{suffix}.dds')], tex_ver, os.path.join(TEXDIR, f'{key.lower()}_{suffix.lower()}.tex.{tex_ver}'))
    REPORT['textures'][key] = {'size': [w, h], 'coverage': round(float(cov.mean()), 3), 'rough_median': round(float(np.median(rough[..., 0][cov])), 3)}
    print('TEX', key, REPORT['textures'][key], flush=True)
unload_texconv()
REPORT['summary'] = {'baked': sorted(k for k, v in REPORT['textures'].items() if isinstance(v, dict)),
                     'kept': sorted(k for k, v in REPORT['textures'].items() if not isinstance(v, dict)),
                     'placeholders_kept': sorted(k for k, v in R['materials'].items() if v['placeholder_material'])}
json.dump(REPORT, open(REP, 'w'), indent=1)
print('DONE', REPORT['summary'])
