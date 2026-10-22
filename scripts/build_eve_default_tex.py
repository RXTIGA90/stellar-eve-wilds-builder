"""Textures + mdf2 for Eve's default look (materials evd00..09, see build_eve_default.py KEYS).

Same packing as build_eve_body_mesh.py (ALBD = RGB albedo, A = 1-metal; NRRO = R rough, G normal Y, B AO, A normal X;
ATOS R = alpha), from the original Stellar Blade textures of CH_P_EVE_08 / BaseBody / Face / EVE_HR_01.
Template: native armor import blend (Base_Equip_NoMultiBlend material ch03_091_0002_body_UseSC).
Usage: blender --background <armor template blend> --python build_eve_default_tex.py -- <asset root> <stage natives/stm> <report>
Output: <stage>/stellar/eve/eve_default.mdf2.45 and <stage>/stellar/eve/tex/evdNN_*.tex.241106027
"""
import bpy, sys, os, json
import numpy as np
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()
import ctypes; ctypes.windll.ole32.CoInitializeEx(None, 0)
from RE_Mesh_Editor.modules.ddsconv.directx.texconv import Texconv, unload_texconv
from RE_Mesh_Editor.modules.tex.re_tex_utils import DDSToTex
from RE_Mesh_Editor.modules.tex.file_re_tex import getTexVersionFromGameName

asset_root, stage, report_path = sys.argv[sys.argv.index('--') + 1:]
REL, TEX_REL = os.environ.get('EVE_MDF_DIR', 'stellar/eve'), os.environ.get('EVE_TEX_REL', 'stellar/eve/tex')   # EVE_OUTFIT=27: mdf next to the replaced armour mesh
out_dir = os.path.join(stage, *REL.split('/')); tex_dir = os.path.join(stage, *TEX_REL.split('/'))
tmp = os.path.join(os.path.dirname(report_path), 'eve_default_tex_tmp')
for d in (out_dir, tex_dir, tmp): os.makedirs(d, exist_ok=True)
report = {}

png_index = {}
for root, dirs, files in (w for r_ in asset_root.split(';') for w in os.walk(r_)):   # several roots: 'a;b'
    dirs.sort(key=lambda d: d.lower() == 'old')          # prefer current textures over Old/ copies
    for f in files:
        if f.lower().endswith('.png'):
            png_index.setdefault(os.path.splitext(f)[0], os.path.join(root, f))
SIZE = 2048


def img(name, size=SIZE):
    im = bpy.data.images.load(png_index[name]); im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    ys = np.arange(size) * h // size; xs = np.arange(size) * w // size
    return a[ys][:, xs]


def const(rgb, a=1.0, size=64):
    arr = np.ones((size, size, 4), np.float32); arr[..., :3] = rgb; arr[..., 3] = a; return arr


def srgb_hex(h): return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def pack(albedo, metal, rough, ao, nx, ny, alpha=None):
    s = albedo.shape[0]
    def fit(x):
        if np.isscalar(x): return np.full((s, s), x, np.float32)
        if x.shape[0] != s:
            ys = np.arange(s) * x.shape[0] // s; return x[ys][:, ys]
        return x
    albd = np.dstack([albedo[..., 0], albedo[..., 1], albedo[..., 2], 1.0 - fit(metal)])
    # Wilds NRRO stores the tangent normal rotated by 45 deg and sign-sqrt compressed: G = x', A = y' (Y flipped), R = rough,
    # B = AO. This is the exact inverse of RE Mesh Editor's NRRXToNRMR decoder. Input nx / ny are a DirectX-style map (UE),
    # so Y is flipped to the GL convention first. (Before 2026-10-18 nx / ny went in raw -> shading seams at every UV border.)
    x = fit(nx) * 2.0 - 1.0; y = -(fit(ny) * 2.0 - 1.0)
    c45 = np.cos(np.pi * 0.25)
    rx = (x + y) * c45; ry = (y - x) * c45                    # rotate by -45 deg
    g = np.sign(rx) * np.sqrt(np.abs(rx)); a = -np.sign(ry) * np.sqrt(np.abs(ry))
    nrro = np.dstack([fit(rough), np.clip((g + 1) * 0.5, 0, 1), fit(ao), np.clip((a + 1) * 0.5, 0, 1)])
    atos = None if alpha is None else np.dstack([fit(alpha), np.ones((s, s)), np.zeros((s, s)), np.ones((s, s))])
    return albd, nrro, atos


def std(d, orm, n):
    d = img(d); orm = img(orm); n = img(n)
    return pack(d, orm[..., 2], orm[..., 1], orm[..., 0], n[..., 0], n[..., 1])


SKIN_MATS = set()   # materials built by skin() (filled while writing textures)
SKIN_CALLS = []
# 2026-10-21: EVE_SKIN_PROFILE=common_v1 -> the common skin colour profile EVE_COMMON_SKIN_SOURCE_V1
# (checked against the original Stellar Blade): decode the unbaked SB A from sRGB, multiply the linear BaseTint
# once, encode back to sRGB. No lift, no saturation change, no EVE_SKIN_REF gain. Face and body both go through skin(),
# so one switch moves them together. Roughness is NOT part of the colour profile: EVE_SKIN_ROUGH_ADD stays a separate
# Wilds-adapter value (default 0.18 as before, recorded in the report). Default 'legacy' = the installed look, unchanged.
SKIN_PROFILE = os.environ.get('EVE_SKIN_PROFILE', 'legacy')
if SKIN_PROFILE not in ('legacy', 'common_v1'): raise SystemExit('EVE_SKIN_PROFILE must be legacy or common_v1')
TINT_LINEAR = np.array([0.921582, 0.679543, 0.693872], np.float32)   # = sRGB decode of F6D7D9 (SB cooked BaseTint R/G/B)
def srgb_decode(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def srgb_encode(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
report['skinProfile'] = {'profile': 'EVE_COMMON_SKIN_SOURCE_V1' if SKIN_PROFILE == 'common_v1' else 'legacy_sb_tint_lift',
                         'tint_linear': TINT_LINEAR.tolist() if SKIN_PROFILE == 'common_v1' else None,
                         'lift': 1.0 if SKIN_PROFILE == 'common_v1' else float(os.environ.get('EVE_SKIN_LIFT', '1.08')),
                         'skin_ref_gain': SKIN_PROFILE != 'common_v1' and bool(os.environ.get('EVE_SKIN_REF')),
                         'adapter_rough_add': float(os.environ.get('EVE_SKIN_ROUGH_ADD', '0.18'))}


def skin(d, n, orss):
    SKIN_CALLS.append(d)
    d = img(d); n = img(n); o = img(orss)
    lift = float(os.environ.get('EVE_SKIN_LIFT', '1.08'))   # approved look 10-18 (with BaseTint, SSS 1): default for every Eve outfit
    radd = float(os.environ.get('EVE_SKIN_ROUGH_ADD', '0.18'))   # Eve's skin read wet / oily under Wilds lighting
    if radd: o = o.copy(); o[..., 1] = np.clip(o[..., 1] + radd, 0, 1)
    if SKIN_PROFILE == 'common_v1':   # img() keeps the stored sRGB values (Non-Color), so decode exactly once here
        d = d.copy(); d[..., :3] = srgb_encode(srgb_decode(d[..., :3]) * TINT_LINEAR)
        return pack(d, 0.0, o[..., 1], o[..., 0], n[..., 0], n[..., 1])
    if os.environ.get('EVE_SKIN_TINT') == '1':
        tint = np.array([0xF6, 0xD7, 0xD9], np.float32) / 255.0
        lum = (d[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
        sat = lum + (d[..., :3] - lum) * float(os.environ.get('EVE_SKIN_SAT', '1.0'))                     # keep the rosy makeup / cheeks lively
        d = d.copy(); d[..., :3] = np.clip(sat * tint * lift, 0, 1)
        return pack(d, 0.0, o[..., 1], o[..., 0], n[..., 0], n[..., 1])
    if os.environ.get('EVE_SKIN_MODE', 'sb') == 'sb':
        # user 10-18: in game Eve's skin read pale grey with no pink. SB's skin materials (MA_Skin_EVE / MA_Skin_NPC) multiply
        # the base colour by BaseTint F6D7D9 (rosy) and add subsurface scattering; the old 'paler + brighter' step here (85 %
        # saturation, x1.08) removed exactly that pink. Now: SB's BaseTint, a little extra saturation, then the brightness
        # lift (the tint darkens green / blue by ~15 %).
        tint = np.array([0xF6, 0xD7, 0xD9], np.float32) / 255.0
        lum = (d[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
        sat = lum + (d[..., :3] - lum) * float(os.environ.get('EVE_SKIN_SAT', '1.0'))
        d = d.copy(); d[..., :3] = np.clip(sat * tint * lift, 0, 1)
    elif lift != 1.0:
        lum = (d[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
        d = d.copy(); d[..., :3] = np.clip((lum + (d[..., :3] - lum) * 0.85) * lift, 0, 1)   # a bit paler + brighter
    return pack(d, 0.0, o[..., 1], o[..., 0], n[..., 0], n[..., 1])


def flat(rgb_hex, rough=0.6, alpha=None, size=SIZE):
    c = srgb_hex(rgb_hex); s = size if alpha is not None else 64
    return pack(const(c, size=s), 0.0, rough, 1.0, 0.5, 0.5, alpha)


HEAD_TEX = os.environ.get('EVE_OUTFIT') not in ('27', '63', '41', '18', '34', 'auto') or 'PonyTail_Alpha' in png_index   # outfit-only builds may lack hair textures
hair_alpha = img('PonyTail_Alpha')[..., 0] if HEAD_TEX else None
brow = img('Tex_P_EVE_eyebrow_O') if HEAD_TEX and 'Tex_P_EVE_eyebrow_O' in png_index else None
# Same order as build_eve_default.py KEYS.
MATERIALS = {
    'MI_CH_P_EVE_08_Suit':     lambda: std('MI_CH_NPC_Lilly_01_Lower_2_A', 'MI_CH_NPC_Lilly_01_Lower_4_ORM', 'MI_CH_NPC_Lilly_01_Lower_2_N'),
    'MI_CH_P_EVE_08_Acc':      lambda: std('MI_CH_NPC_Lilly_01_Skin_2_A', 'MI_CH_NPC_Lilly_01_Skin_2_ORM', 'MI_CH_NPC_Lilly_01_Skin_2_N'),
    # glass-like vinyl (HDR reflection shader in the original); no translucency in this Wilds shader -> glossy dark
    'MI_EVE_Cos_08_Vinyl':     lambda: flat('15181C', 0.15),
    'MI_CH_P_EVE_BB_V01':      lambda: skin('CH_P_EVE_BaseBody_A', 'CH_P_EVE_BaseBody_N', 'CH_P_EVE_BB_V01_ORSS'),
    'MI_EVE_Head_V02_Jali':    lambda: skin('Tex_P_EVE_Head_A', 'Tex_P_EVE_Head_N', 'CH_P_EVE_Head_ORSS'),
    'MI_EyeRefractive1':       lambda: pack(img('S_EyeIrisBaseColor'), 0.0, 0.2, 1.0, 0.5, 0.5),
    'MI_Teeth':                lambda: flat('E8E2D8', 0.4),
    'MI_EyeBrow1':             lambda: flat('3A2A20', 0.8, alpha=brow[..., 0], size=brow.shape[0]),
    'MI_EVE_HR_01_TypeA':      lambda: flat('5D4D3D', 0.5, alpha=hair_alpha, size=hair_alpha.shape[0]),
    'MI_EVE_HR_01_Tail_TypeA': lambda: flat('5D4D3D', 0.5, alpha=hair_alpha, size=hair_alpha.shape[0]),
}
if os.environ.get('EVE_OUTFIT') == '09' or os.environ.get('EVE_AUTO_PRESET') == '09':
    def glossy(d, orm, n, rough_scale=1.0):
        d = img(d); orm = img(orm); n = img(n)
        rough_scale = rough_scale * float(os.environ.get('EVE_METAL_ROUGH', '1.0'))
        return pack(d, orm[..., 2], np.clip(orm[..., 1] * rough_scale, 0.04, 1.0), orm[..., 0], n[..., 0], n[..., 1])
    def lace():
        d = img('CH_P_EVE_09_Map04_D'); orm = img('CH_P_EVE_09_Map04_AORM'); n = img('CH_P_EVE_09_Map04_N')
        return pack(d, np.clip(orm[..., 3] if orm.shape[2] > 3 else orm[..., 2], 0, 1), orm[..., 2], 1.0, n[..., 0], n[..., 1], alpha=d[..., 3])
    def suit09():
        # The original suit gets its green sheen from a layered HDR reflection tinted green (HDRITint, HDR_Intensity 3.19)
        # that this Wilds shader cannot do. Approximate it from the DetailMask regions: pure green = glossy vinyl panels
        # (tinted green, low roughness, a little metal), cyan = matte fabric (slight green tint), red = white stripes (as is).
        d = img('CH_P_EVE_09_Map01_D'); orm = img('CH_P_EVE_09_Map01_ORM_02'); n = img('CH_P_EVE_09_Map01_N'); m = img('CH_P_EVE_09_Body_DetailMask')
        gain = float(os.environ.get('EVE_GREEN_GAIN', '1.0'))
        lum = (0.3 * d[..., 0] + 0.59 * d[..., 1] + 0.11 * d[..., 2])[..., None]
        vinyl = ((m[..., 1] > 0.5) & (m[..., 2] < 0.5) & (m[..., 0] < 0.5))[..., None]
        fabric = ((m[..., 1] > 0.5) & (m[..., 2] > 0.5))[..., None]
        alb = d[..., :3].copy()
        alb = np.where(vinyl, np.clip(lum * np.array([0.42, 1.30, 0.55]) * gain, 0, 1), alb)
        alb = np.where(fabric, np.clip(lum * np.array([0.72, 1.02, 0.82]), 0, 1), alb)
        out = d.copy(); out[..., :3] = alb
        rough = np.where(vinyl[..., 0], float(os.environ.get('EVE_VINYL_ROUGH', '0.12')), np.where(fabric[..., 0], orm[..., 1] * float(os.environ.get('EVE_FABRIC_ROUGH', '0.8')), orm[..., 1]))
        # metal tints the reflection with the green albedo (stand-in for the original's green HDRI reflection)
        metal = np.where(vinyl[..., 0], float(os.environ.get('EVE_VINYL_METAL', '0.35')), orm[..., 2])
        report['suitRegions'] = {'vinyl': float(vinyl.mean()), 'fabric': float(fabric.mean())}
        return pack(out, metal, rough, orm[..., 0], n[..., 0], n[..., 1])
    def metal01():
        # shoulder / chest devices: the original lights the green marks (teardrop lines, cross, ring, LEDs) through
        # Map02_Mask01 red channel (ML_GlowEmissive_CH = R, ML_GlowEm_Mult 5.4) -> emissive map = albedo x mask
        out = glossy('CH_P_EVE_09_Map02_D', 'CH_P_EVE_09_Map02_ORM', 'CH_P_EVE_09_Map02_N')
        if os.environ.get('EVE_DECO_GLOW') == '1':
            d = img('CH_P_EVE_09_Map02_D'); m = img('CH_P_EVE_09_Map02_Mask01')[..., 0:1]
            glow = np.clip(d[..., :3] * 1.4, 0, 1) * m
            EMISSIVE['MI_P_EVE_09_Metal01_Layered'] = np.dstack([glow, np.ones(m.shape[:2])]).astype(np.float32)
            report['metal01Glow'] = float(m.mean())
        return out
    def metal02():
        out = glossy('CH_P_EVE_09_Map03_D', 'CH_P_EVE_09_Map03_ORM', 'CH_P_EVE_09_Map03_N')
        if os.environ.get('EVE_DECO_GLOW') == '1' and 'CH_P_EVE_09_Map03_E' in png_index:
            e = img('CH_P_EVE_09_Map03_E')
            EMISSIVE['MI_P_EVE_09_Metal02_Layered'] = np.dstack([e[..., :3], np.ones(e.shape[:2])]).astype(np.float32)
            report['metal02Glow'] = float(e[..., :3].mean())
        return out
    def plastic09():
        d = img('CH_P_EVE_09_Map02_D'); n = img('CH_P_EVE_09_Map02_N'); s_ = d.shape[0]
        tint = np.array([0.42, 0.36, 0.52], np.float32)
        lum = (d[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
        out = d.copy(); out[..., :3] = np.clip(tint * (0.55 + 0.9 * lum), 0, 1)
        if os.environ.get('EVE_CAPE_VEIL') == '1':
            # real translucency (veil shader DU_Equip_RoughTransparent): pale cyan glass like the original panel
            cyan = np.array([float(x) for x in os.environ.get('EVE_CAPE_RGB', '0.62,0.80,0.98').split(',')], np.float32)
            out[..., :3] = np.clip(cyan * (0.75 + 0.35 * lum), 0, 1)
            if os.environ.get('EVE_CAPE_PATTERN') == '1':
                # Colour 435853 + Outer Colour 606EC9 (rim), Pattern (dark marks on white) glowing in Pattern Colour 11FFCF
                pat = img('CH_P_EVE_09_Pattern')
                if pat.shape[0] != s_: ys = np.arange(s_) * pat.shape[0] // s_; pat = pat[ys][:, ys]
                mark = (np.clip(1.0 - (pat[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)), 0, 1) * (pat[..., 3] if pat.shape[-1] > 3 else 1.0))[..., None]   # transparent background
                base = np.array([0x43, 0x58, 0x53], np.float32) / 255 * 0.55 + np.array([0x60, 0x6E, 0xC9], np.float32) / 255 * 0.45
                glow = np.array([0x11, 0xFF, 0xCF], np.float32) / 255
                out[..., :3] = np.clip(base * (0.8 + 0.4 * lum) * (1 - mark) + glow * mark, 0, 1)
                EMISSIVE['MA_Plastic_2_Inst'] = np.dstack([glow * mark, np.ones((s_, s_))]).astype(np.float32)
            if os.environ.get('EVE_CAPE_TILED') == '1':
                # 10-19: the SB veil's sparkle pattern is CH_P_EVE_09_Pattern TILED over the UVs ('UV X (S)' 31.35,
                # 'UV Y (S)' -22.28, Pattern Power 20, emissive 11FFCF) on a dark 435853 / 606EC9 glass; Opacity Top 0.3 ->
                # Bottom 1.0. The panel's UVs cover a plain part of Map02, so the untiled bake showed nothing.
                pat = img('CH_P_EVE_09_Pattern'); ph, pw = pat.shape[:2]
                yy, xx = np.mgrid[0:s_, 0:s_].astype(np.float32) / s_
                py_ = ((yy * 22.28181) % 1.0 * ph).astype(np.int32) % ph; px_ = ((xx * 31.35453) % 1.0 * pw).astype(np.int32) % pw
                tp = pat[py_, px_]
                mark = np.clip(1.0 - (tp[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)), 0, 1) * (tp[..., 3] if tp.shape[-1] > 3 else 1.0)
                mark = np.clip(mark * float(os.environ.get('EVE_CAPE_SPARK', '1.6')), 0, 1)[..., None]
                # user 10-19: the original reads dark (near-black green glass, green / blue sheen), not pale blue
                base = np.array([0x43, 0x58, 0x53], np.float32) / 255 * 0.35 + np.array([0x60, 0x6E, 0xC9], np.float32) / 255 * 0.08
                glow = np.array([0x11, 0xFF, 0xCF], np.float32) / 255 * 0.7 + np.array([0x00, 0xFF, 0x8A], np.float32) / 255 * 0.3
                yy2 = np.mgrid[0:s_, 0:s_][0].astype(np.float32) / s_
                sheen = np.array([0x60, 0x6E, 0xC9], np.float32) / 255 * 0.25 * (0.5 + 0.5 * np.sin(yy2 * 18.0 + xx * 9.0))[..., None]
                out[..., :3] = np.clip((base + sheen * 0.4) * (1 - mark) + glow * mark, 0, 1)
                EMISSIVE['MA_Plastic_2_Inst'] = np.dstack([glow * mark[..., 0:1].repeat(1, 2) if False else glow * mark, np.ones((s_, s_))]).astype(np.float32)
                a_ = float(os.environ.get('EVE_CAPE_ALPHA', '0.6'))
                report['capeTiled'] = float(mark.mean())
                return pack(out, 0.55, 0.04, 1.0, n[..., 0], n[..., 1], alpha=np.clip(a_ + 0.35 * mark[..., 0], 0, 0.95).astype(np.float32))   # glossier glass (10-20)
            if os.environ.get('EVE_CAPE_DETAIL') == '1':
                # user 10-19 (SB check): the original panel shows the Map02 machine detail (rings, circuits) dark-teal with
                # green / blue sheen and glowing marks (Map02_E, scratch pattern Map04_mask); ours was a flat pale glass.
                # Detail contrast from the albedo luminance drives colour, sheen and opacity.
                c_ = np.clip((lum[..., 0] - 0.30) * 2.4, 0, 1)[..., None]
                dark = np.array([0x2c, 0x4a, 0x50], np.float32) / 255   # 10-19: darker one vanished on the green suit
                sheen = np.array([0x11, 0xFF, 0xCF], np.float32) / 255 * 0.45 + np.array([0x60, 0x6E, 0xC9], np.float32) / 255 * 0.55
                out[..., :3] = np.clip(dark * (1 - c_) + sheen * c_, 0, 1)
                emi = np.zeros((s_, s_, 3), np.float32)
                for nm_, k_ in (('CH_P_EVE_09_Map02_E', 1.0), ('CH_P_EVE_09_Map04_mask', 0.35)):
                    if nm_ in png_index:
                        e_ = img(nm_)
                        if e_.shape[0] != s_: ys = np.arange(s_) * e_.shape[0] // s_; e_ = e_[ys][:, ys]
                        g_ = e_[..., :3] if nm_.endswith('_E') else (e_[..., 0:1] * np.array([0x11, 0xFF, 0xCF], np.float32) / 255)
                        emi = emi + g_ * k_
                old = EMISSIVE.get('MA_Plastic_2_Inst')
                if old is not None: emi = emi + old[..., :3]
                EMISSIVE['MA_Plastic_2_Inst'] = np.dstack([np.clip(emi, 0, 1), np.ones((s_, s_))]).astype(np.float32)
                a_ = float(os.environ.get('EVE_CAPE_ALPHA', '0.45'))
                report['capeDetail'] = float(c_.mean())
                return pack(out, 0.35, 0.08, 1.0, n[..., 0], n[..., 1], alpha=np.clip(a_ + 0.35 * c_[..., 0], 0, 0.92).astype(np.float32))
            return pack(out, 0.1, 0.05, 1.0, n[..., 0], n[..., 1], alpha=np.full((s_, s_), float(os.environ.get('EVE_CAPE_ALPHA', '0.45')), np.float32))
        yy, xx = np.mgrid[0:s_, 0:s_]
        dither = (((xx // 2) + (yy // 2)) % 2).astype(np.float32)          # 50 % screen door (2x2 checker)
        dither = np.maximum(dither, 0.0)
        return pack(out, 0.2, 0.08, 1.0, n[..., 0], n[..., 1], alpha=dither)
    head = {k: MATERIALS[k] for k in list(MATERIALS)[4:]}
    MATERIALS = {
        'MI_CH_P_EVE_09_Suit':         suit09,
        'MI_P_EVE_09_Metal01_Layered': metal01,
        'MI_P_EVE_09_Metal02_Layered': metal02,
        'MI_P_EVE_09_Skin':            lambda: skin('CH_P_EVE_09_Skin_D_noline' if 'CH_P_EVE_09_Skin_D_noline' in png_index else 'CH_P_EVE_09_Skin_D', 'CH_P_EVE_09_Skin_N_noline' if 'CH_P_EVE_09_Skin_N_noline' in png_index else 'CH_P_EVE_09_Skin_N', 'CH_P_EVE_BB_V01_ORSS'),
        'MA_Plastic_2_Inst':           plastic09,
        'MI_P_EVE_09_lace':            lace,
    }
    MATERIALS.update(head)
# Eye: the original refractive eye shader composites sclera (T_EyeScleraBaseColor x ScleraBrightness 1.6) and the iris
# (S_EyeIrisBaseColor) inside 'Iris UV Radius' 0.145 around the UV centre, with a darker limbus (width 0.045).
# Using the iris texture over the whole eyeball made the eyes look black.
def eye():
    s = 1024
    scl = img('T_EyeScleraBaseColor', s)[..., :3]; iris = img('S_EyeIrisBaseColor', s)[..., :3]
    u = (np.arange(s) + 0.5) / s; U, V = np.meshgrid(u, u)
    r = np.sqrt((U - 0.5) ** 2 + (V - 0.5) ** 2); R = float(os.environ.get('EVE_IRIS_R', '0.145'))
    iu = np.clip(((U - 0.5) / (2 * R) + 0.5) * (s - 1), 0, s - 1).astype(int); iv = np.clip(((V - 0.5) / (2 * R) + 0.5) * (s - 1), 0, s - 1).astype(int)
    irs = iris[iv, iu] * float(os.environ.get('EVE_IRIS_GAIN', '1.45'))
    if os.environ.get('EVE_IRIS_TINT') == '1': irs = irs * (np.array([0xD4, 0xCB, 0xFF], np.float32) / 255)   # IrisHueTint
    sc = np.clip(scl * float(os.environ.get('EVE_SCLERA', '1.6')), 0, 1)
    shade = float(os.environ.get('EVE_SCLERA_SHADE', '0'))   # darker towards the lids (stand-in for the eye-shadow occlusion overlay)
    if shade: x_ = np.clip((r - 0.18) / 0.3, 0, 1)[..., None]; sc = sc * (1 - shade * x_ * x_ * (3 - 2 * x_))
    t = np.clip((r - (R - 0.02)) / 0.03, 0, 1)[..., None]           # iris -> sclera
    limb = 1 - float(os.environ.get('EVE_LIMBUS', '0.45')) * np.exp(-((r - R) / 0.018) ** 2)[..., None]   # limbus (original: 0)
    alb = np.clip((irs * (1 - t) + sc * t) * limb, 0, 1)
    for cx, cy, rr, k in ((0.47, 0.545, 0.022, 0.95), (0.53, 0.47, 0.009, 0.7)):   # catchlights (the original eye shader reflects an HDRI)
        g = np.exp(-(((U - cx) ** 2 + (V - cy) ** 2) / (rr * rr)))[..., None] * k
        alb = alb * (1 - g) + g
    out = np.dstack([alb, np.ones((s, s))]).astype(np.float32)
    return pack(out, 0.0, 0.08, 1.0, 0.5, 0.5)
MATERIALS['MI_EyeRefractive1'] = eye
# EVE_OUTFIT=auto + EVE_TEX_JSON: material list written by make_eve_auto.py, in build_eve_outfit.py key order:
# [[material, kind, base, orm_or_orss, normal, stocking_mask_or_null, flat_hex], ...]; kind = std | skin | flat
if os.environ.get('EVE_OUTFIT') == 'auto':
    def _fx(res, fx):
        # SB layer effects baked into the albedo: fuzz sheen tint (mask channel x colour), thin-film iridescence (pastel
        # rainbow by UV position), stocking layer (sheer ~30 denier tint), base colour tint
        if not fx or res is None: return res
        albd, nrro, atos = res; albd = albd.copy(); s_ = albd.shape[0]
        lum = np.clip((albd[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None], 0, 1)
        def mask(name, ch):
            if name not in png_index: return None
            return img(name, s_)[..., ch]
        for name, ch, hexc, inten in fx.get('fuzz', []):
            m = mask(name, ch)
            if m is None: continue
            c = np.array(srgb_hex(hexc), np.float32)
            w = np.clip(m * min(1.0, 0.25 + 0.6 * inten), 0, 1)[..., None]
            albd[..., :3] = albd[..., :3] * (1 - w) + np.clip(c * (0.45 + 0.75 * lum), 0, 1) * w
        # thin film by UV position gave each UV island its own colour -> green patches on Blossom's skirt (user 10-20): off
        if fx.get('film') and os.environ.get('EVE_FILM', '0') == '1':
            name, ch, inten = fx['film']; m = mask(name, ch)
            if m is not None:
                yy, xx = np.mgrid[0:s_, 0:s_].astype(np.float32) / s_
                ph = (xx * 3.0 + yy * 2.0 + lum[..., 0] * 1.5) * 2 * np.pi
                rain = np.dstack([0.5 + 0.5 * np.cos(ph), 0.5 + 0.5 * np.cos(ph - 2.1), 0.5 + 0.5 * np.cos(ph - 4.2)])
                pastel = 0.6 + 0.4 * rain
                w = np.clip(m * 0.55 * min(1.0, inten), 0, 1)[..., None]
                albd[..., :3] = albd[..., :3] * (1 - w) + albd[..., :3] * pastel * 1.08 * w
        if fx.get('stocking'):
            name, ch, hexc = fx['stocking']; m = mask(name, ch)
            if m is not None:
                c = np.array(srgb_hex(hexc), np.float32)
                _sh = float(os.environ.get('EVE_STK_SHEER', '0.30'))   # share of what is under the stocking showing through
                stk_c = albd[..., :3] * _sh + c * (1 - _sh)   # the stocking colour itself (Blossom white lace was turned grey, user 10-19)
                albd[..., :3] = albd[..., :3] * (1 - m[..., None]) + stk_c * m[..., None]
                nrro = nrro.copy(); nrro[..., 0] = nrro[..., 0] * (1 - m) + np.maximum(nrro[..., 0], 0.72) * m
        if fx.get('pattern'):
            name, ch, hexc, inten = fx['pattern']; m = mask(name, ch)
            if m is not None:
                c = np.array(srgb_hex(hexc), np.float32); w = np.clip(m * inten, 0, 1)[..., None]
                albd[..., :3] = albd[..., :3] * (1 - w) + np.clip(c * (0.7 + 0.9 * lum), 0, 1) * w
        if fx.get('tint'):
            albd[..., :3] = albd[..., :3] * np.array(srgb_hex(fx['tint']), np.float32)   # SB Base Color Tint multiplies
        report.setdefault('layerFx', []).append(list(fx))
        return np.clip(albd, 0, 1).astype(np.float32), nrro, atos
    def _auto(spec):
        mat, kind, a_, o_, n_, stk, hexc = spec[:7]; fx = spec[7] if len(spec) > 7 else {}
        def f():
            return _skinref(_fx(_f(), fx))
        def _skinref(res):
            # user 10-19: Eve's skin tone differed from outfit to outfit (every SB costume carries its own body texture);
            # EVE_SKIN_REF = Diver's (Blue Monsoon) mean skin colour -> per-channel gain so every outfit's skin matches it
            ref = os.environ.get('EVE_SKIN_REF')
            if kind == 'skin' and SKIN_PROFILE == 'common_v1':   # whole-map mean gain is excluded from the common profile (S22: 1.24)
                if fx.get('tint') or fx.get('albedoMul'): report.setdefault('skinProfileWarn', []).append(f'{mat}: colour fx on a skin material')
                return res
            if kind != 'skin' or not ref or res is None: return res
            albd = res[0].copy(); rgb = albd[..., :3].reshape(-1, 3)
            lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32); ok = (lum > 0.15) & (lum < 0.95)
            if stk and stk in png_index:   # Moran: the dark stocking area pulled the mean down -> over-bright, orange skin (10-19)
                ok &= img(stk, albd.shape[0])[..., 0].reshape(-1) < 0.1
            sel = rgb[ok]
            if len(sel) < 100: return res
            gain = np.array([float(x) for x in ref.split(',')], np.float32) / np.maximum(sel.mean(0), 1e-3)
            albd[..., :3] = np.clip(albd[..., :3] * gain, 0, 1)
            report.setdefault('skinGain', {})[mat] = [round(float(g), 3) for g in gain]
            return (albd,) + tuple(res[1:])
        def _f():
            return _outfit_fx(_f0())
        def _outfit_fx(res):
            # 2026-10-21: per-material effects the generic path dropped. All optional, set per outfit in
            # data/repro/<row>.tex_overrides.json (fx keys): alphaClip / veil / emissive / roughSet / roughMul / metalSet / albedoMul.
            if res is None or not fx: return res
            albd, nrro, atos = res
            s_ = albd.shape[0]
            def chan(name, ch, size):
                if not name or name not in png_index: return None
                return img(name, size)[..., ch]
            if fx.get('alphaClip'):
                name, ch = fx['alphaClip'][:2]; m = chan(name, ch, s_)
                if m is not None:
                    thr = float(fx['alphaClip'][2]) if len(fx['alphaClip']) > 2 else 0.0
                    if thr: m = (m >= thr).astype(np.float32)
                    atos = np.dstack([m, np.ones((s_, s_)), np.zeros((s_, s_)), np.ones((s_, s_))]).astype(np.float32)
                    report.setdefault('alphaClip', {})[mat] = round(float((m < 0.5).mean()), 3)
            if fx.get('veil'):
                v = fx['veil']; VEIL_MATS[mat] = v
                if albd.shape[0] < 256:
                    albd = np.ones((256, 256, 4), np.float32) * albd[0, 0]; nrro = np.ones((256, 256, 4), np.float32) * nrro[0, 0]; s_ = 256
                if v.get('hex') and not v.get('keepAlbedo'): albd = albd.copy(); albd[..., :3] = srgb_hex(v['hex'])
                if v.get('albedoMul'): albd = albd.copy(); albd[..., :3] = np.clip(albd[..., :3] * np.array(srgb_hex(v['albedoMul']), np.float32), 0, 1)
                op = np.full((s_, s_), float(v.get('alpha', 0.5)), np.float32)
                if v.get('alphaTex'):   # translucent SB material with a texture: its alpha is opacity (lace on a sheer skirt)
                    m = chan(v['alphaTex'][0], int(v['alphaTex'][1]), s_)
                    if m is not None: op = np.clip(float(v.get('alpha', 0.35)) + m * float(v['alphaTex'][2] if len(v['alphaTex']) > 2 else 0.6), 0, 0.97).astype(np.float32)
                atos = np.dstack([op, np.ones((s_, s_)), np.zeros((s_, s_)), np.ones((s_, s_))]).astype(np.float32)
            if fx.get('royalSilk'):
                # SB ML_RoyalSilk (Moran): inside the mask the cloth is silk in SilkTint with a tiled jacquard pattern
                # (ML_RS_Pattern x PatternTiling, PatternTint, PatternIntensity); the cloth texture keeps its shading
                mname, mch, silk, pname, ptint, tiling, inten = fx['royalSilk']
                m = chan(mname, int(mch), s_)
                if m is not None and pname in png_index:
                    pat = img(pname); ph, pw = pat.shape[:2]
                    yy, xx = np.mgrid[0:s_, 0:s_].astype(np.float32) / s_
                    tp = pat[((yy * float(tiling)) % 1.0 * ph).astype(np.int32) % ph, ((xx * float(tiling)) % 1.0 * pw).astype(np.int32) % pw]
                    plum = np.clip(tp[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32), 0, 1)[..., None]
                    lum = np.clip((albd[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None], 0, 1)
                    shade = np.clip(lum / max(1e-3, float(np.median(lum))), 0.4, 1.6)   # keep the folds' light / dark from the texture
                    silk_c = np.array(srgb_hex(silk), np.float32) * 0.92 * shade
                    pat_c = np.array(srgb_hex(ptint), np.float32) * 0.85 * shade
                    k = np.clip(plum * float(inten), 0, 1)
                    newc = np.clip(silk_c * (1 - k) + pat_c * k, 0, 1)
                    outside = albd[..., :3]
                    if fx.get('tintOutside'):   # SB Base Color Tint acts on the non-silk part (Moran's dragon art reads gold)
                        outside = np.clip(outside * np.array(srgb_hex(fx['tintOutside']), np.float32) * float(fx.get('tintGain', 1.0)), 0, 1)
                    albd = albd.copy(); albd[..., :3] = outside * (1 - m[..., None]) + newc * m[..., None]
                    report.setdefault('royalSilk', {})[mat] = round(float(m.mean()), 3)
            if fx.get('albedoMul'):
                albd = albd.copy(); albd[..., :3] = np.clip(albd[..., :3] * np.array(srgb_hex(fx['albedoMul']), np.float32) / 0.5, 0, 1)
            if 'roughSet' in fx or 'roughMul' in fx:
                nrro = nrro.copy()
                if 'roughSet' in fx: nrro[..., 0] = float(fx['roughSet'])
                if 'roughMul' in fx: nrro[..., 0] = np.clip(nrro[..., 0] * float(fx['roughMul']), 0.02, 1)
            if 'metalSet' in fx:
                albd = albd.copy(); albd[..., 3] = 1.0 - float(fx['metalSet'])
            if fx.get('emissive'):
                e = fx['emissive']; s2 = max(s_, 256)
                col = np.array(srgb_hex(e.get('hex', 'FFFFFF')), np.float32)
                m = chan(e.get('tex'), int(e.get('ch', 0)), s2) if e.get('tex') else np.ones((s2, s2), np.float32)
                if m is None: m = np.ones((s2, s2), np.float32)
                if e.get('thr'): m = np.clip((m - float(e['thr'])) / max(1e-3, 1 - float(e['thr'])), 0, 1)
                if e.get('rgb') and e.get('tex') in png_index:   # SB *_E map: its own colours, normalised to its brightest texel
                    t_ = img(e['tex'], s2)[..., :3]; mx = float(np.percentile(t_.max(-1), 99.9)) or 1.0
                    base_ = np.clip(t_ / max(mx, 1e-3), 0, 1); m = np.ones((s2, s2), np.float32)
                elif e.get('albedo') and albd.shape[0] == s2:
                    base_ = albd[..., :3]
                else:
                    base_ = np.ones((s2, s2, 3), np.float32)
                EMISSIVE[mat] = np.dstack([np.clip(base_ * col * m[..., None], 0, 1), np.ones((s2, s2))]).astype(np.float32)
                EMIT_POWER[mat] = float(e.get('power', os.environ.get('EVE_DECO_EMIT', '4')))
                report.setdefault('emissive', {})[mat] = round(float(m.mean()), 4)
            return albd, nrro, atos
        def _f0():
            if kind == 'flat' or not a_ or a_ not in png_index: return flat(hexc or '808080', float(fx.get('flatRough', 0.55)) if fx else 0.55)
            if kind == 'skin':
                albd, nrro, atos = skin(a_, n_ if n_ in png_index else 'CH_EVE_BaseBody_V02_F2_N', o_ if o_ in png_index else 'CH_EVE_BaseBody_V02_F1_ORSS')
                if stk and stk in png_index:      # SB stocking layer baked as sheer ~30 denier black (as Moran, user 10-18)
                    m = img(stk, albd.shape[0])[..., int((fx or {}).get('stkCh', 0))]
                    lum = np.clip((albd[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None], 0, 1)
                    # stocking colour / sheer share per outfit (white Santa stocking, darker black sheers); default as before
                    sh_ = float((fx or {}).get('stkSheer', 0.30))
                    sc_ = np.array(srgb_hex((fx or {}).get('stkColor', '090808')), np.float32) if (fx or {}).get('stkColor') else np.array([0.035, 0.033, 0.035], np.float32)
                    skin_even = np.array([0.80, 0.62, 0.55], np.float32) * (0.55 + 0.45 * lum)
                    if (fx or {}).get('stkKeepShade'):   # keep the skin's own light/dark (knee, shin highlights) under the sheer
                        skin_even = albd[..., :3]
                    stk_c = skin_even * sh_ + sc_ * (1 - sh_)
                    albd = albd.copy(); albd[..., :3] = albd[..., :3] * (1.0 - m)[..., None] + stk_c * m[..., None]
                    nrro = nrro.copy(); nrro[..., 0] = nrro[..., 0] * (1.0 - m) + np.maximum(nrro[..., 0], float((fx or {}).get('stkRough', 0.72))) * m
                    report.setdefault('skinStocking', {})[mat] = [round(float(m.mean()), 3), sh_]
                return albd, nrro, atos
            orm = o_ if o_ in png_index else None; nn = n_ if n_ in png_index else None
            if orm and nn: return std(a_, orm, nn)
            d = img(a_); return pack(d, 0.0, 0.6, 1.0, 0.5, 0.5)
        return f
    # EVE_AUTO_PRESET: reuse a hand-tuned material set (e.g. 09 = Planet Dive Suit: vinyl sheen, veil cape, glow) where it has the key
    _pre = MATERIALS if os.environ.get('EVE_AUTO_PRESET') else {}
    MATERIALS = {sp[0]: (_pre.get(sp[0]) or _auto(sp)) for sp in json.load(open(os.environ['EVE_TEX_JSON'], encoding='utf-8'))}
    MATERIALS['MI_EVE_HR_01_Tail_TypeA'] = lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                                    else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0]))
    MATERIALS['CH_W_Sword_02_Blade_Body'] = lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N')
# EVE_OUTFIT=27: Ocean Maid (CH_P_EVE_27) as the innerwear body part -- outfit materials only (no head / hair in this mesh)
if os.environ.get('EVE_OUTFIT') == '27':
    MATERIALS = {
        'MI_EVE_Cos_27_BB_02': lambda: skin('EVE_COS_27_BB_A_02', 'EVE_COS_27_BB_N_02', 'EVE_COS_27_BB_ORSS'),
        'MI_EVE_Cos_27_01':    lambda: std('EVE_COS_27_UV01_A', 'EVE_COS_27_UV01_ORM', 'EVE_COS_27_UV01_N'),
        'MI_EVE_Cos_27_02':    lambda: std('EVE_COS_27_UV02_A', 'EVE_COS_27_UV02_ORM', 'EVE_COS_27_UV02_N'),
        'MI_EVE_Cos_27_03':    lambda: std('EVE_COS_27_UV03_A', 'EVE_COS_27_UV03_ORM', 'EVE_COS_27_UV03_N'),
        # MA_MachineGlow (no textures, 'Eye Core HDR Tint' 51FFFF): glowing cyan parts
        'MI_EVE_Cos_27_Glow':  lambda: flat('51FFFF', 0.2),
        # the ponytail lives in the body part (physics chains in its chain2)
        'MI_EVE_HR_01_Tail_TypeA': lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                            else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])),
        # folded-sword hair ornament (build_eve_outfit.py): D / M (R AO, G rough, B metal) / N
        'CH_W_Sword_02_Blade_Body': lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N'),
    }
# EVE_OUTFIT=63: Wave Diver Bikini (CH_P_EVE_63) on outfit beta type 1 -- body skin, suit, CH_P_EVE_43 parts, ponytail, ornament
if os.environ.get('EVE_OUTFIT') == '63':
    MATERIALS = {
        'MI_Basebody_V02_F1':  lambda: skin('CH_EVE_BaseBody_V02_F1_A', 'CH_EVE_BaseBody_V02_F1_N', 'CH_EVE_BaseBody_V02_F1_ORSS'),
        'MI_CH_P_EVE_63_Suit': lambda: std('CH_P_EVE_63_A', 'CH_P_EVE_63_ORM', 'CH_P_EVE_63_N'),
        'MI_CH_P_EVE_43':      lambda: std('CH_P_EVE_43_A', 'CH_P_EVE_43_ORM', 'CH_P_EVE_43_N'),
        'MI_EVE_HR_01_Tail_TypeA': lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                            else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])),
        'CH_W_Sword_02_Blade_Body': lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N'),
    }
# EVE_OUTFIT=41: Racer's High (CH_P_EVE_41) on Mizutsune beta, split by part -- same material order as build_eve_outfit.py
# OUTFITS['41'] keys; one mdf per part (EVE_MDF_SKIP drops the materials that part's mesh does not use)
if os.environ.get('EVE_OUTFIT') == '41':
    def _emis41():
        a_ = flat('FFED00', 0.4)
        EMISSIVE['MI_CH_P_EVE_41_Emissive'] = np.dstack([np.ones((SIZE, SIZE, 3), np.float32) * np.array([1.0, 0.93, 0.0], np.float32), np.ones((SIZE, SIZE))]).astype(np.float32)
        return a_
    MATERIALS = {
        'MI_CH_P_EVE_41_Upper':    lambda: std('CH_P_EVE_41_Upper_A', 'CH_P_EVE_41_Upper_ORM', 'CH_P_EVE_41_Upper_N'),
        'MI_CH_P_EVE_41_Lower':    lambda: std('CH_P_EVE_41_Lower_A', 'CH_P_EVE_41_Lower_ORM', 'CH_P_EVE_41_Lower_N'),
        'MI_Basebody_V02_F2':      lambda: skin('CH_EVE_BaseBody_V02_F2_A', 'CH_EVE_BaseBody_V02_F2_N', 'CH_EVE_BaseBody_V02_F1_ORSS'),
        'MI_CH_P_EVE_41_Emissive': _emis41,
        'MI_EVE_HR_01_Tail_TypeA': lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                            else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])),
        'CH_W_Sword_02_Blade_Body': lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N'),
    }
# EVE_OUTFIT=18: Daily Mascot (CH_P_EVE_18) on Rey Dau gamma, split by part -- order = build_eve_outfit.py OUTFITS['18'] keys
if os.environ.get('EVE_OUTFIT') == '18':
    MATERIALS = {
        'MI_Basebody_V02_F3': lambda: skin('CH_EVE_BaseBody_V02_F2_A', 'CH_EVE_BaseBody_V02_F2_N', 'CH_EVE_BaseBody_V02_F1_ORSS'),
        'MI_EVE_Cos_18_01':   lambda: std('EVE_Cos_18_01_A', 'EVE_Cos_18_01_ORM', 'EVE_Cos_18_01_N'),
        'MI_EVE_Cos_18_02':   lambda: std('EVE_Cos_18_02_A', 'EVE_Cos_18_02_ORM', 'EVE_Cos_18_02_N'),
        'MI_EVE_HR_01_Tail_TypeA': lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                            else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])),
        'CH_W_Sword_02_Blade_Body': lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N'),
    }
# EVE_OUTFIT=34: Moran with stockings (CH_P_EVE_34_body) on Nu Udra gamma -- order = build_eve_outfit.py OUTFITS['34'] keys
if os.environ.get('EVE_OUTFIT') == '34':
    # SB draws Moran's black stockings as a layer on the body skin (Use_ML_Stocking, MASK_Stocking = CH_P_EVE_34_BB_StkMask,
    # stocking tint 7F7F7E over a darkened skin) -- the plain skin read as bare legs in game (user 10-18). Bake it: under the
    # mask the skin is darkened to a sheer black (EVE_STK_DARK) and made a bit rougher.
    def _stk_skin():
        albd, nrro, atos = skin('CH_P_EVE_29_BB_Addd', 'CH_P_EVE_29_BB_N', 'CH_EVE_BaseBody_V02_F1_ORSS')
        m = img('CH_P_EVE_34_BB_StkMask', albd.shape[0])[..., 0]
        k = float(os.environ.get('EVE_STK_DARK', '0.74'))
        # user 10-18: the painted panties showed through as a pale patch -> under the mask a plain sheer black (a little
        # of the skin's shading only), no painted underwear
        # user 10-18 (2nd): solid black read as leggings -> sheer ~30 denier: the skin tone still shows through (darkened,
        # cooler), painted underwear evened out by using the skin's brightness only, and a matte finish (rough 0.72)
        lum = np.clip((albd[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))[..., None], 0, 1)
        skin_even = np.array([0.80, 0.62, 0.55], np.float32) * (0.55 + 0.45 * lum)
        sheer = float(os.environ.get('EVE_STK_SHEER', '0.30'))          # share of the skin showing through
        stk = skin_even * sheer + np.array([0.035, 0.033, 0.035], np.float32) * (1 - sheer)
        albd = albd.copy(); albd[..., :3] = albd[..., :3] * (1.0 - m)[..., None] + stk * m[..., None]
        nrro = nrro.copy(); nrro[..., 0] = nrro[..., 0] * (1.0 - m) + np.maximum(nrro[..., 0], 0.72) * m
        report['stockingMask'] = round(float(m.mean()), 3)
        return albd, nrro, atos
    MATERIALS = {
        'MI_CH_P_EVE_34_BB':   _stk_skin,
        'MI_CH_P_EVE_34_Suit': lambda: std('CH_P_EVE_34_Cloth_A', 'CH_P_EVE_34_Cloth_ORM', 'CH_P_EVE_34_Cloth_N'),
        'MI_CH_P_EVE_34_ACC':  lambda: flat('F2F2F2', 0.5),
        'MI_EVE_HR_01_Tail_TypeA': lambda: (hair_strands() if os.environ.get('EVE_HAIR_STRANDS') == '1'
                                            else flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])),
        'CH_W_Sword_02_Blade_Body': lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N'),
    }
# Hair: the original Eve hair is near-black (the old flat brown read as blonde in Wilds sunlight).
HAIR_HEX = os.environ.get('EVE_HAIR_HEX', '43352B')   # darker: SB Eve hair is near-black brown (5D4D3D read light ash brown in game, user 10-18)
# Strand look of the original MA_CH_Hair: root->tip colour (PonyTail_Root), per-strand brightness (PonyTail_ID) and
# strand depth (PonyTail_Height, also turned into a normal map) -- a flat colour made the ponytail read as one block.
def hair_strands():
    s_ = hair_alpha.shape[0]
    def ch(n):
        x = img(n)[..., 0]
        if x.shape[0] != s_: ys = np.arange(s_) * x.shape[0] // s_; x = x[ys][:, ys]
        return x.astype(np.float32)
    root, sid, hgt = ch('PonyTail_Root'), ch('PonyTail_ID'), ch('PonyTail_Height')
    base = srgb_hex(HAIR_HEX)[:3]; tip = np.clip(np.array(base) * np.array([1.45, 1.25, 1.1]), 0, 1)
    t = (1 - root)[..., None]
    col = np.array(base)[None, None] * (1 - t) + tip[None, None] * t
    col = col * (0.72 + 0.56 * sid[..., None]) * (0.8 + 0.3 * hgt[..., None])
    gy, gx = np.gradient(hgt * 6.0)
    nx = np.clip(0.5 - gx, 0, 1); ny = np.clip(0.5 - gy, 0, 1)
    out = np.dstack([np.clip(col, 0, 1), np.ones((s_, s_))]).astype(np.float32)
    rough = np.clip(0.34 + 0.12 * (1 - sid), 0, 1)
    return pack(out, 0.0, rough, np.clip(0.55 + 0.45 * hgt, 0, 1), nx, ny, alpha=hair_alpha)
for _k in (('MI_EVE_HR_01_TypeA', 'MI_EVE_HR_01_Tail_TypeA') if os.environ.get('EVE_OUTFIT') not in ('27', '63', '41', '18', '34', 'auto') else ()):
    MATERIALS[_k] = (hair_strands if os.environ.get('EVE_HAIR_STRANDS') == '1'
                     else (lambda: flat(HAIR_HEX, 0.45, alpha=hair_alpha, size=hair_alpha.shape[0])))

# EVE_OUTFIT=face: Eve's head as the Wilds face mesh (build_eve_face.py KEEP order -> evf00..05)
if os.environ.get('EVE_OUTFIT') == 'face':
    MATERIALS = {k: MATERIALS[k] for k in ('MI_EVE_Head_V02_Jali', 'MI_EyeRefractive1', 'MI_Teeth', 'MI_EyeBrow1', 'MI_EVE_HR_01_TypeA')}
    MATERIALS['NewMaterial'] = lambda: flat(os.environ.get('EVE_LASH_HEX', '1C1814'), 0.55)   # eyelashes (geometry strands)
    # Eve's sword folded into her hairpin (CH_W_Sword_01_Folded, material CH_W_Sword_02_Blade_Body: D / M (R AO, G rough, B metal) / N)
    if os.environ.get('EVE_HAIRPIN') == '1':
        MATERIALS['CH_W_Sword_02_Blade_Body'] = lambda: std('CH_W_Sword_02_D', 'CH_W_Sword_02_M', 'CH_W_Sword_02_N')



def save_tga(arr, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True); im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).reshape(-1))
    im.filepath_raw = path; im.file_format = 'TARGA_RAW'; im.save(); bpy.data.images.remove(im)


EMISSIVE = {}   # material -> RGBA emissive texture (written as <key>_EMI, bound to EmissiveMap)
EMIT_POWER = {}   # per-material emissive intensity (default EVE_DECO_EMIT)
VEIL_MATS = {}    # materials drawn with the translucent veil template (fx 'veil')
ONLY_TEX = set(filter(None, os.environ.get('EVE_ONLY_TEX', '').split(',')))   # rebuild just these (e.g. evm04)
SKIP_TEX = os.environ.get('EVE_SKIP_TEX') == '1'   # reuse textures already written (mdf-only rerun)
tex_ver = getTexVersionFromGameName('MHWILDS')
tc = Texconv(); short = {}; written = []
def write_tex(name, arr, fmt):
    tga = os.path.join(tmp, name + '.tga'); save_tga(arr, tga)
    tc.convert_to_dds(file=tga, dds_fmt=fmt, out=tmp, no_mip=False, verbose=False)
    DDSToTex([os.path.join(tmp, name + '.dds')], tex_ver, os.path.join(tex_dir, name.lower() + f'.tex.{tex_ver}'))
    written.append(name)
for i, (mat, fn) in enumerate(MATERIALS.items()):
    key = f"{os.environ.get('EVE_MAT_PREFIX', 'evd')}{i:02d}"; short[mat] = key
    if SKIP_TEX or (ONLY_TEX and key not in ONLY_TEX):
        written += [key + s for s in ('_ALBD', '_NRRO', '_ATOS', '_EMI') if os.path.exists(os.path.join(tex_dir, (key + s).lower() + f'.tex.{tex_ver}'))]
        continue
    _sk0 = len(SKIN_CALLS); albd, nrro, atos = fn()
    if len(SKIN_CALLS) > _sk0: SKIN_MATS.add(mat)
    if atos is not None and (mat.startswith('MI_EVE_HR') or mat.startswith('MI_EyeBrow')):
        # hair / brow: no skin subsurface (ATOS T / O / S = 1 / 0 / 1 read as a pink glow on the ponytail in game)
        t_, o_, s_ = (float(x) for x in os.environ.get('EVE_HAIR_ATOS', '0.3,1,0').split(','))
        atos[..., 1] = t_; atos[..., 2] = o_; atos[..., 3] = s_
    write_tex(key + '_ALBD', albd, 'BC7_UNORM_SRGB'); write_tex(key + '_NRRO', nrro, 'BC7_UNORM')
    if atos is not None: write_tex(key + '_ATOS', atos, 'BC7_UNORM')
    if mat in EMISSIVE: write_tex(key + '_EMI', EMISSIVE[mat], 'BC7_UNORM_SRGB')
unload_texconv()
report['textures'] = written; report['materials'] = short

template_mats = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('Material')]
template = next(o for o in template_mats if o.re_mdf_material.materialName == 'ch03_091_0002_body_UseSC')
mdf_col = next(c for c in bpy.data.collections if c.name.endswith('.mdf2'))
# EVE_SKIN_TEMPLATE_MDF + EVE_SKIN_KEYS: those materials (Eve's skin) use the hunter's own skin material from that mdf2
# (Base_ATOS_SkinEdit_VFX: subsurface skin shading) instead of the plain equipment shader, with Eve's textures bound
skin_tmpl = None
if os.environ.get('EVE_SKIN_TEMPLATE_MDF'):
    before_ = set(bpy.data.objects); sp = os.environ['EVE_SKIN_TEMPLATE_MDF']
    bpy.ops.re_mdf.importfile(files=[{'name': os.path.basename(sp)}], directory=os.path.dirname(sp))
    new_ = [o for o in bpy.data.objects if o not in before_]
    skin_tmpl = next((o for o in new_ if o.type == 'EMPTY' and o.re_mdf_material.materialName == 'skin'), None)
    for o in new_:
        if o is not skin_tmpl: bpy.data.objects.remove(o, do_unlink=True)
    if skin_tmpl:
        for c in list(skin_tmpl.users_collection): c.objects.unlink(skin_tmpl)
    report['skinTemplate'] = bool(skin_tmpl)
SKIN_KEYS = set(filter(None, os.environ.get('EVE_SKIN_KEYS', '').split(',')))
NULLS = {'EmissiveMap': 'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
         'FxMap': 'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
         'ColorLayer_MaskMap': 'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
         'AlphaTranslucentOcclusionSSSMap': 'systems/rendering/NullATOS.tex'}
for mat, key in short.items():
    if key in os.environ.get('EVE_MDF_SKIP', '').split(','): continue   # material dropped from the mesh: mdf must list the same set
    veil = (mat == 'MA_Plastic_2_Inst' and os.environ.get('EVE_CAPE_VEIL') == '1') or mat in VEIL_MATS
    src_t = next(t for t in template_mats if t.re_mdf_material.materialName == 'ch03_091_0002_body_veil_UseSC') if veil else template
    if key in SKIN_KEYS and skin_tmpl: src_t = skin_tmpl
    o = src_t.copy(); mdf_col.objects.link(o); o.name = f'Material ({key})'
    if veil:
        VEIL = {'RoughTransparent_Color': tuple(float(x) for x in os.environ.get('EVE_CAPE_TINT', '0.80,0.92,1.0,1.0').split(',')), 'Tranparent_Roughness': 1.2, 'AlphaAdjust': 0.5,
                'Film_Blend': 0.35, 'MetalParam': 0.1, 'RoughnessParam': 1.0,
                'Emissive_Intensity': float(os.environ.get('EVE_CAPE_EMIT', '0')), 'Emissive_Color': (1.0, 1.0, 1.0, 1.0)}
        if mat in VEIL_MATS:   # per-material veil (SB translucent BlendMode 2 parts: Santa sleeves, YoRHa lace / skirt)
            vv = VEIL_MATS[mat]
            VEIL.update({'RoughTransparent_Color': tuple(vv.get('tint', [0.2, 0.2, 0.22, 1.0])), 'AlphaAdjust': float(vv.get('alphaAdjust', 0.5)),
                         'Film_Blend': float(vv.get('film', 0.0)), 'Tranparent_Roughness': float(vv.get('tRough', 1.2))})
            report.setdefault('veil', {})[key] = vv
        for pr in o.re_mdf_material.propertyList_items:
            if pr.prop_name in VEIL:
                v = VEIL[pr.prop_name]
                if isinstance(v, tuple): pr.color_value = v
                else: pr.float_value = v
    if not veil and mat in EMISSIVE:
        names = []
        for pr in o.re_mdf_material.propertyList_items:
            names.append(pr.prop_name)
            if pr.prop_name in ('Emissive_Intensity', 'EmissiveIntensity', 'Emissive_Power'): pr.float_value = EMIT_POWER.get(mat, float(os.environ.get('EVE_DECO_EMIT', '4')))
            elif pr.prop_name in ('Emissive_Color', 'EmissiveColor'): pr.color_value = (1.0, 1.0, 1.0, 1.0)
        report.setdefault('emissiveProps', {})[key] = [n for n in names if 'mis' in n.lower()]
    o.re_mdf_material.materialName = key
    o.re_mdf_material.linkedMaterial = bpy.data.materials.get(key) or bpy.data.materials.new(key)
    for b in o.re_mdf_material.textureBindingList_items:
        if b.textureType == 'BaseDielectricMap': b.path = f'{TEX_REL}/{key}_ALBD.tex'
        elif b.textureType == 'NormalRoughnessOcclusionMap': b.path = f'{TEX_REL}/{key}_NRRO.tex'
        elif b.textureType == 'AlphaTranslucentOcclusionSSSMap' and f'{key}_ATOS' in written: b.path = f'{TEX_REL}/{key}_ATOS.tex'
        elif b.textureType == 'EmissiveMap' and f'{key}_EMI' in written: b.path = f'{TEX_REL}/{key}_EMI.tex'
        elif b.textureType in NULLS: b.path = NULLS[b.textureType]
    # cut-out hair / brow / lace: the equipment shader only clips by the ATOS alpha when AlphaTestEnable is on
    # (left off, the ponytail cards drew as solid quads -- a wide pink block in game)
    if f'{key}_ATOS' in written and not veil and os.environ.get('EVE_ALPHA_TEST', '1') == '1':
        o.re_mdf_material.flags.AlphaTestEnable = True
        report.setdefault('alphaTest', []).append(key)
    # shadows (user 10-18: the Eve body cast no shadow in game): the template material has ShadowCastDisable set; the
    # game's own equipment materials have it off
    if os.environ.get('EVE_SHADOW', '1') == '1':
        o.re_mdf_material.flags.ShadowCastDisable = False
    # subsurface: the template is a skin-like equipment material with SSSParam 1 (skin profile) on every material; the
    # screen-space scattering bled a strong pink fringe round the hair strands, lace and body outline in game.
    # Skin keeps a little (EVE_SSS_SKIN), everything else none (EVE_SSS_OTHER, and the SSS profile flag off).
    if not veil:
        # every Eve skin material (face, reference body, outfit body-skin '..._BB_..'): SB skin look (user 10-18: keep this
        # option for all Eve outfits) -- BaseTint in skin(), full SSS here
        skin = mat in SKIN_MATS or mat in ('MI_EVE_Head_V02_Jali',) or any(k in mat for k in ('_BB_', 'Basebody', 'BaseBody', 'Skin'))
        # 2026-10-21: the name rule also caught non-skin SB materials (S22 Nikke_05_Skin_02 = MA_CH_Standard_Ver03
        # clearcoat suit). EVE_SSS_NOT_SKIN=<mat,...> takes listed materials out of the skin SSS; default unchanged.
        if mat in set(filter(None, os.environ.get('EVE_SSS_NOT_SKIN', '').split(','))): skin = False
        sss = float(os.environ.get('EVE_SSS_SKIN' if skin else 'EVE_SSS_OTHER', '1.0' if skin else '0'))   # skin: full SSS again (the pink rim was the VFX blend, not SSS)
        # equipment-only overlays the game drives on armour parts (VFX layer, dirt / sand dynamic material): the pink
        # rim stayed on the body part (outfit, ponytail, outline) with SSS off, while the face mesh had none
        vfx = float(os.environ.get('EVE_VFX_BLEND', '0')); dyn = float(os.environ.get('EVE_DYNMAT', '0'))
        for pr in o.re_mdf_material.propertyList_items:
            if pr.prop_name == 'SSSParam': pr.float_value = sss
            elif pr.prop_name == 'VFXBlend_Weight': pr.float_value = vfx
            elif pr.prop_name == 'DynamicMat_Weight': pr.float_value = dyn
        if sss <= 0: o.re_mdf_material.flags.SSSProfileUsed = False
        report.setdefault('sss', {})[key] = sss
for o in template_mats: bpy.data.objects.remove(o, do_unlink=True)
if skin_tmpl: bpy.data.objects.remove(skin_tmpl, do_unlink=True)
# The add-on reports export problems through UI popups, which crash Blender in --background: print them instead.
import RE_Mesh_Editor.modules.mdf.blender_re_mdf as _mdfmod
_mdfmod.showMessageBox = lambda *a, **k: print('RE MSG', a, k)
_mdfmod.showErrorMessageBox = lambda *a, **k: print('RE ERROR', a, k)
r = bpy.ops.re_mdf.exportfile(filepath=os.path.join(out_dir, os.environ.get('EVE_MDF_NAME', 'eve_default') + '.mdf2.45'), targetCollection=mdf_col.name)
report['export'] = list(r)
json.dump(report, open(report_path, 'w'), indent=1, default=str)
print('done')
