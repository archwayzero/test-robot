import bpy, bmesh
from mathutils import Vector
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, tuple(round(v,3) for v in o.location), tuple(o.dimensions), o.parent)
me = [o for o in bpy.data.objects if o.type=='MESH']
for o in me:
    m=o.data
    print("mesh", o.name, len(m.vertices), len(m.polygons), [mt.name for mt in m.materials], len(o.vertex_groups), [md.type for md in o.modifiers])
    co=[o.matrix_world@v.co for v in m.vertices]
    for ax in range(3):
        print(ax, min(c[ax] for c in co), max(c[ax] for c in co))
    # cross sections of left leg (x<0) by z
    import collections
    for z in [0.0,0.02,0.05,0.1,0.15,0.2,0.25,0.3,0.336,0.38,0.42,0.447,0.48,0.52,0.6,0.7,0.8,0.87,0.95,1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7]:
        s=[c for c in co if abs(c.z-z)<0.01]
        L=[c for c in s if c.x<-0.02]; 
        if s:
            print("z=%.3f n=%d x[%.3f,%.3f] y[%.3f,%.3f] | left x[%s] y[%s]"%(z,len(s),min(c.x for c in s),max(c.x for c in s),min(c.y for c in s),max(c.y for c in s),
              "%.3f,%.3f"%(min(c.x for c in L),max(c.x for c in L)) if L else "-", "%.3f,%.3f"%(min(c.y for c in L),max(c.y for c in L)) if L else "-"))
    # loose parts
    bm=bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table()
    seen=set(); parts=[]
    for v in bm.verts:
        if v.index in seen: continue
        st=[v]; seen.add(v.index); comp=[]
        while st:
            a=st.pop(); comp.append(a.index)
            for e in a.link_edges:
                b=e.other_vert(a)
                if b.index not in seen: seen.add(b.index); st.append(b)
        parts.append(comp)
    print("parts", len(parts))
    parts.sort(key=len, reverse=True)
    for p in parts[:40]:
        pc=[co[i] for i in p]
        mn=Vector((min(c.x for c in pc),min(c.y for c in pc),min(c.z for c in pc)));mx=Vector((max(c.x for c in pc),max(c.y for c in pc),max(c.z for c in pc)))
        print(" part n=%d min %s max %s"%(len(p),tuple(round(x,3) for x in mn),tuple(round(x,3) for x in mx)))
