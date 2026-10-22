"""Step 1 of the installer: build the local work folder from the user's OWN game installs.

Everything written here comes from the user's Stellar Blade and Monster Hunter Wilds files and stays in WORK
(config.json work_dir). Nothing in this folder is ever part of the builder download.
Each step is skipped when its output already exists, so the script can be re-run after a failure.

usage: python prepare.py
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eve_paths as EP

W = EP.WORK
ENV = dict(os.environ, BLENDER_USER_SCRIPTS=EP.USER_SCRIPTS, PYTHONIOENCODING='utf-8',
           MHW_DIR=EP.GAME, SB_PAKS=EP.SB_PAKS, WORK_DIR=W)
SBX = [EP.DOTNET, EP.ROOT + 'tools/sb-extract/bin/sb-extract.dll']
MC = [EP.DOTNET, EP.ROOT + 'tools/motion-convert/bin/motion-convert.dll']


def log(*a):
    print('[prepare]', *a, flush=True)


def run(cmd, out=None, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=ENV)
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w', encoding='utf-8').write(r.stdout + '\n' + r.stderr)
    if r.returncode != 0:
        raise SystemExit(f'failed ({r.returncode}): {" ".join(map(str, cmd))}\n{r.stderr[-2000:]}')
    return r


# ---------- Stellar Blade (sb-extract: glb meshes, png textures, material json) ----------
SB_EXPORTS = {
    'sb-refbody':       ['SB/Content/Art/Character/PC/CH_P_EVE_ReferenceBody'],
    'eve-hair':         ['SB/Content/Art/Character/PC/CH_P_EVE_Hair'],
    'eve-head':         ['SB/Content/Art/Character/PC/CH_P_EVE_Head'],
    'eve-sword01-full': ['SB/Content/Art/Character/Weapon/Sword/CH_W_Sword_01'],
    'eve27-suit':       ['SB/Content/Art/Character/PC/CH_P_EVE_27'],
    'eve63-suit':       ['SB/Content/Art/Character/PC/CH_P_EVE_63', 'SB/Content/Art/Character/PC/CH_P_EVE_43',
                         'SB/Content/Art/Character/PC/CH_P_EVE_ReferenceBody'],
}


def sb_step():
    if not os.path.exists(W + 'sb_pc_list.txt'):
        log('listing Stellar Blade files')
        r = run(SBX + ['--list', 'SB/Content/'])
        open(W + 'sb_pc_list.txt', 'w', encoding='utf-8').write(r.stdout)
    for out, dirs in SB_EXPORTS.items():
        if os.path.exists(W + out + '/export-report.json'):
            continue
        for d in dirs:
            log('exporting', d, '->', out)
            run(SBX + ['--export', d, W + out], W + f'logs/{out}.log')


# ---------- Monster Hunter Wilds (motion-convert --extract-file: native files from the paks) ----------
MHW_FILES = []
for sub in ('100', '101'):
    for n in (1, 2, 4, 5, 6):
        MHW_FILES += [(f'wilds-inner{sub}', f'art/model/character/ch03/002/{sub}/{n}/ch03_002_{sub}{n}.mesh.241111606'),
                      (f'wilds-inner{sub}', f'art/model/character/ch03/002/{sub}/{n}/ch03_002_{sub}{n}.mdf2.45')]
    MHW_FILES += [(f'wilds-inner{sub}', f'art/model/character/ch03/002/{sub}/2/ch03_002_{sub}2.chain2.14')]
MHW_FILES += [(f'wilds-inner101', 'art/model/character/ch03/002/101/5/ch03_002_1015.chain2.14')]
MHW_FILES += [('wilds-hair', 'art/model/character/ch00/001/0000/ch00_001_0000.mesh.241111606'),
              ('wilds-hair', 'art/model/character/ch01/001/0/518/ch01_001_0518.chain2.14'),
              ('wilds-hair', 'art/model/character/ch01/001/0/518/ch01_001_0518.mesh.241111606'),
              ('wilds-hair', 'art/model/character/ch01/001/0/518/ch01_001_0518.mdf2.45')]
for n in (1, 2, 3, 4, 5):
    MHW_FILES += [('wilds-armor', f'art/model/character/ch03/091/000/{n}/ch03_091_000{n}.mesh.241111606'),
                  ('wilds-armor', f'art/model/character/ch03/091/000/{n}/ch03_091_000{n}.mdf2.45')]
MHW_FILES += [('wilds-reference', 'art/model/character/ch03/000/900/ch03_000_9000.fbxskel.7')]


def mhw_step():
    for out, rel in MHW_FILES:
        dst = W + f'{out}/natives/stm/' + os.path.dirname(rel)
        if os.path.exists(os.path.join(dst, os.path.basename(rel))):
            continue
        log('extracting', rel)
        run(MC + ['--extract-file', rel, dst])
        if rel.endswith('.mesh.241111606'):      # meshes keep their high LODs in the streaming folder
            sdst = W + f'{out}/natives/stm/streaming/' + os.path.dirname(rel)
            run(MC + ['--extract-file', 'streaming/' + rel, sdst])
    # the builder reads the innerwear chain2 files from <inner>/extra
    for sub in ('100', '101'):
        ex = W + f'wilds-inner{sub}/extra/'
        os.makedirs(ex, exist_ok=True)
        for root, _, fs in os.walk(W + f'wilds-inner{sub}/natives'):
            for f in fs:
                if f.endswith('.chain2.14') and not os.path.exists(ex + f):
                    shutil.copy2(os.path.join(root, f), ex + f)


# ---------- Blender: armor template blend and the hunter reference rig ----------
def blender_step():
    tpl = W + 'wilds-armor/ch03_091_0002.blend'
    if not os.path.exists(tpl):
        log('making the armor template blend')
        run([EP.BLENDER, '-b', '--factory-startup', '-P', EP.SCRIPTS + 'make_template_blend.py', '--',
             W + 'wilds-armor/natives/stm/art/model/character/ch03/091/000/2/', tpl], W + 'logs/template.log')
    rig = W + 'wilds-reference/eve-and-wilds-rigs.blend'
    if not os.path.exists(rig):
        log('making the hunter reference rig')
        run([EP.BLENDER, '-b', '--factory-startup', '-P', EP.SCRIPTS + 'make_reference_rig.py', '--',
             W + 'wilds-reference/natives/stm/art/model/character/ch03/000/900/ch03_000_9000.fbxskel.7', rig],
            W + 'logs/reference_rig.log')


def main():
    os.makedirs(W, exist_ok=True)
    for f in (EP.BLENDER, EP.SB_PAKS, EP.GAME):
        if not os.path.exists(f):
            raise SystemExit(f'not found: {f} (check config.json)')
    sb_step()
    mhw_step()
    blender_step()
    log('done; work folder:', W)


if __name__ == '__main__':
    main()
