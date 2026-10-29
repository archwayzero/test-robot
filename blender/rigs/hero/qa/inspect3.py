import bpy
from mathutils import Vector
from mathutils.geometry import intersect_point_line
o=bpy.data.objects['hero']; me=o.data
H=Vector((-0.1413,0.0238,0.336)); A=Vector((-0.1531,-0.048,0.2233)); K=Vector((-0.1303,0.0834,0.4471))
import collections
bins=collections.Counter(); ex=collections.defaultdict(list)
for v in me.vertices:
    c=v.co
    if c.x>-0.05 or c.z>0.5: continue
    p,t=intersect_point_line(c,H,A)
    d=(c-p).length
    if c.z<0.36:
        key=(round(t,1), round(d,2)); bins[key]+=1
for k in sorted(bins): print(k,bins[k])
# knee region: distance to knee->hock axis
print("knee")
bins=collections.Counter()
for v in me.vertices:
    c=v.co
    if c.x>-0.05 or not (0.33<c.z<0.56): continue
    p,t=intersect_point_line(c,K,H); d=(c-p).length
    bins[(round(t,1),round(d,2))]+=1
for k in sorted(bins): print(k,bins[k])
