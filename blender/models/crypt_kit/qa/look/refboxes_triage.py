import sys; sys.path.insert(0,'tools')
import numpy as np, OpenImageIO as oiio, metrics, rmetrics_lib as R
ref=R.rd('builds/v4/reference/map/crypt.jpg'); k=ref.shape[1]/2000
print('box                      x0   y0   x1   y1  |  p50 span mid fine | f/c crete k0 blue%')
B={'REF back wall (target)':(1130,620,1450,900),'clean R stone':(1305,700,1445,840),'clean R stone2':(1345,720,1445,820),'clean L stone':(1135,650,1205,720),'pier target':(560,880,690,1190),'web target':(760,110,1100,200)}
for n,b in B.items():
    x0,y0,x1,y1=[int(v*k) for v in b]; c=ref[y0:y1,x0:x1]; m=R.one(ref,b,k)
    blue=(c[...,2]>c[...,0]).mean()*100
    print('%-22s %5d %4d %5d %4d | %.3f %.3f %.4f %.4f | %.2f %.3f %.2f %.1f'%(n,x0,y0,x1,y1,m['ml_p50'],m['ml_span'],m['ml_mid'],m['ml_fine'],m['fine_over_coarse'],m['crete'],m['kurt'][0],blue))
