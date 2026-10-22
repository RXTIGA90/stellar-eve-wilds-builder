"""Build everything from the user's own games: prepare -> Eve's face + default looks -> every Eve outfit in data/night_queue.json.

usage: python build_all.py [--rows 144,146,...] [--skip-prepare] [--skip-base] [--jobs N]
  --rows: only those outfits. 27 = default look innerwear beta type 2 (Ocean Maid), 63 = type 1 (Wave Diver Bikini).
          Eve's face (shared by every outfit) is always built once and kept; the default looks are installed only when
          chosen (work/innerwear-<id>.selected). Without --rows: everything.
  --jobs: outfits built at the same time (default 1). Each outfit has its own work folders; with N > 1 every outfit's
          output goes to work/logs/auto<row>.log. About 4 CPU threads and 6 GB RAM per job.
Runs with any Python 3.10+ (the installer uses the Python that ships inside Blender).
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eve_paths as EP

INNERWEAR = {'27': 'ocean_maid_joints.json', '63': 'wave_bikini_joints.json'}


def step(script, *args):
    t0 = time.time()
    print(f'=== {script} {" ".join(args)}', flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args])
    print(f'=== {script} finished in {round(time.time() - t0)} s (exit {r.returncode})', flush=True)
    return r.returncode


def step_logged(row):
    """one outfit with its output in work/logs/auto<row>.log (parallel builds)"""
    os.makedirs(EP.WORK + 'logs', exist_ok=True)
    t0 = time.time()
    with open(EP.WORK + f'logs/auto{row}.log', 'w', encoding='utf-8') as f:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'make_eve_auto.py'), str(row)], stdout=f, stderr=subprocess.STDOUT)
    print(f'=== outfit {row} finished in {round(time.time() - t0)} s (exit {r.returncode})', flush=True)
    return r.returncode


def built(oid):
    return os.path.exists(EP.WORK + f'base{oid}-build/stage/reframework/data/stellar-eve/{INNERWEAR[oid]}')


def main():
    a = sys.argv[1:]
    rows = None
    if '--rows' in a:
        rows = [x.strip() for x in a[a.index('--rows') + 1].split(',') if x.strip()]
    chosen = set(INNERWEAR) if rows is None else {r for r in rows if r in INNERWEAR}
    if '--skip-prepare' not in a and step('prepare.py'): raise SystemExit('prepare failed')
    if '--skip-base' not in a:
        if rows is None:
            todo = ['27', '63']                                    # full build: rebuild both
        else:
            # type 2 (27) also makes Eve's face, which every outfit needs: built once and kept
            todo = [o for o in ('27', '63') if (o == '27' or o in chosen) and not built(o)]
        if todo and step('build_base.py', *todo): raise SystemExit('base build failed')
        if not todo: print('=== face / default looks already built, kept', flush=True)
    os.makedirs(EP.WORK, exist_ok=True)
    for o in chosen:                                               # remembered: later installs keep this default look
        open(EP.WORK + f'innerwear-{o}.selected', 'w').close()
    qall = json.load(open(EP.DATA + 'night_queue.json', encoding='utf-8'))
    queue = [q['row'] for q in qall if rows is None or str(q['row']) in rows]
    # outfits this Stellar Blade does not have (DLC not installed) are skipped, not failed
    lst = EP.WORK + 'sb_pc_list.txt'
    have = open(lst, encoding='utf-8', errors='replace').read().lower() if os.path.exists(lst) else None
    code = {q['row']: q['code'][1] for q in qall}
    missing = [row for row in queue if have is not None and '/' + code[row].lower() + '.uasset' not in have]
    queue = [row for row in queue if row not in missing]
    for row in missing: print(f'=== outfit {row} ({code[row]}) is not in your Stellar Blade (DLC not installed?): skipped', flush=True)
    jobs = max(1, int(a[a.index('--jobs') + 1])) if '--jobs' in a else 1
    if jobs == 1:
        failed = [row for row in queue if step('make_eve_auto.py', str(row))]
    else:
        with ThreadPoolExecutor(jobs) as ex:
            failed = [row for row, rc in zip(queue, ex.map(step_logged, queue)) if rc]
    print('failed outfits:', failed or 'none', '| skipped (not in your Stellar Blade):', missing or 'none')
    # the outfits that did build are still installed; only a run where nothing built is a failure
    if queue and len(failed) == len(queue): raise SystemExit(1)


if __name__ == '__main__':
    main()
