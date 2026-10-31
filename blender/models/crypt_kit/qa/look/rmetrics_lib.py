import sys, json
sys.path.insert(0,'tools')
import numpy as np, OpenImageIO as oiio, metrics
from pathlib import Path
def rd(p):
    i=oiio.ImageInput.open(str(p)); a=i.read_image('float'); i.close(); return a[...,:3].astype(np.float64)
def blur(L,s):
    r=int(4*s)+2; p=np.pad(L,r,mode='reflect'); h,w=p.shape
    fy=np.fft.fftfreq(h)[:,None]; fx=np.fft.rfftfreq(w)[None,:]
    return np.fft.irfft2(np.fft.rfft2(p)*np.exp(-2*(np.pi*s)**2*(fx**2+fy**2)),s=(h,w))[r:-r,r:-r]
def ml(r,sc=1):
    "measure_look.st definitions"
    L=r@metrics.LUM; p=np.percentile(L,[5,50,95])
    return dict(p50=p[1],span=p[2]-p[0],fine=(L-blur(L,6*sc)).std(),mid=(blur(L,6*sc)-blur(L,30*sc)).std())
def crete(L):
    "Crete-Roffet no-reference blur estimate, 0 sharp .. 1 blurred"
    b=blur(L,1.5); o=[]
    for ax in (0,1):
        dF=np.abs(np.diff(L,axis=ax)); dB=np.abs(np.diff(b,axis=ax)); o.append(np.maximum(0,dF-dB).sum()/dF.sum())
    return 1-min(o)
Q={"back wall":(810,400,1080,700),"web":(650,110,880,160),"pier":(310,600,480,950),"floor":(560,760,1000,900)}
REF={"back wall":(1130,620,1450,900),"web":(760,110,1100,200),"pier":(560,880,690,1190)}
def one(r,box,sc):
    x0,y0,x1,y1=[int(v*sc) for v in box]; c=r[y0:y1,x0:x1]
    m=metrics.crop_metrics(c); m.update({('ml_'+k):float(v) for k,v in ml(c,sc).items()}); m['crete']=float(crete(c@metrics.LUM)); return m
