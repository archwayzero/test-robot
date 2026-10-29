"""Parameter probe for rig.py (no bake): loads rig.py as a module, builds scene+weights+solver, then runs a
user snippet (--code FILE) with helpers: R (module), S (solver), hero, arm, apply(P), ev() -> deformed coords,
W (weights list), co_rest. blender -b --factory-startup -P probe.py -- --code snippet.py
"""
import importlib.util
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
code = argv[argv.index("--code") + 1]
spec = importlib.util.spec_from_file_location("rigmod", "blender/rigs/hero/rig.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
hero, arm = R.setup_scene()
W, arms = R.compute_weights(hero)
S = R.Solver(arm, hero, W)
nv = len(hero.data.vertices)
co_rest = np.array([v.co[:] for v in hero.data.vertices])


def apply(P):
    L, Wm = S.solve(P)
    for b, M in L.items():
        arm.pose.bones[b].matrix_basis = M
    bpy.context.view_layer.update()
    return Wm


def ev():
    dg = bpy.context.evaluated_depsgraph_get()
    ob = hero.evaluated_get(dg)
    m = ob.to_mesh()
    c = np.empty(nv * 3)
    m.vertices.foreach_get("co", c)
    ob.to_mesh_clear()
    return c.reshape(nv, 3)


def wsum(*names):
    return np.array([sum(w.get(n, 0) for n in names) for w in W])


exec(open(code).read())
