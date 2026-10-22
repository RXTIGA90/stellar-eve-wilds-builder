"""Common-skin look (2026-10-21: common skin colour, neck seam and outfit fixes, approved in game) rebuilt from the user's own files.

data/repro/<key>.<name>.json (key = queue row, base27 or face) holds numbers only, no game or Stellar Blade data:
  delta.json        eve-mesh-delta-v1: per changed vertex the position offset / normal / full weight set, per moved bone its
                    rest matrix (from this builder's own output to the approved model; submeshes matched by material key)
  recipe.json       eve-material-recipe-v1: the approved material node graphs (images by path inside the work folder, no pixels)
                    and the per-vertex values they read; baked here into ALBD (colour, metal) and NRRO R (roughness)
  chain2_patch.json eve-bytes-patch-v1: changed bytes of the body chain2 (checked against the expected base hash)
Called by make_eve_auto.py / build_base.py right after their own steps; a key without data is left as built.
"""
import hashlib
import json
import os
import subprocess

import eve_paths as EP

REPRO = EP.DATA + 'repro/'
ENV = dict(os.environ, BLENDER_USER_SCRIPTS=EP.USER_SCRIPTS, PYTHONIOENCODING='utf-8', WORK_DIR=EP.WORK)


def _blender(script, args, out):
    r = subprocess.run([EP.BLENDER, '--background', '--factory-startup', '--python', EP.SCRIPTS + script, '--'] + args,
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV, timeout=3600)
    open(out, 'w', encoding='utf-8').write(r.stdout + '\n' + r.stderr)
    if r.returncode != 0 or 'Traceback' in r.stdout + r.stderr:
        raise SystemExit(f'{script} failed, see {out}')
    return r.stdout


def _overrides(key):
    p = REPRO + f'{key}.tex_overrides.json'
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def specs(key, specs_, respec, log=print):
    """material spec changes of the approved build (tex_overrides.json): 'variant' = textures of another SB material
    instance in the same slot (respec(name) = make_eve_auto.mat_spec), 'specs' = field values / fx per material"""
    o = _overrides(key)
    for sp in specs_:
        vm = o.get('variant', {}).get(sp[0])
        if vm:
            nv = respec(vm); nv[0] = sp[0]; sp[:] = nv; log('repro variant', sp[0], '<-', vm)
    for sp in specs_:
        c = o.get('specs', {}).get(sp[0])
        if not c: continue
        for i, k in enumerate(('mat', 'kind', 'base', 'orm', 'nrm', 'stk', 'hex')):
            if k in c and k != 'mat': sp[i] = c[k]
        if 'fx' in c: sp[7] = c['fx']
        if 'fxAdd' in c: sp[7] = dict(sp[7] or {}, **c['fxAdd'])
        log('repro spec', sp[0], sp[1], sp[2])


def outfit(key, oc, log=print):
    """outfit build setting changes of the approved build (outfit.json), e.g. a material kept instead of dropped"""
    p = REPRO + f'{key}.outfit.json'
    if not os.path.exists(p): return
    ch = {k: v for k, v in json.load(open(p, encoding='utf-8')).items() if not k.startswith('_')}
    oc.update(ch); log('repro outfit', key, ch)


def tex_env(key):
    """texture build settings of the approved build: the shared skin colour profile + the outfit's own values"""
    if not os.path.exists(REPRO + f'{key}.delta.json'): return {}
    return dict({'EVE_SKIN_PROFILE': 'common_v1'}, **{k: str(v) for k, v in _overrides(key).get('env', {}).items()})


def mesh(key, path, build_dir, log=print):
    """apply the mesh delta to the built mesh (in place); log and temp file in the build folder, outside stage"""
    d = REPRO + f'{key}.delta.json'
    if not os.path.exists(d): return
    td = build_dir + f'repro_{key}/'; os.makedirs(td, exist_ok=True)
    tmp = td + os.path.basename(path)
    out = _blender('eve_repro_delta.py', [path, d, tmp], td + 'delta.log')
    os.replace(tmp, path)
    log('repro mesh', key, next((l for l in out.splitlines() if l.startswith('APPLY')), ''))


def textures(key, mesh_path, tex_dir, build_dir, log=print, keep=()):
    """bake the material recipe over the built ALBD / NRRO (normal and AO channels: the builder's own TGA in
    build_dir/eve_default_tex_tmp); keep = keys whose builder texture stays (Eve's hair / sword keys)"""
    rcp = REPRO + f'{key}.recipe.json'
    if not os.path.exists(rcp): return
    td = build_dir + f'repro_{key}/'; os.makedirs(td, exist_ok=True)
    rep = td + 'bake.json'
    keep = ','.join(list(keep) + _overrides(key).get('keepBuilderTex', []))
    _blender('eve_repro_bake.py', [mesh_path, rcp, EP.WORK, tex_dir, build_dir + 'eve_default_tex_tmp', rep, keep], td + 'bake.log')
    log('repro textures', key, json.load(open(rep)).get('summary'))


def chain(key, path, log=print):
    """patch the body chain2 bytes (only when the built file is the expected one)"""
    p = REPRO + f'{key}.chain2_patch.json'
    if not os.path.exists(p): return
    P = json.load(open(p)); b = bytearray(open(path, 'rb').read())
    h = hashlib.sha256(b).hexdigest()
    if h == P['target_sha256']: log('repro chain', key, 'already patched'); return
    if len(b) != P['size'] or h != P['base_sha256']: raise SystemExit(f'repro chain {key}: built chain2 differs from the expected base')
    for off, hx in P['runs']: v = bytes.fromhex(hx); b[off:off + len(v)] = v
    assert hashlib.sha256(b).hexdigest() == P['target_sha256']
    open(path, 'wb').write(b)
    log('repro chain', key, len(P['runs']), 'runs patched')
