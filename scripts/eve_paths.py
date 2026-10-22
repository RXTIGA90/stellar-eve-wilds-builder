"""One place for every path the builder uses.

Reads config.json from the builder root (one folder above this script). Each key can be overridden with an
environment variable of the same name in upper case (e.g. MHW_DIR). Blender scripts import this too: the
script's own folder is on sys.path when Blender runs a script with --python.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
_CFG_FILE = os.path.join(ROOT_DIR, 'config.json')
_cfg = json.load(open(_CFG_FILE, encoding='utf-8-sig')) if os.path.exists(_CFG_FILE) else {}

DEFAULTS = {
    'mhw_dir': r'C:\Program Files (x86)\Steam\steamapps\common\MonsterHunterWilds',
    'sb_paks': r'C:\Program Files (x86)\Steam\steamapps\common\StellarBlade\SB\Content\Paks',
    'work_dir': os.path.join(ROOT_DIR, 'work'),
    'blender': os.path.join(ROOT_DIR, 'tools', 'blender', 'blender.exe'),
    'blender_user_scripts': os.path.join(ROOT_DIR, 'tools', 'blender', 'user-scripts'),
    'dotnet': 'dotnet',
    'ree_editor_dir': os.path.join(ROOT_DIR, 'tools', 'ree-content-editor'),
    'previews': False,
}


def get(key):
    v = os.environ.get(key.upper())
    if v is None:
        v = _cfg.get(key, DEFAULTS[key])
    return v


def slash(p):
    """Forward slashes and a trailing slash for folders (the scripts join paths with +)."""
    p = str(p).replace('\\', '/')
    return p if p.endswith('/') else p + '/'


ROOT = slash(ROOT_DIR)                       # builder root (scripts, data, game files we ship)
SCRIPTS = slash(HERE)
DATA = ROOT + 'data/'
WORK = slash(get('work_dir'))                # everything extracted / built on this PC (never shipped)
P = WORK                                      # old name: assets/private
GAME = slash(get('mhw_dir'))
SB_PAKS = str(get('sb_paks'))
BLENDER = str(get('blender'))
USER_SCRIPTS = str(get('blender_user_scripts'))
DOTNET = str(get('dotnet'))
PREVIEWS = str(get('previews')).lower() in ('1', 'true', 'yes')
