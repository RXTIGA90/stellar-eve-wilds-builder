"""Install / uninstall the built Eve files into Monster Hunter Wilds.

  python install_game.py install     copy every built stage into the game (originals backed up once)
  python install_game.py uninstall   put the game back exactly as it was before the first install
  python install_game.py status      show what is installed

The first time a game file is replaced, the original is copied to WORK/game-backup/original/<path>. Files that did not
exist are listed in WORK/game-backup/added.txt. Uninstall restores the originals and deletes the added files, so the
game ends up as it was (re-running install is safe: originals are never overwritten by Eve files).
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eve_paths as EP

W, GAME = EP.WORK, EP.GAME
BK = W + 'game-backup/'
ORIG = BK + 'original/'
ADDED = BK + 'added.txt'
DATA_DIR = 'reframework/data/stellar-eve/'
RUNTIME = ('hunter_face.json', 'hunter_face_state.json', 'status.json', 'control.json')


# The other parts of an Eve outfit's armour (head 3, arms 1, legs 4, waist 5 + its _0/_9 extras) are built as one-triangle
# hidden meshes, but NOT installed (10-20, user: the same helm worn without the Eve part was invisible and left the hunter
# bald). The game keeps its own files; the Lua hides those parts only while the Eve part is worn.
BASE_HIDDEN = {'27': ['ch03_002_1011', 'ch03_002_1014', 'ch03_002_1015'],
               '63': ['ch03_002_1001', 'ch03_002_1004', 'ch03_002_1005']}


def hidden_stems(info):
    s = set(info.get('hidePhys', [])) | set(info.get('dropKeys', []))
    if info.get('twin'): s |= set(info['twin'].get('hidePhys', []))
    return s - set(info.get('unhide', []))


def stem(fn):
    return os.path.basename(fn).split('.')[0]


def added_set():
    return set(open(ADDED, encoding='utf-8').read().split('\n')) - {''} if os.path.exists(ADDED) else set()


def put(src, rel, added):
    dst = GAME + rel
    if os.path.exists(dst) and rel not in added and not os.path.exists(ORIG + rel):
        os.makedirs(os.path.dirname(ORIG + rel), exist_ok=True)
        shutil.copy2(dst, ORIG + rel)                       # vanilla copy, kept forever
    elif not os.path.exists(dst):
        added.add(rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def copy_stage(stage, added, skip=(), only=None):
    n = 0
    for root, _, fs in os.walk(stage):
        for f in fs:
            if stem(f) in skip: continue
            src = os.path.join(root, f)
            rel = os.path.relpath(src, stage).replace('\\', '/')
            if only and not only(rel): continue
            put(src, rel, added); n += 1
    return n


# Eve's face (built with the type 2 default look) is installed with every outfit; each default look (innerwear beta
# type 2 = Ocean Maid "27", type 1 = Wave Diver Bikini "63") only when chosen (build_all.py writes
# work/innerwear-<id>.selected), or when an older install already put it in.
def face_file(rel):
    return rel.startswith('natives/stm/stellar/eve27/face/') or os.path.basename(rel).startswith('evf')


def innerwear_chosen(oid, added):
    if os.path.exists(W + f'innerwear-{oid}.selected'):
        return True
    part = 'ch03_002_1012' if oid == '27' else 'ch03_002_1002'
    return any(stem(r) == part for r in added)


# The drone slinger (default-look part 6 + its "evs" textures) was dropped on 10-20: it needed UModel. An older install's
# drone files are removed so the slinger is the game's own again.
OLD_DRONE = {'ch03_002_1006', 'ch03_002_1016'}


def old_drone_texture(rel):
    return rel.startswith('natives/stm/stellar/') and os.path.basename(rel).startswith('evs')


def drop_hidden(stems, added):
    """Remove hidden-part / drone files an older install put in the game (originals come back from the backup or the paks)."""
    n = 0
    for rel in sorted(added):
        if stem(rel) in stems or old_drone_texture(rel):
            p = GAME + rel
            if os.path.exists(p): os.remove(p); n += 1
            added.discard(rel)
    if os.path.exists(ORIG):
        for root, _, fs in os.walk(ORIG):
            for f in fs:
                if stem(f) in stems:
                    src = os.path.join(root, f); rel = os.path.relpath(src, ORIG).replace('\\', '/')
                    shutil.copy2(src, GAME + rel); n += 1
    return n


def install():
    if not os.path.exists(GAME + 'MonsterHunterWilds.exe'):
        raise SystemExit('Monster Hunter Wilds not found at ' + GAME)
    if not os.path.exists(GAME + 'dinput8.dll'):
        print('WARNING: REFramework (dinput8.dll) is not installed; Eve needs it at runtime.')
    os.makedirs(BK, exist_ok=True)
    added = added_set()
    total = 0
    hidden = set(OLD_DRONE)
    for oid in ('27', '63'):                                   # Eve's face + the chosen default looks
        st = W + f'base{oid}-build/stage'
        hidden.update(BASE_HIDDEN[oid])
        if not os.path.exists(st): continue
        if innerwear_chosen(oid, added): total += copy_stage(st, added, BASE_HIDDEN[oid])
        elif oid == '27': total += copy_stage(st, added, BASE_HIDDEN[oid], only=face_file)
    put(EP.ROOT + 'game/reframework/autorun/stellar_eve_outfit_bones.lua', 'reframework/autorun/stellar_eve_outfit_bones.lua', added)
    reg = {'outfits': {}, 'chainFix': {}, 'hidePhys': [], 'keep': []}
    hp, keep = set(), set()
    queue = json.load(open(EP.DATA + 'night_queue.json', encoding='utf-8'))
    tmp = W + 'install-tmp/'; os.makedirs(tmp, exist_ok=True)
    for q in queue:
        B = W + f'auto{q["row"]}-build/'
        if not os.path.exists(B + 'info.json'):
            print('not built, skipped:', q['row']); continue
        info = json.load(open(B + 'info.json', encoding='utf-8'))
        hs = hidden_stems(info); hidden |= hs
        total += copy_stage(B + 'stage', added, hs)
        keep.update(set(info.get('unhide', [])) - {info['body']})
        jn = f'auto_{info["row"]}_joints.json'
        put(B + 'eve_outfit_joints.json', DATA_DIR + jn, added)
        for body in [info['body']] + ([info['twin']['body']] if info.get('twin') else []):
            reg['outfits'][body] = 'stellar-eve/' + jn
        if info.get('chainFix'): reg['chainFix'][info['body']] = info['chainFix']
        if info.get('face'): reg.setdefault('faces', {})[info['body']] = info['face']   # own face (Scarlet), Lua swaps to it
        if info.get('twin') and info['twin'].get('chainFix'): reg['chainFix'][info['twin']['body']] = info['twin']['chainFix']
        hp.update(info.get('hidePhys', []))
        if info.get('twin'): hp.update(info['twin']['hidePhys'])
        hp.difference_update(info.get('unhide', []))
    reg['hidePhys'] = sorted(hp)
    reg['keep'] = sorted(keep)
    dropped = drop_hidden(hidden, added)
    json.dump(reg, open(tmp + 'outfits_auto.json', 'w', encoding='utf-8'), indent=1)
    put(tmp + 'outfits_auto.json', DATA_DIR + 'outfits_auto.json', added)
    open(ADDED, 'w', encoding='utf-8').write('\n'.join(sorted(added)))
    print(f'installed {total} files, {len(reg["outfits"])} outfits registered, {dropped} hidden-part files of an older install removed;'
          ' uninstall with: install_game.py uninstall')


def uninstall():
    added = added_set()
    for rel in sorted(added):
        p = GAME + rel
        if os.path.exists(p): os.remove(p)
    n = 0
    for root, _, fs in os.walk(ORIG):
        for f in fs:
            src = os.path.join(root, f); rel = os.path.relpath(src, ORIG).replace('\\', '/')
            os.makedirs(os.path.dirname(GAME + rel), exist_ok=True); shutil.copy2(src, GAME + rel); n += 1
    # files the Lua writes while the game runs (face snapshot, status), then the folders the install created
    for f in RUNTIME:
        if os.path.exists(GAME + DATA_DIR + f): os.remove(GAME + DATA_DIR + f)
    for d in sorted({os.path.dirname(r) for r in added}, key=len, reverse=True):
        while 'stellar' in d and os.path.isdir(GAME + d) and not os.listdir(GAME + d):   # only our own folders
            os.rmdir(GAME + d); d = os.path.dirname(d)
    if os.path.exists(ADDED): os.remove(ADDED)
    print(f'removed {len(added)} added files, restored {n} originals')


def status():
    added = added_set()
    n = sum(len(fs) for _, _, fs in os.walk(ORIG)) if os.path.exists(ORIG) else 0
    print(f'added files: {len(added)}, originals backed up: {n}')


if __name__ == '__main__':
    {'install': install, 'uninstall': uninstall, 'status': status}[sys.argv[1] if len(sys.argv) > 1 else 'status']()
