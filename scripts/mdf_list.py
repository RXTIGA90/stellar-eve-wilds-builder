import sys, json
import os; sys.path.insert(0, os.path.join(os.environ.get('BLENDER_USER_SCRIPTS', ''), 'addons'))
from RE_Mesh_Editor.modules.mdf.file_re_mdf import readMDF
for p in sys.argv[sys.argv.index('--') + 1:]:
    m = readMDF(p); print('MATS ' + p + ' :: ' + json.dumps([[x.materialName, x.mmtrPath.split('/')[-1]] for x in m.materialList]))
