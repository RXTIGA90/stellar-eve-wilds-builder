"""Hunter reference rig for the builder: the user's own ch03_000_9000.fbxskel as armature 'Wilds_Female_Reference'
(rest pose = the game's bind pose, Blender world = armature space).
usage: blender -b --factory-startup -P make_reference_rig.py -- <ch03_000_9000.fbxskel.7> <out.blend>"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from re_mesh_common import register_re_mesh_editor
register_re_mesh_editor()
from RE_Mesh_Editor.modules.fbxskel.blender_re_fbxskel import importFBXSkelFile
src, out = sys.argv[sys.argv.index('--') + 1:]
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
arm = importFBXSkelFile(src)
arm.name = 'Wilds_Female_Reference'
print('BONES', len(arm.data.bones))
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('saved', out)
