"""One Eve outfit onto one Wilds armour (called by build_all.py for every row of data/night_queue.json).

py make_eve_auto.py <row> [--install]

  row       outfit id in data/night_queue.json
  --install copy the result into the game (backups first) and register it for the Lua (outfits_auto.json)

Steps: resolve the armour folder from the game file list -> extract its part files -> extract the Stellar Blade outfit
-> outfit json for build_eve_outfit.py (EVE_OUTFIT_JSON) and material json for build_eve_default_tex.py (EVE_TEX_JSON)
-> build -> textures + body mdf -> arm / leg mdf (only their materials) -> hidden head / waist parts (one plain
material each, mdf cut from the original by eve_mdf_drop.py) -> empty chain2 / gpuc for every replaced part that has one
-> previews -> (install).
"""
import json, os, re, shutil, struct, subprocess, sys, time

import eve_paths as EP
import eve_repro
ROOT = EP.ROOT
SCRIPTS = EP.SCRIPTS
P = EP.WORK
GAME = EP.GAME
BL = EP.BLENDER
TPL = P + 'wilds-armor/ch03_091_0002.blend'
DOTNET = EP.DOTNET
MC = [DOTNET, ROOT + 'tools/motion-convert/bin/motion-convert.dll']
SBX = [DOTNET, ROOT + 'tools/sb-extract/bin/sb-extract.dll']
LIST = EP.slash(EP.get('ree_editor_dir')) + 'MHWS_STM-upstream.list'
FEED = P + 'previews/'
SCR = SCRIPTS
ENV = dict(os.environ, BLENDER_USER_SCRIPTS=EP.USER_SCRIPTS, PYTHONIOENCODING='utf-8',
           MHW_DIR=EP.GAME, SB_PAKS=EP.SB_PAKS, WORK_DIR=P)
LOG = []
SB_SHADERS = False   # set for another SB character's row (q['character']): SB hair / eye / skin tint read from her materials


def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)


def run(cmd, out=None, timeout=1500, env=ENV):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=env)
    if out: open(out, 'w', encoding='utf-8').write(r.stdout + '\n' + r.stderr)
    return r


def blender(script, args, out=None, blend=None, factory=False):
    cmd = [BL, '-b'] + (['--factory-startup'] if factory else []) + ([blend] if blend else []) + ['-P', script, '--'] + args
    return run(cmd, out)


GLIST = [l.strip() for l in open(LIST, encoding='utf-8') if l.startswith('natives/stm/art/model/character/ch03/')]


def folder_files(folder):
    pre = f'natives/stm/art/model/character/{folder}/'
    return [l for l in GLIST if l.startswith(pre) and '/textures/' not in l]


def resolve(path):
    a, b, c = path.split('/')
    cands = [c, c.lstrip('0') or '0', c[-3:], '000']
    if c == '1100': cands = ['100', '000']
    for cc in cands:
        fs = folder_files(f'{a}/{b}/{cc}')
        if any(re.search(r'/2/[^/]+2\.mesh\.', f) for f in fs): return f'{a}/{b}/{cc}', fs
    raise SystemExit(f'no folder for {path}')


def extract(rel, outdir):
    os.makedirs(outdir, exist_ok=True)
    if os.path.exists(os.path.join(outdir, os.path.basename(rel))): return True
    r = run(MC + ['--extract-file', rel, outdir], timeout=200)
    return '"output"' in r.stdout


def sb_extract(code):
    names = [code] + [re.sub(r'_(TypeB|TypeA|V0\d|body|Body|02)$', '', code)] + [re.sub(r'(_[A-Za-z]+)?(_V\d+)?$', '', code)]
    m = re.match(r'(CH_P_EVE_(?:Nikke_|Nier_|Christmas_)?\d+)', code)
    if m: names.append(m.group(1))
    tag = code.lower().replace('ch_p_eve_', '')
    out = P + f'auto-{tag}-suit'
    # the outfit's own folder from the SB file list (DLC outfits live under SB/Content/DLC_n/...)
    lst = [l.strip() for l in open(P + 'sb_pc_list.txt', encoding='utf-8', errors='replace')]
    hit = [l for l in lst if l.lower().endswith('/' + code.lower() + '.uasset')]
    dirs = [os.path.dirname(h) for h in hit] + [f'SB/Content/Art/Character/PC/{n}' for n in dict.fromkeys(names)]
    for dd in dict.fromkeys(dirs):
        if not os.path.isdir(out + '/' + dd):
            run(SBX + ['--export', dd, out], P + f'auto-{tag}-extract.log', timeout=1200)
        for root, _, files in os.walk(out):
            for f in files:
                if f == code + '.glb': return out, os.path.join(root, f).replace('\\', '/')
    raise SystemExit(f'no glb for {code}')


def glb_materials(glb):
    d = open(glb, 'rb').read(); n = struct.unpack_from('<I', d, 12)[0]
    return [m['name'] for m in json.loads(d[20:20 + n])['materials']]


def mat_spec(suit, mat, png):
    js = None
    for root, _, files in os.walk(suit):
        if mat + '.json' in files and 'materials' in root.lower(): js = json.load(open(os.path.join(root, mat + '.json'), encoding='utf-8')); break
    t = {k: v['ObjectName'].split("'")[1] for k, v in (js or {}).get('Textures', {}).items() if "'" in v.get('ObjectName', '')}
    base = t.get('Basecolor') or t.get('BaseColor') or t.get('Diffuse') or t.get('Base Color') or t.get('Base') or t.get('PM_Diffuse')
    orm = t.get('ORM') or t.get('ORSS Mask') or t.get('ORSS')
    nrm = t.get('Baked NormalMap') or t.get('BaseNormal') or t.get('Normal')
    stem = re.sub(r'^(MI_|MA_)', '', mat); stem = re.sub(r'_Inst$', '', stem)
    for pre in ('CH_P_EVE_', ''):     # textures named after the material when the json only has the HDR shader inputs
        nm = stem if stem.startswith('CH_') else pre + stem.replace('CH_P_EVE_', '')
        if not base and nm + '_A' in png: base = nm + '_A'
        if not base and nm + '_D' in png: base = nm + '_D'
        if not orm and nm + '_ORM' in png: orm = nm + '_ORM'
        if not nrm and nm + '_N' in png: nrm = nm + '_N'
    if not base and nrm and nrm.endswith('_N') and nrm[:-2] + '_A' in png: base = nrm[:-2] + '_A'   # skin bodies: only the normal is listed
    sw = (js or {}).get('Switches', {})
    stk = t.get('MASK_Stocking') if sw.get('Use_ML_Stocking') else None
    skin = ('ORSS Mask' in t or any(k in mat for k in ('Basebody', 'BaseBody', '_BB', 'Skin')) or (js or {}).get('ShadingModel') == 5
            or any(k in (base or '') for k in ('_BB_', 'BaseBody')))
    hexc = None
    for k, v in (js or {}).get('Colors', {}).items():
        if 'Base' in k or 'Tint' in k: hexc = v.get('Hex'); break
    if base and base.startswith('T_ML_'): base = None; hexc = 'E6E6E6'   # tiled material-library pattern (not the outfit's UVs): plain light cloth
    kind = 'skin' if skin else ('std' if base and base in png and not base.startswith('T_Solid') else 'flat')
    if kind == 'flat' and base and base.startswith('T_SolidWhite'): hexc = hexc or 'F2F2F2'
    # materials whose colour lives in the parent material / HDR shader (no base texture exported): looked up in SB renders
    FLAT = {'MI_CH_P_EVE_Christmas_01_03': 'E8E4DE', 'MI_EVE_Cos_08_Vinyl': '141414', 'CH_P_EVE_47_Fur': 'F4F4F4', 'MI_CH_P_EVE_59_Emissive': 'FFB040'}
    if kind == 'flat' and mat in FLAT: hexc = FLAT[mat]
    # SB material-layer effects baked into the albedo (user 10-19: Blossom lost its colourful look, Blue Samurai's stockings)
    js_ = js or {}; col = {k: v.get('Hex') for k, v in js_.get('Colors', {}).items()}; sc = js_.get('Scalars', {}); swi = js_.get('Switches', {})
    chn = lambda h: {'FF0000': 0, '00FF00': 1, '0000FF': 2}.get((h or '').upper(), 0)
    fx = {}
    if swi.get('UesFuzzLayer') and t.get('FuzzMask'):
        fx['fuzz'] = [[t['FuzzMask'], chn(col.get(f'Fuzz_{i}_CH', 'FF0000' if i == '01' else '00FF00')), col[f'FUZZ_{i}_COLOR'],
                       float(sc.get(f'Fuzz_{i}_INTENSITY', 0.5))] for i in ('01', '02') if col.get(f'FUZZ_{i}_COLOR')]
    if t.get('ThinFilmMask'):
        fx['film'] = [t['ThinFilmMask'], 2, float(sc.get('FilmIntensity', 0.5))]
    if swi.get('Use_ML_Stocking') and t.get('MaterialLayerMask') and col.get('ML_STK_StockingTint'):
        fx['stocking'] = [t['MaterialLayerMask'], chn(col.get('ML_Stocking_CH', 'FF0000')), col['ML_STK_StockingTint']]
    if col.get('Base Color Tint'): fx['tint'] = col['Base Color Tint']
    if SB_SHADERS:   # another SB character (Scarlet): her hair cards (SB hair shader) and eyes (iris texture) as in SB
        if t.get('HairTexture') and col.get('RootColor') and col.get('TipColor'): fx['sbHair'] = [t['HairTexture'], col['RootColor'], col['TipColor']]
        if t.get('IrisColor'): fx['sbEye'] = t['IrisColor']
        if skin and col.get('BaseTint'): fx['skinTint'] = col['BaseTint']
        # SB lights her armour with an image-based reflection (HDR_Intensity 0.5 / 2.77) that Wilds does not have; the same
        # ORM looked dull in game (user 10-25 "metal gloss differs") -> glossier and more metallic, more where SB's HDR is stronger
        if not skin and sc.get('HDR_Intensity') and not fx.get('sbHair'):
            h = float(sc['HDR_Intensity'])
            fx['metalMul'] = 1.5 if h > 1 else 1.3
            if not (fx.get('fuzz') or fx.get('stocking')): fx['roughMul'] = 0.6 if h > 1 else 0.75   # cloth / stockings keep their sheen
    if swi.get('UsePatternTiling') and col.get('Pattern01_Tint') and t.get('Mask'):   # tiled fabric layer tinted over the mask (Holiday Rabbit)
        fx['pattern'] = [t['Mask'], 0, col['Pattern01_Tint'], float(sc.get('Pattern01_BasecolorIntensity', 0.8))]
    return [mat, kind, base, orm, nrm, stk, hexc or '262626', fx]   # unknown shader colour: dark (glass / vinyl / lace were black in SB)


def mdf_mats(paths):
    r = blender(SCR + 'mdf_list.py', paths, factory=True)
    out = {}
    for l in r.stdout.splitlines():
        if l.startswith('MATS '):
            p, lst = l[5:].split(' :: ', 1); out[p] = json.loads(lst)
    return out


def mesh_mats(path, pfx):
    d = open(path, 'rb').read()
    return sorted(set(x.decode() for x in re.findall(rb'%s\d\d' % pfx.encode(), d)))


def main():
    row = int(sys.argv[1]); install = '--install' in sys.argv
    q = {e['row']: e for e in json.load(open(EP.DATA + 'night_queue.json', encoding='utf-8'))}[row]
    code = q['code'][1]
    tag = f'auto{row}'
    pfx = 'e' + chr(97 + (row // 26) % 26) + chr(97 + row % 26)
    B = P + f'{tag}-build/'; ST = B + 'stage/'
    if os.path.exists(B + 'info.json'): os.remove(B + 'info.json')   # written again only when this build finishes (install reads it)
    os.makedirs(ST, exist_ok=True)
    log(f'== row {row} {q["armor"]} <- {q["eve"]} ({code}) pfx {pfx}')
    folder, files = resolve(q['path'])
    a_, b_, c_ = folder.split('/'); opre = f'{a_}_{b_}_{c_}'
    log('folder', folder, len(files), 'files')
    global SB_SHADERS
    SB_SHADERS = bool(q.get('character'))
    W = P + f'wilds-{tag}/'
    parts = {}
    for f in files:
        m = re.match(rf'natives/stm/art/model/character/{folder}/(\d)/([^/]+)$', f)
        if not m: continue
        n, fn = int(m.group(1)), m.group(2)
        if re.search(r'\.(mesh\.241111606|mdf2\.45|chain2\.14|clsp\.3)$', fn) or '.gpuc.' in fn:
            parts.setdefault(n, []).append(fn)
    for n, fns in parts.items():
        for fn in fns:
            rel = f'art/model/character/{folder}/{n}/{fn}'
            if fn.endswith(('.mesh.241111606', '.mdf2.45', '.chain2.14')):
                extract(rel, W + f'natives/stm/art/model/character/{folder}/{n}')
                if fn.endswith('.mesh.241111606'): extract('streaming/' + rel, W + f'natives/stm/streaming/art/model/character/{folder}/{n}')
    log('parts', {n: sorted(v) for n, v in parts.items()})
    suit, glb = sb_extract(code)
    png = {}
    for root, _, fs in os.walk(suit):
        for f in fs:
            if f.endswith('.png'): png.setdefault(f[:-4], os.path.join(root, f).replace('\\', '/'))
    for root, _, fs in os.walk(P + 'sb-refbody'):     # SB reference body textures (shared skin bodies)
        for f in fs:
            if f.endswith('.png'): png.setdefault(f[:-4], os.path.join(root, f).replace('\\', '/'))
    mats = glb_materials(glb)
    specs = [mat_spec(suit, m, png) for m in mats]
    log('materials', specs)
    skin_mat = next((s[0] for s in specs if s[1] == 'skin'), None)
    texd = suit[len(P):] + '/'
    base = {}
    for s in specs:
        if s[2] in png and png[s[2]].startswith(P + texd): base[s[0]] = png[s[2]][len(P + texd):-4]
    # hidden parts: head (3) and waist (5) + every extra mesh of those parts; one plain material each
    # rows built as ONE piece (user 10-19: the part split left saw-tooth seams, Afi test): the whole Eve in the body part,
    # arm / leg parts hidden like head / waist
    NOSPLIT = 'all'   # user 10-19: Afi test fixed the seams -> every auto outfit as one piece
    nosplit = NOSPLIT == 'all' or row in NOSPLIT
    hidden_ns = (1, 3, 4, 5) if nosplit else (3, 5)
    mdfs = {}
    for n in hidden_ns:
        for fn in parts.get(n, []):
            if fn.endswith('.mdf2.45'): mdfs[f'{n}/{fn}'] = W + f'natives/stm/art/model/character/{folder}/{n}/{fn}'
    mm = mdf_mats(list(mdfs.values())) if mdfs else {}
    def plain(lst):
        ok = [nm for nm, sh in lst if sh in ('Base_Equip_NoMultiBlend.mmtr', 'Base_Equip.mmtr') and not any(k in nm.lower() for k in ('hair', 'shellfer', 'fur', '_ve_', 'ice', 'emi', 'glow'))]
        ok.sort(key=lambda nm: (nm != 'cage', 'knife' in nm))   # one plain material is enough for a hidden triangle
        return ok[:1]
    cage_src = None
    for k, p_ in mdfs.items():
        for nm, sh in mm.get(p_, []):
            if nm == 'cage': cage_src = p_
    hide, hide_extra, hide_mdf = {}, {}, {}
    for k, p_ in mdfs.items():
        n = int(k.split('/')[0]); stem = k.split('/')[1][:-len('.mdf2.45')]
        if f'{stem}.mesh.241111606' not in parts.get(n, []): continue
        ok = plain(mm.get(p_, []))
        src = p_
        if not ok and cage_src: ok, src = ['cage'], cage_src
        if not ok: ok = [mm.get(p_, [['cage', '']])[0][0]]
        if stem == f'{opre}{n}': hide[n] = ok
        else: hide_extra[f'{n}/{stem}'] = ok
        hide_mdf[f'{n}/{stem}'] = (src, ok)
    split = {2: ['body', 'waist', 'head']}
    if any(f == f'{opre}1.mesh.241111606' for f in parts.get(1, [])): split[1] = ['arm']
    else: split[2].append('arm')
    if any(f == f'{opre}4.mesh.241111606' for f in parts.get(4, [])): split[4] = ['leg']
    else: split[2].append('leg')
    if nosplit: split = {2: ['body', 'waist', 'head', 'arm', 'leg']}
    oc = dict(sub='101', name=f'eve{tag}', pfx=pfx, odir=folder, opre=opre, split=split, keys=mats, texd=texd, base=base,
              hide=hide, hideExtra=hide_extra, neckAuto=True, skinMat=skin_mat, toeExtra='auto')
    oc['dropMats'] = [sp[0] for sp in specs if sp[1] == 'flat' and 'Decal' in sp[0]]   # texture-less decals drew as dark patches (Breakcat leg, 10-19)
    # per-row fixes from the user's game checks (10-19)
    # round 4 (10-19, checked against the running original SB): Planet Dive 7th's sheer back panels hang from the shoulders
    # over the back and stay close to the body (ours swung with the upper arm) -> rooted on Spine_2, stiff 'veil' chain;
    # Diver alpha: only part 5 (waist) has a chain the game loads -> the Eve body goes to part 5 (bodyPart);
    # Cyber Bunny: natural V cleavage in SB, our cleavage fill dented the right inner breast -> off; Holiday Rabbit: hood
    # strings hang straight down in SB (no own swing), suit is dark charcoal -> strings skinned, plain 6C5246 multiply;
    # YoRHa uniform sleeves hang straight down from the forearm in SB -> drape chains free to fall (170 deg)
    # round 5 (10-19 user photos): 144 panels hang by gravity (no spring back to the T-pose shape) + SB pattern on the veil;
    # 157 hood fur shell drew as dark smudges on the collarbones -> dropped, hood chains crumpled the shoulder straps -> off;
    # 158 sleeves: 6 bones, 12 cm blend from the arm, joints after the root nearly straight; ribbons hang skinned
    OVR = {144: {'chainRoot': {'Ab_Cape': 'Spine_2'}, 'chainKind': {'Ab_Cape': 'veil'}, 'kindSet': {'veil': [0.4, 0.0, 45]},
                 'capeNarrow': [{'match': 'Ab_Cape', 'k': 0.35, 'depth': 0.3, 'rootT': 0.4, 'clear': 0.025}]},
           149: {'bodyPart': 5, 'limbRefWrite': True},   # Diver = reference body (user 10-19)
           151: {'toeExtra': '-12'},
           # hand-built outfits rebuilt as one piece (10-19), keeping their approved per-outfit settings
           # 9041 Racer's High: grafted neck skin showed through the hood folds at the collarbones (user 10-20): shorter graft + cull all skin pieces
           9041: {'neckDown': '0.025', 'skinCullAll': True, 'collarClear': '0.003', 'toeExtra': '0', 'neckFrom': ['eve63-suit/SB/Content/Art/Character/PC/CH_P_EVE_63/CH_P_EVE_63.glb', 'MI_Basebody_V02_F1', 'MI_Basebody_V02_F2']},
           # 9034 Moran: the auto spec tinted the grey dress yellow (FFDA00) and painted the white laces dark (user 10-19, game)
           9034: {'skirtThigh': ['Ab-L-SkirtA', 'Ab-R-SkirtA', 'Ab-L-SkirtC', 'Ab-R-SkirtC'], 'dropIslands': [['MI_CH_P_EVE_34_ACC', 0.90, 1.10, 0.12]],
                  'fxOverride': {'MI_CH_P_EVE_34_Suit': {}, 'MI_CH_P_EVE_34_ACC': {}}, 'specHex': {'MI_CH_P_EVE_34_ACC': 'F2F2F2'}},
           9018: {'chainSkip': ['String'],   # Daily Mascot front string: chain made it float at an odd angle (user 10-19)
                  # stockings: SB MA_CH_Stocking, mask CH_costume_13_02_Mask R -- were baked as the light albedo (user 10-20: darker)
                  'fxOverride': {'MI_EVE_Cos_18_02': {'stocking': ['CH_costume_13_02_Mask', 0, '141213']}}},
           147: {'chainSkip': ['SuiteA']},   # Blossom: the front under-skirt chain sagged out below the outer skirt (user 10-20)
           190: {'chainSkip': ['shoulderFrill']},   # Noblesse: swinging shoulder frills cut into the armpit (user 10-20)
           152: {'cleavageFill': '0'},
           # 157 Omega: reset to the plain automatic build (user 10-19: fixes on top kept making it worse)
           157: {'toeExtra': '0'},   # Holiday Rabbit replaced by 4Seconds Destroyed Denim (CH_P_EVE_51) per user 10-19; closed heels: no toe lift
           148: {'chainSkip': ['neck']},   # Afi necktie: hangs skinned on the chest (chain made it float at an angle, 10-19)
           158: {'drapes': [{'bone': 'Ab-L-Forearm-Tw1', 'min_dist': 0.08}, {'bone': 'Ab-R-Forearm-Tw1', 'min_dist': 0.08}],
                 'kindLimit': {'drape': 170}, 'drapeBones': 6, 'drapeFade': 0.05, 'drapeNodeLimit': 150, 'drapeGravity': 3.0, 'drapePart': 1, 'drapeHang': True, 'kindSet': {'drape': [0.15, 0.0, 170]},
                 # 10-20 (user, side by side with SB): face across the back, narrower tip, less sticking out behind
                 'hangTwist': 0.75, 'hangTaper': 0.5, 'hangCurlTop': 60, 'hangCurl': 240, 'hangPleats': 3, 'hangPleatAmp': 0.012, 'hangBack': 0.0, 'hangBend': 0.1, 'hangFar': 0.06,
                 'chainSkip': ['ClothRibbon', 'RibbonC']}}
    # another Stellar Blade character (10-25, Scarlet CH_M_NA_961, user: "not an Eve outfit -- fit it to her, mind the head
    # and the whole body proportions"): her mesh carries her own body, clothes and hair -> keep her shape (no Eve bust
    # growth / cleavage fill / limb girth normalising to Eve), no Eve ponytail or hairpin, hair strands as physics chains;
    # her face is built from her own facial mesh below and swapped in by the Lua (outfits_auto.json "faces")
    CH = q.get('character')
    if CH:
        oc.update(ownHair=True, hairChains=True, bust='1.0', cleavageFill='0', limbNormalize=False)
        oc.update(q.get('ovr', {}))
    ovr = dict(OVR.get(row, {}))
    fxo = ovr.pop('fxOverride', {})
    for sp in specs:
        if sp[0] in ovr.get('specHex', {}): sp[6] = ovr['specHex'][sp[0]]
    ovr.pop('specHex', None)
    for sp in specs:
        if sp[0] in fxo: sp[7] = fxo[sp[0]]
    # queue "fxAdd" {material: {fx key: value}}: merged into that material's fx (Scarlet gloss B, user 10-25 from previews)
    for sp in specs:
        if sp[0] in q.get('fxAdd', {}): sp[7] = dict(sp[7] or {}, **q['fxAdd'][sp[0]])
    eve_repro.specs(str(row), specs, lambda m: mat_spec(suit, m, png), log)   # approved common-skin look (data/repro)
    oc.update(ovr)
    eve_repro.outfit(str(row), oc, log)
    if nosplit: oc.pop('drapePart', None)   # one piece: sleeve drapes stay in the body chain
    bodyN = int(oc.get('bodyPart', 2))
    json.dump(oc, open(B + 'outfit.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    json.dump(specs, open(B + 'tex.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    # build
    t0 = time.time()
    env = dict(ENV, EVE_OUTFIT_JSON=B + 'outfit.json')
    r = run([BL, '--background', TPL, '--python', SCRIPTS + 'build_eve_outfit.py', '--', glb, ST, B + 'report.json'], B + 'build.log', env=env)
    rep = json.load(open(B + 'report.json', encoding='utf-8')) if os.path.exists(B + 'report.json') else {}
    log('build', r.returncode, 'export errors', open(B + 'build.log', encoding='utf-8').read().count('Unable to export'), round(time.time() - t0), 's',
        {k: rep.get(k) for k in ('splitVerts', 'neckGraft', 'neckSkinFaces', 'toeAuto', 'looseDropped', 'shoulderXfer')})
    if r.returncode != 0 or not rep: raise SystemExit('build failed')
    D = f'art/model/character/{folder}'
    body_mesh = ST + f'natives/stm/{D}/2/{opre}2.mesh.241111606'    # the build writes the Eve body as part 2
    eve_repro.mesh(str(row), body_mesh, B, log)
    if os.path.exists(ST + f'natives/stm/{D}/2/{opre}2.chain2.14'): eve_repro.chain(str(row), ST + f'natives/stm/{D}/2/{opre}2.chain2.14', log)
    srcs = f'{suit};{P}sb-refbody;{P}eve-hair;{P}eve-sword01-full'
    PRESETS = {'CH_P_EVE_09': dict(EVE_AUTO_PRESET='09', EVE_CAPE_VEIL='1', EVE_CAPE_PATTERN='1', EVE_CAPE_TILED='1', EVE_CAPE_ALPHA='0.72', EVE_CAPE_SPARK='2.4', EVE_DECO_GLOW='1', EVE_VINYL_ROUGH='0.05',
                                   EVE_VINYL_METAL='0.7', EVE_FABRIC_ROUGH='0.25', EVE_METAL_ROUGH='0.6'),
               'CH_P_EVE_Nikke_02': dict(EVE_STK_SHEER='0.5')}   # Blossom: sheer white stockings, skin shows through (user 10-19)   # approved 09 look (STATUS 10-1x)
    env = dict(ENV, **PRESETS.get(code, {}))
    env = dict(env, EVE_SKIN_REF='0.717,0.512,0.476')   # Diver (Blue Monsoon, row 149) skin tone for every outfit (user 10-19)
    env = dict(env, **eve_repro.tex_env(str(row)))
    if CH:   # her own skin colour: SB's skin tint on her own texture, no gain toward Eve's skin tone
        env.pop('EVE_SKIN_REF', None); env['EVE_SKIN_PROFILE'] = 'common_v1'
    env = dict(env, EVE_OUTFIT='auto', EVE_TEX_JSON=B + 'tex.json', EVE_MAT_PREFIX=pfx, EVE_TEX_REL=f'stellar/{tag}/tex', EVE_HAIR_STRANDS='1')
    allkeys = [f'{pfx}{i:02d}' for i in range(len(mats) + 2)]
    for n in sorted(split):
        meshf = ST + f'natives/stm/{D}/{n}/{opre}{n}.mesh.241111606'
        used = mesh_mats(meshf, pfx)
        e = dict(env, EVE_MDF_NAME=f'{opre}{n}', EVE_MDF_DIR=f'{D}/{n}')
        if n != 2: e['EVE_SKIP_TEX'] = '1'
        skip = [k for k in allkeys if k not in used]
        if skip: e['EVE_MDF_SKIP'] = ','.join(skip)
        r = run([BL, '--background', TPL, '--python', SCRIPTS + 'build_eve_default_tex.py', '--', srcs, ST + 'natives/stm', B + f'tex_report{n}.json'], B + f'tex{n}.log', env=e)
        log('mdf', n, r.returncode, 'tracebacks', open(B + f'tex{n}.log', encoding='utf-8').read().count('Traceback'), 'used', used)
    eve_repro.textures(str(row), body_mesh, ST + f'natives/stm/stellar/{tag}/tex', B, log, keep=allkeys[len(mats):])   # hair, sword
    face_rel = None
    if CH and q.get('face'):
        # her head as the Wilds face mesh (build_eve_face.py with her facial glb / materials), textures + mdf from her own
        # material jsons like the body (EVE_OUTFIT=auto); the Lua swaps Player_Face to it while this outfit is worn
        fq = q['face']; fglb = None
        for root_, _, fs_ in os.walk(suit):
            if fq['glb'] + '.glb' in fs_: fglb = os.path.join(root_, fq['glb'] + '.glb').replace('\\', '/'); break
        if not fglb: raise SystemExit(f'no face glb {fq["glb"]}')
        fpfx = pfx[:2] + 'f'; face_rel = f'stellar/{tag}/face/{tag}_face'
        e = dict(ENV, EVE_FACE_GLB=fglb, EVE_FACE_HAIR='', EVE_FACE_KEEP=','.join(fq['keep']), EVE_FACE_SKIN=fq['skin'],
                 EVE_FACE_EYE=fq['eye'], EVE_FACE_TEETH=fq['teeth'], EVE_FACE_PFX=fpfx, EVE_FACE_OUT=face_rel + '.mesh.241111606',
                 EVE_FACE_BODY=f'{D}/2/{opre}2.mesh.241111606')
        r = run([BL, '--background', TPL, '--python', SCRIPTS + 'build_eve_face.py', '--', B, ST], B + 'face.log', env=e)
        log('face', r.returncode, 'tracebacks', open(B + 'face.log', encoding='utf-8').read().count('Traceback'))
        if r.returncode != 0 or not os.path.exists(ST + f'natives/stm/{face_rel}.mesh.241111606'): raise SystemExit('face build failed')
        fspecs = [mat_spec(suit, m, png) for m in fq['keep']]
        for sp in fspecs:
            sp_fx = fq.get('fx', {}).get(sp[0])
            if sp_fx is not None: sp[7] = sp_fx
            if sp[0] == fq['skin']: sp[1] = 'skin'
            elif sp[1] == 'skin': sp[1] = 'std'   # teeth (SB skin shading model) are not face skin
            if sp[0] in fq.get('hex', {}): sp[1] = 'flat'; sp[6] = fq['hex'][sp[0]]   # texture-less SB colours (brows / lashes)
        json.dump(fspecs, open(B + 'face_tex.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        fkeys = [f'{fpfx}{i:02d}' for i in range(len(fq['keep']) + 2)]
        e = dict(env, EVE_TEX_JSON=B + 'face_tex.json', EVE_MAT_PREFIX=fpfx, EVE_TEX_REL=f'stellar/{tag}/face/tex',
                 EVE_MDF_NAME=f'{tag}_face', EVE_MDF_DIR=f'stellar/{tag}/face', EVE_MDF_SKIP=','.join(fkeys[len(fq['keep']):]))
        r = run([BL, '--background', TPL, '--python', SCRIPTS + 'build_eve_default_tex.py', '--', srcs, ST + 'natives/stm', B + 'face_tex_report.json'], B + 'face_tex.log', env=e)
        log('face mdf', r.returncode, 'tracebacks', open(B + 'face_tex.log', encoding='utf-8').read().count('Traceback'))
    for k, (src, keep) in hide_mdf.items():
        n, stem = k.split('/')
        r = blender(SCRIPTS + 'eve_mdf_drop.py', [src, ST + f'natives/stm/{D}/{n}/{stem}.mdf2.45', ','.join(keep)], blend=TPL)
        log('hidden mdf', k, keep, 'ok' if 'FINISHED' in r.stdout else 'FAIL')
    # replaced parts keep no original physics: empty chain2 for parts 1,3,4,5; empty gpuc (all listed versions)
    drapeN = int(oc.get('drapePart', 0))
    for n in (1, 3, 4, 5):
        for fn in parts.get(n, []):
            dst = ST + f'natives/stm/{D}/{n}/{fn}'
            if fn.endswith('.chain2.14') and n == drapeN and os.path.exists(dst): log('own chain', n); continue
            if fn.endswith('.chain2.14'):
                r = blender(SCRIPTS + 'eve_chain_empty.py', [W + f'natives/stm/{D}/{n}/{fn}', dst], factory=True)
                log('empty chain', n, 'ok' if 'GROUPS after 0' in r.stdout else 'FAIL')
            if '.gpuc.' in fn:
                os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(b'GCLO'); log('empty gpuc', fn)
    own_chain = any(f.endswith('.chain2.14') for f in parts.get(2, []))
    if bodyN != 2:
        # the build writes the Eve body as part 2 and the one-triangle hidden mesh as part bodyN: swap their mesh / mdf,
        # and the body's chain2 replaces the (emptied) chain of part bodyN, whose Chain2 component the game creates
        P2, PN = ST + f'natives/stm/{D}/2/', ST + f'natives/stm/{D}/{bodyN}/'
        for ext in ('.mesh.241111606', '.mdf2.45'):
            a_f, b_f = P2 + f'{opre}2{ext}', PN + f'{opre}{bodyN}{ext}'
            tmp = a_f + '.swap'; os.replace(a_f, tmp); os.replace(b_f, a_f); os.replace(tmp, b_f)
        os.replace(P2 + f'{opre}2.chain2.14', PN + f'{opre}{bodyN}.chain2.14')
        own_chain = True
        log('body part', bodyN, 'swapped with 2')
    # previews
    PV = [B + f'eve{tag}_{t}.png' for t in ('rest_front', 'rest_side', 'jog0_front', 'sprint_side', 'dodge_side')]
    if EP.PREVIEWS: os.makedirs(FEED, exist_ok=True); blender(SCR + 'stitch.py', [FEED + f'{row}_{q["eve"]}_빌드미리보기.png', '0,0,0.5,1'] + [p for p in PV if os.path.exists(p)], factory=True)
    info = dict(row=row, armor=q['armor'], eve=q['eve'], folder=folder, opre=opre, body=f'{opre}{bodyN}', tag=tag,
                chainFix=None if own_chain else f'Art/Model/Character/{folder}/2/{opre}2.chain2',
                hidePhys=[f'{opre}{n}' for n in (1, 3, 4, 5) if n not in (bodyN, drapeN) and any(f.startswith(f'{opre}{n}.') for f in parts.get(n, []))] +
                         [k.split('/')[1] for k in hide_extra])
    if bodyN != 2: info['dropKeys'] = [f'{opre}2']; info['unhide'] = [f'{opre}{bodyN}']
    if face_rel: info['face'] = {'mesh': face_rel + '.mesh', 'mdf': face_rel + '.mdf2'}
    if drapeN: info.setdefault('unhide', []).append(f'{opre}{drapeN}')
    json.dump(info, open(B + 'info.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    if q.get('memo') and ('마름모' in q['memo'] or '원형' in q['memo']):
        # user note: pieces crafted as both armour types (diamond / round icons) -> the same Eve parts also in the other
        # type folder (000 <-> 001), renamed; empty chain / gpuc where that folder has them
        tf = f'{a_}/{b_}/' + ('000' if c_ == '001' else '001')
        tfiles = folder_files(tf); topre = tf.replace('/', '_')
        TS = ST + 'natives/stm/art/model/character/' + tf + '/'
        n_tw = 0
        for root, _, fs in os.walk(ST + f'natives/stm/{D}'):
            for f in fs:
                n = os.path.basename(root); nf = f.replace(opre, topre, 1)
                if any(t.endswith(f'/{tf}/{n}/{nf}') for t in tfiles) or nf.endswith('.mdf2.45') and any(t.endswith(f'/{tf}/{n}/' + nf.replace('.mdf2.45', '.mesh.241111606')) for t in tfiles):
                    os.makedirs(TS + n, exist_ok=True); shutil.copy2(os.path.join(root, f), TS + n + '/' + nf); n_tw += 1
        for t in tfiles:
            m = re.match(rf'natives/stm/art/model/character/{tf}/(\d)/([^/]+)$', t)
            if not m or m.group(1) in ('2', '6'): continue
            dst = TS + m.group(1) + '/' + m.group(2)
            if '.gpuc.' in t: os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(b'GCLO'); n_tw += 1
            if t.endswith('.chain2.14') and not os.path.exists(dst):
                srcd = W + f'natives/stm/art/model/character/{tf}/{m.group(1)}'
                if extract(t[len('natives/stm/'):], srcd):
                    blender(SCRIPTS + 'eve_chain_empty.py', [srcd + '/' + m.group(2), dst], factory=True); n_tw += 1
        info['twin'] = dict(body=f'{topre}2', chainFix=None if any(t.endswith(f'/2/{topre}2.chain2.14') for t in tfiles) else f'Art/Model/Character/{tf}/2/{topre}2.chain2',
                            hidePhys=[f'{topre}{n}' for n in (1, 3, 4, 5) if n != drapeN], files=n_tw)
        if drapeN: info.setdefault('unhide', []).append(f'{topre}{drapeN}')
        log('twin folder', tf, n_tw, 'files')
        json.dump(info, open(B + 'info.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    if install: do_install(info, B, ST)
    open(B + 'auto.log', 'w', encoding='utf-8').write('\n'.join(LOG))


def do_install(info, B, ST):
    stamp = time.strftime('%H%M%S')
    IB = P + f'install-backup/auto-{info["row"]}-{stamp}/'
    os.makedirs(IB, exist_ok=True)
    n_new = n_old = 0
    from install_game import hidden_stems, stem      # hidden parts are not installed (the Lua hides them at runtime)
    skip = hidden_stems(info)
    for root, _, fs in os.walk(ST + 'natives'):
        for f in fs:
            if stem(f) in skip: continue
            src = os.path.join(root, f); rel = os.path.relpath(src, ST).replace('\\', '/'); dst = GAME + rel
            if os.path.exists(dst):
                os.makedirs(os.path.dirname(IB + rel), exist_ok=True); shutil.copy2(dst, IB + rel); n_old += 1
            else: n_new += 1
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
    jn = f'auto_{info["row"]}_joints.json'
    shutil.copy2(B + 'eve_outfit_joints.json', GAME + 'reframework/data/stellar-eve/' + jn)
    af = GAME + 'reframework/data/stellar-eve/outfits_auto.json'
    a = json.load(open(af, encoding='utf-8')) if os.path.exists(af) else {}
    if os.path.exists(af): shutil.copy2(af, IB + 'outfits_auto.json')
    for k in info.get('dropKeys', []):
        a.get('outfits', {}).pop(k, None); a.get('chainFix', {}).pop(k, None)
    a.setdefault('outfits', {})[info['body']] = 'stellar-eve/' + jn
    if info.get('face'): a.setdefault('faces', {})[info['body']] = info['face']
    if info['chainFix']: a.setdefault('chainFix', {})[info['body']] = info['chainFix']
    hp = set(a.get('hidePhys', [])); hp.update(info['hidePhys']); hp.difference_update(info.get('unhide', []))
    if info.get('twin'):
        tw = info['twin']; a['outfits'][tw['body']] = 'stellar-eve/' + jn; hp.update(tw['hidePhys']); hp.difference_update(info.get('unhide', []))
        if tw['chainFix']: a.setdefault('chainFix', {})[tw['body']] = tw['chainFix']
    a['hidePhys'] = sorted(hp)
    a['keep'] = sorted(set(a.get('keep', [])) | (set(info.get('unhide', [])) - {info['body']}))
    json.dump(a, open(af, 'w', encoding='utf-8'), indent=1)
    log('installed', n_new, 'new', n_old, 'replaced (backup', IB, ')')


if __name__ == '__main__':
    main()
