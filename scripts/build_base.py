"""Step 2 of the installer: Eve's base pieces, built from the work folder (prepare.py).

  27  Ocean Maid (CH_P_EVE_27) on outfit beta type 2 (ch03/002/101) + Eve face
  63  Wave Diver Bikini (CH_P_EVE_63) on outfit beta type 1 (ch03/002/100)

The face mesh (stellar/eve27/face) is shared by every Eve outfit. Outputs: WORK/base<id>-build/stage/...

usage: python build_base.py [27] [63]
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eve_paths as EP
import eve_repro

W = EP.WORK
TPL = W + 'wilds-armor/ch03_091_0002.blend'
BASE_ENV = dict(os.environ, BLENDER_USER_SCRIPTS=EP.USER_SCRIPTS, PYTHONIOENCODING='utf-8', WORK_DIR=W)

BASES = {
    '27': dict(sub='101', glb='eve27-suit/SB/Content/Art/Character/PC/CH_P_EVE_27/CH_P_EVE_27.glb', pfx='evo', tex='stellar/eve27/tex',
               roots=['eve27-suit', 'sb-refbody', 'eve-hair', 'eve-sword01-full'], joints='ocean_maid_joints.json', face=True),
    '63': dict(sub='100', glb='eve63-suit/SB/Content/Art/Character/PC/CH_P_EVE_63/CH_P_EVE_63.glb', pfx='evb', tex='stellar/eve63/tex',
               roots=['eve63-suit', 'sb-refbody', 'eve-hair', 'eve-sword01-full'], joints='wave_bikini_joints.json', face=False),
}


def log(*a):
    print('[build_base]', *a, flush=True)


def blender(script, args, out, env):
    cmd = [EP.BLENDER, '--background', TPL, '--python', EP.SCRIPTS + script, '--'] + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=3600)
    open(out, 'w', encoding='utf-8').write(r.stdout + '\n' + r.stderr)
    if r.returncode != 0 or 'Traceback' in r.stdout + r.stderr:
        raise SystemExit(f'{script} failed, see {out}')


def tex(B, ST, cfg, outfit, prefix, name, mdf_dir, roots, tag):
    env = dict(BASE_ENV, EVE_OUTFIT=outfit, EVE_MAT_PREFIX=prefix, EVE_TEX_REL=cfg['tex'], EVE_MDF_NAME=name,
               EVE_MDF_DIR=mdf_dir, EVE_HAIR_STRANDS='1')
    env.update(eve_repro.tex_env('face' if outfit == 'face' else f'base{outfit}'))
    blender('build_eve_default_tex.py', [';'.join(W + r for r in roots), ST + 'natives/stm', B + f'{tag}_report.json'], B + f'{tag}.log', env)


def build(oid):
    cfg = BASES[oid]; sub = cfg['sub']
    B = W + f'base{oid}-build/'; ST = B + 'stage/'
    if os.path.exists(B): shutil.rmtree(B)
    os.makedirs(ST)
    part = f'art/model/character/ch03/002/{sub}'
    log(oid, 'outfit mesh')
    blender('build_eve_outfit.py', [W + cfg['glb'], ST, B + 'report.json'], B + 'build.log', dict(BASE_ENV, EVE_OUTFIT_ID=oid))
    body_mesh = ST + f'natives/stm/{part}/2/ch03_002_{sub}2.mesh.241111606'
    eve_repro.mesh(f'base{oid}', body_mesh, B, log)
    log(oid, 'outfit textures + mdf')
    tex(B, ST, cfg, oid, cfg['pfx'], f'ch03_002_{sub}2', f'{part}/2', cfg['roots'], 'tex')
    eve_repro.textures(f'base{oid}', body_mesh, ST + 'natives/stm/' + cfg['tex'], B, log, keep=['evo05', 'evo06'] if oid == '27' else [])   # hair, sword
    if cfg['face']:
        log(oid, 'face mesh')
        blender('build_eve_face.py', [B, ST], B + 'face.log', BASE_ENV)
        face_mesh = ST + 'natives/stm/stellar/eve27/face/eve27_face.mesh.241111606'
        eve_repro.mesh('face', face_mesh, B, log)
        log(oid, 'face textures + mdf')
        tex(B, ST, cfg, 'face', 'evf', 'eve27_face', 'stellar/eve27/face', ['eve-head', 'eve27-suit', 'eve-hair', 'eve-sword01-full'], 'face_tex')
        eve_repro.textures('face', face_mesh, ST + 'natives/stm/' + cfg['tex'], B, log)
    # runtime joint positions for the Lua
    dj = ST + 'reframework/data/stellar-eve/'
    os.makedirs(dj, exist_ok=True)
    shutil.copy2(B + 'eve_outfit_joints.json', dj + cfg['joints'])
    log(oid, 'done ->', ST)


if __name__ == '__main__':
    for oid in (sys.argv[1:] or ['27', '63']):
        build(oid)
