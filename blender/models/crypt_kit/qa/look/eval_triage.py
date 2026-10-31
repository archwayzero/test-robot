"""Candidate metrics on the four builds, like for like: 145 px stone-only boxes (clean crypt.jpg box vs back wall centre in the render)."""
import sys, json; sys.path.insert(0,'tools')
import numpy as np, metrics, rmetrics_lib as R
ref=R.rd('builds/v4/reference/map/crypt.jpg')
CLEAN=(1350,724,1495,869)   # px in crypt.jpg, stone only (no statue, no cast shadow)
BOX=(873,478,1018,623)      # 145 px, back wall centre, render px
def L(c): return c@metrics.LUM
def localc(l,w=9):
    k=np.ones(w)/w
    bl=lambda a:np.apply_along_axis(lambda r:np.convolve(r,k,'same'),0,np.apply_along_axis(lambda r:np.convolve(r,k,'same'),1,a))
    m=bl(l); s=np.sqrt(np.maximum(bl(l*l)-m*m,0)); e=w
    return float(np.median((s/(m+1e-6))[e:-e,e:-e]))
def shape(b): e=np.log2(np.array(b)); return e-e.mean()
def m(c):
    d=metrics.crop_metrics(c); l=L(c); d.update({('ml_'+k):float(v) for k,v in R.ml(c).items()}); d['crete']=float(R.crete(l)); d['local']=localc(l)
    q=np.percentile(l/np.median(l),np.arange(1,100)); d['q']=q.tolist(); return d
x0,y0,x1,y1=CLEAN; rc=m(ref[y0:y1,x0:x1])
res={'crypt_clean':rc}
for rig,f in (('lit','arcade_crypt_camera.png'),('flat','arcade_flat.png')):
    for b in ('v1','v2','v3','v4'):
        a=R.rd(f'renders/{rig}/{b}/{f}'); x0,y0,x1,y1=BOX; res[f'{rig}/{b}']=m(a[y0:y1,x0:x1])
for v in ('i_dad70d3',):
    a=R.rd(f'renders/lit/{v}/arcade_crypt_camera.png'); x0,y0,x1,y1=BOX; res[f'lit/{v}']=m(a[y0:y1,x0:x1])
for v in ('v2_stain_both','v2_tone','v2_tone_rim','v4_R_stain_sharp','v4_R_tone','v4_R_rim','v4_R_stain_tone_rim'):
    a=R.rd(f'renders/abl/{v}/arcade_crypt_camera.png'); x0,y0,x1,y1=BOX; res[f'abl/{v}']=m(a[y0:y1,x0:x1])
for k,d in res.items():
    d['spec_dist']=float(np.linalg.norm(shape(d['bands'])-shape(rc['bands'])))
    d['hist_emd']=float(np.abs(np.array(d['q'])-np.array(rc['q'])).mean())
json.dump(res,open('eval_boxes.json','w'))
ks=['ml_mid','ml_span','ml_fine','fine_over_coarse','crete','local','spec_dist','hist_emd']
print('%-26s'%'stone-only 145px box',*['%8s'%k[:8] for k in ks],'k0','bands')
for t,d in res.items():
    print('%-26s'%t,*['%8.4f'%d[k] for k in ks],'%.2f'%d['kurt'][0],' '.join('%.3f'%v for v in d['bands']))
