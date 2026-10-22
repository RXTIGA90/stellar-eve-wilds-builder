"""Apply an eve-mesh-delta-v1 (data/repro/<key>.delta.json) to a built mesh (Blender; called by eve_repro.mesh).
usage: blender -b -P eve_repro_delta.py -- <built mesh> <delta json> <out mesh>"""
import bpy, sys, os, json, addon_utils
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index('--') + 1:]; BASE, DELTA, OUT = a
addon_utils.enable('RE_Mesh_Editor', default_set=True)
D = json.load(open(DELTA))
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bc = set(bpy.data.collections)
bpy.ops.re_mesh.importfile(files=[{'name': os.path.basename(BASE)}], directory=os.path.dirname(BASE), loadMaterials=False)
col = next(c for c in bpy.data.collections if c not in bc and c.name.endswith('.mesh'))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
# bones: the rest matrices given by the delta
if D.get('bones'):
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
    for n, m in D['bones'].items():
        eb = arm.data.edit_bones.get(n)
        if eb: L = eb.length; eb.matrix = Matrix(m); eb.length = L
    bpy.ops.object.mode_set(mode='OBJECT')
done = {'pos': 0, 'normal': 0, 'uv': 0, 'weights': 0}
for o in [x for x in col.objects if x.type == 'MESH']:
    e = D['submeshes'].get(o.name.split('__')[-1].split('.')[0])   # keyed by material key
    if not e: continue
    me = o.data
    if len(me.vertices) != e['verts']: raise SystemExit(f'vertex count differs: {o.name}')
    N = [None] * len(me.vertices)
    for l, cn in zip(me.loops, me.corner_normals): N[l.vertex_index] = tuple(cn.vector)
    for i, d in e.get('pos', {}).items(): v = me.vertices[int(i)]; v.co = v.co + Vector(d); done['pos'] += 1
    for i, n in e.get('normal', {}).items(): N[int(i)] = tuple(n); done['normal'] += 1
    if 'uv' in e:
        uvl = me.uv_layers[0].data
        for l in me.loops:
            u = e['uv'].get(str(l.vertex_index))
            if u: uvl[l.index].uv = u
        done['uv'] += len(e['uv'])
    for i, w in e.get('weights', {}).items():
        vi = int(i)
        for g in o.vertex_groups: g.remove([vi])
        for bn, x in w.items():
            g = o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn); g.add([vi], x, 'REPLACE')
        done['weights'] += 1
    # custom normals are ignored on flat-shaded faces / across sharp edges
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    for an in ('sharp_edge', 'sharp_face'):
        if an in me.attributes: me.attributes.remove(me.attributes[an])
    me.normals_split_custom_set_from_vertices(N)
r = list(bpy.ops.re_mesh.exportfile(filepath=OUT, targetCollection=col.name, exportAllLODs=False, exportBoundingBoxes=True))
print('APPLY', done, r)
