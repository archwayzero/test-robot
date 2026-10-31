import sys, json, os
sys.path.insert(0,'tools')
import numpy as np, OpenImageIO as oiio, metrics
from pathlib import Path
FONT=sys.argv[1]
BU=[('v1','7590125 pass 1'),('v2','a6d7e65 first reviewed'),('v3','96e3e55 pass 3'),('v4','3905db7 pass 4')]
def rd(p):
    i=oiio.ImageInput.open(str(p)); a=i.read_image('float'); i.close(); return a[...,:3].astype(np.float64)
def wr(p,a):
    a=np.clip(a,0,1); s=oiio.ImageSpec(a.shape[1],a.shape[0],3,'uint8'); o=oiio.ImageOutput.create(str(p)); o.open(str(p),s); o.write_image((a*255+.5).astype(np.uint8)); o.close()
G5={'0':'3E5149453E','1':'00427F4000','2':'4261514946','3':'2141454B31','4':'1814127F10','5':'2745454539','6':'3C4A494930','7':'0171090503','8':'3649494936','9':'064949291E',
'A':'7E1111117E','B':'7F49494936','C':'3E41414122','D':'7F4141221C','E':'7F49494941','F':'7F09090901','G':'3E4149497A','H':'7F0808087F','I':'00417F4100','J':'2040413F01','K':'7F08142241','L':'7F40404040','M':'7F020C027F','N':'7F0408107F','O':'3E4141413E','P':'7F09090906','Q':'3E4151215E','R':'7F09192946','S':'4649494931','T':'01017F0101','U':'3F4040403F','V':'1F2040201F','W':'3F4038403F','X':'6314081463','Y':'0708700807','Z':'6151494543',
'.':'0060600000','+':'08083E0808','-':'0808080808',',':'0050300000','[':'007F414100',']':'0041417F00',':':'0036360000',' ':'0000000000'}
def label(a,t,size=24):
    "strip above the image: the image's own pixels are never covered. OIIO here has no FreeType, so a 5x7 bitmap font"
    k=3; H=7*k+12
    o=np.vstack([np.zeros((H,a.shape[1],3)),a])
    x=8
    for ch in t.upper():
        g=bytes.fromhex(G5[ch])
        for i,col in enumerate(g):
            for j in range(7):
                if col>>j&1: o[6+j*k:6+(j+1)*k,x+i*k:x+(i+1)*k]=(1,1,.6)
        x+=6*k
    return o
def rs(a,w,h):
    b=oiio.ImageBuf(oiio.ImageSpec(a.shape[1],a.shape[0],3,'float')); b.set_pixels(oiio.ROI(0,a.shape[1],0,a.shape[0],0,1,0,3),a.astype(np.float32))
    r=oiio.ImageBufAlgo.resize(b,roi=oiio.ROI(0,w,0,h,0,1,0,3)); return r.get_pixels(oiio.FLOAT).reshape(h,w,3).astype(np.float64)
def nn(a,k): return np.repeat(np.repeat(a,k,0),k,1)
def grid(rows):
    return np.vstack([np.hstack(r) for r in rows])
ref=rd('builds/v4/reference/map/crypt.jpg')
print('crypt',ref.shape)
PW,PH=750,500
rh=ref.shape[0]*PW//ref.shape[1]
refp=rs(ref,PW,rh)
if rh<PH: refp=np.vstack([refp,np.zeros((PH-rh,PW,3))])
refp=refp[:PH]
for rig,cand in (('lit','arcade_crypt_camera.png'),('flat','arcade_flat.png')):
    ims={}
    for b,_ in BU:
        p=Path(f'renders/{rig}/{b}/{cand}')
        if p.exists(): ims[b]=rd(p)
    if len(ims)<4: print('missing',rig,list(ims)); continue
    if rig=='lit':
        for (b,d) in BU:
            wr(f'snap_{b}_{d.split()[0]}.png',ims[b])
    else:
        for (b,d) in BU:
            wr(f'snap_flat_{b}_{d.split()[0]}.png',ims[b])
    P={b:label(rs(ims[b],PW,PH),f'{b} {d} [{rig}]') for b,d in BU}
    crop=np.hstack([rs(ims['v2'][400:700,810:1080],375,417),rs(ims['v4'][400:700,810:1080],375,417)])
    crop=np.vstack([crop,np.zeros((83,750,3))])
    crop=label(crop,'back wall crop: v2 left, v4 right')
    wr(f'snap_4up{"" if rig=="lit" else "_flat"}.png',grid([[P['v1'],P['v2'],label(refp,'crypt.jpg')],[P['v3'],P['v4'],crop]]))
    BOX={'wall':(850,450,1050,650),'pier':(500,590,620,790),'web':(620,90,900,180)}
    for n,(x0,y0,x1,y1) in BOX.items():
        k=3 if n!='web' else 2
        tiles=[label(nn(ims[b][y0:y1,x0:x1],k),f'{b}',22) for b,_ in BU]
        wr(f'crop_{rig}_{n}.png',grid([tiles[:2],tiles[2:]]))
    for n in ('close_wall','close_pier','close_web'):
        t={b:rd(f'renders/{rig}/{b}/{n}.png') for b,_ in BU if Path(f'renders/{rig}/{b}/{n}.png').exists()}
        if len(t)==4:
            wr(f'{n}_{rig}_4up.png',grid([[label(rs(t['v1'],750,500),'v1'),label(rs(t['v2'],750,500),'v2')],[label(rs(t['v3'],750,500),'v3'),label(rs(t['v4'],750,500),'v4')]]))

# isolation montage: same rig, same pixels
V=[('renders/lit/v2','v2 as built'),('renders/lit/v4','v4 as built'),('renders/abl/v4_R_stain_sharp','v4 + v2 stain'),('renders/abl/v4_R_rim','v4, rim 0'),('renders/abl/v4_R_tone','v4, tone .10'),('renders/abl/v4_R_stain_tone_rim','v4 + stain tone rim of v2')]
T=[]
for d,t in V:
    a=rd(d+'/arcade_crypt_camera.png')[400:700,810:1080]; c=rd(d+'/close_wall.png')[300:700,450:1050]
    T.append(label(np.hstack([np.repeat(np.repeat(a,2,0),2,1)[:540,:540],rs(c,810,540)]),t))
wr('isolation_lit.png',grid([T[:2],T[2:4],T[4:]]))
