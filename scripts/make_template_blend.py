"""Armor template blend for the builder: RE Mesh Editor import of the user's own ch03_091_0002 mesh + mdf2
(the builder takes its equipment material set and settings from here).
usage: blender -b --factory-startup -P make_template_blend.py -- <folder with ch03_091_0002.*> <out.blend>"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()
src, out = sys.argv[sys.argv.index('--') + 1:]
src = os.path.join(os.path.normpath(src), '')
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
r1 = bpy.ops.re_mesh.importfile(filepath=src + 'ch03_091_0002.mesh.241111606', files=[{'name': 'ch03_091_0002.mesh.241111606'}], directory=src)
r2 = 'mdf loaded with the mesh'
print('IMPORT', r1, r2, [c.name for c in bpy.data.collections])
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('saved', out)
