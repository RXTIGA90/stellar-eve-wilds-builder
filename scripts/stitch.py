# blender -b -P stitch.py -- out.png crop(x0,y0,x1,y1 frac or 'full') in1 in2 ...  (side by side, same size)
import bpy, sys
a = sys.argv[sys.argv.index('--') + 1:]
out, crop, ins = a[0], a[1], a[2:]
ims = [bpy.data.images.load(p) for p in ins]
W, H = ims[0].size
x0, y0, x1, y1 = [float(t) for t in crop.split(',')] if crop != 'full' else (0, 0, 1, 1)
cx0, cx1 = int(x0 * W), int(x1 * W); cy0, cy1 = int((1 - y1) * H), int((1 - y0) * H)   # crop given top-down
cw, ch = cx1 - cx0, cy1 - cy0
sheet = bpy.data.images.new('s', cw * len(ims), ch)
px = [0.0] * (cw * len(ims) * ch * 4)
for k, im in enumerate(ims):
    src = im.pixels[:]
    for y in range(ch):
        s0 = ((cy0 + y) * W + cx0) * 4; d0 = (y * cw * len(ims) + k * cw) * 4
        px[d0:d0 + cw * 4] = src[s0:s0 + cw * 4]
sheet.pixels = px; sheet.filepath_raw = out; sheet.file_format = 'PNG'; sheet.save()
