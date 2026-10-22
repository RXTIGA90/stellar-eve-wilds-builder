# blender -b <blend> -P mdf_drop.py -- <in.mdf2> <out.mdf2> <keep1,keep2,...>
import bpy, sys, os
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()
src, dst, keep = sys.argv[sys.argv.index('--') + 1:]
keep = keep.split(',')
before = set(bpy.data.objects)
bpy.ops.re_mdf.importfile(files=[{'name': os.path.basename(src)}], directory=os.path.dirname(src))
new = [o for o in bpy.data.objects if o not in before]
col = next(c for c in bpy.data.collections if c.name.endswith('.mdf2') and any(o in new for o in c.objects))
for o in list(col.objects):
    if o.type == 'EMPTY' and hasattr(o, 're_mdf_material') and o.re_mdf_material.materialName and o.re_mdf_material.materialName not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
import RE_Mesh_Editor.modules.mdf.blender_re_mdf as m_
m_.showMessageBox = lambda *a, **k: print('RE MSG', a, k); m_.showErrorMessageBox = lambda *a, **k: print('RE ERROR', a, k)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print('EXPORT', bpy.ops.re_mdf.exportfile(filepath=dst, targetCollection=col.name), [o.re_mdf_material.materialName for o in col.objects if o.type == 'EMPTY' and hasattr(o, 're_mdf_material')])
