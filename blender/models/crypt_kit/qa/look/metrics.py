"""Texture measures. All on sRGB-encoded luma (approx. perceived value)."""
import numpy as np
LUM = np.array([.2126, .7152, .0722])
OCT = [(0.0078,0.0156),(0.0156,0.031),(0.031,0.0625),(0.0625,0.125),(0.125,0.25),(0.25,0.5),(0.5,1.0)]  # wavelength bands, m

def kurt(x):
    x = x - x.mean(); s = x.var()
    return float((x**4).mean() / (s*s + 1e-12) - 3)

def bands_fft(L, ppm, oct=OCT):
    """Periodic band-pass images by wavelength (m). Band RMS is not normalised here."""
    h, w = L.shape
    F = np.fft.rfft2(L - L.mean())
    fy = np.fft.fftfreq(h, 1/ppm)[:, None]; fx = np.fft.rfftfreq(w, 1/ppm)[None, :]
    f = np.sqrt(fx**2 + fy**2)
    out = []
    for a, b in oct:
        m = (f >= 1/b) & (f < 1/a)
        out.append(np.fft.irfft2(F*m, s=(h, w)))
    return out

def grad(L):
    gx = (np.roll(L,-1,1)-np.roll(L,1,1))/2; gy = (np.roll(L,-1,0)-np.roll(L,1,0))/2
    return np.hypot(gx, gy)

def map_metrics(alb, nrm, ids, dist, ppm):
    """alb: band A albedo sRGB; nrm: band A normal map 0..1; ids stone id; dist distance to joint, m."""
    L = alb @ LUM
    mean = L.mean()
    it = dist > 0.03            # stone interior
    jt = dist < 0.015
    r = dict(mean=float(mean), std_rel=float(L.std()/mean))
    B = bands_fft(L, ppm)
    r['band_all'] = [float(b.std()/mean) for b in B]
    r['band_interior'] = [float(b[it].std()/mean) for b in B]
    r['kurt_interior'] = [kurt(b[it]) for b in B]
    n = ids.max()+1
    fl = ids[it]; lv = L[it]
    cnt = np.bincount(fl, minlength=n).astype(float); s = np.bincount(fl, lv, n)
    ok = cnt > 50
    me = s[ok]/cnt[ok]
    within = (lv - (s/np.maximum(cnt,1))[fl]).var()
    between = float(np.average((me-lv.mean())**2, weights=cnt[ok]))
    r['between_std_rel'] = float(np.sqrt(between)/mean); r['within_std_rel'] = float(np.sqrt(within)/mean)
    r['between_over_within'] = float(between/within)
    # neighbour step: mean |difference| of mean value between adjacent stones = "checker" strength, sampled across joints
    hmask = ids != np.roll(ids,-1,1)
    vmask = ids != np.roll(ids,-1,0)
    m2 = np.where(ok)[0]; mm = np.zeros(n); mm[m2] = s[ok]/cnt[ok]
    d = np.concatenate([np.abs(mm[ids[hmask]]-mm[np.roll(ids,-1,1)[hmask]]), np.abs(mm[ids[vmask]]-mm[np.roll(ids,-1,0)[vmask]])])
    r['neighbour_step_rel'] = float(d.mean()/mean)
    # joint profile: mean value by distance from joint
    edges = np.arange(0, 0.0805, 0.002)
    bin_ = np.digitize(dist.ravel(), edges)
    prof = np.bincount(bin_, L.ravel(), len(edges)+1)[1:len(edges)]/np.maximum(np.bincount(bin_, minlength=len(edges)+1)[1:len(edges)],1)
    lo, hi = prof.min(), prof[-5:].mean()
    p = (prof-lo)/(hi-lo+1e-9)
    k0 = int(np.argmin(prof))
    k10 = k0 + int(np.argmax(p[k0:]>=0.1)); k90 = k0 + int(np.argmax(p[k0:]>=0.9))
    r['joint_depth_rel'] = float((hi-lo)/hi); r['joint_rise_10_90_cm'] = float((k90-k10)*0.2)
    # acutance: mean gradient per mm, at the joint band vs interior
    g = grad(L)*ppm/1000/mean
    r['grad_joint'] = float(g[jt].mean()); r['grad_interior'] = float(g[it].mean())
    r['grad_interior_p99'] = float(np.percentile(g[it], 99))
    r['edge_density_interior'] = float((g[it] > 0.02).mean())
    # normals
    sl = np.hypot(nrm[...,0]-.5, nrm[...,1]-.5)*2
    r['slope_rms_all'] = float(np.sqrt((sl**2).mean())); r['slope_rms_interior'] = float(np.sqrt((sl[it]**2).mean())); r['slope_rms_joint'] = float(np.sqrt((sl[jt]**2).mean()))
    nb = bands_fft(nrm[...,0]-nrm[...,0].mean(), ppm)
    r['normal_band_interior'] = [float(b[it].std()) for b in nb]
    return r

def px_bands(L, n=5):
    """Octave DoG in pixels (reflect padded). returns list of band images, wavelengths ~ 2-4, 4-8, 8-16, 16-32, 32-64 px."""
    def blur(a, s):
        if s <= 0: return a
        r = int(4*s)+2
        p = np.pad(a, r, mode='reflect'); h, w = p.shape
        fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.rfftfreq(w)[None, :]
        return np.fft.irfft2(np.fft.rfft2(p)*np.exp(-2*(np.pi*s)**2*(fx**2+fy**2)), s=(h, w))[r:-r, r:-r]
    prev = L; out = []
    for i in range(n):
        s = 0.6*2**i
        cur = blur(L, s)
        out.append(prev-cur); prev = cur
    return out

def crop_metrics(rgb, gamma_already=True):
    L = rgb @ LUM
    mean = float(L.mean())
    r = dict(mean=mean, p5=float(np.percentile(L,5)), p50=float(np.percentile(L,50)), p95=float(np.percentile(L,95)))
    B = px_bands(L)
    r['bands'] = [float(b.std()/mean) for b in B]
    r['kurt'] = [kurt(b) for b in B]
    g = grad(L)[2:-2, 2:-2]/mean
    r['grad_mean'] = float(g.mean()); r['grad_p95'] = float(np.percentile(g,95)); r['grad_p99'] = float(np.percentile(g,99))
    r['edge_density'] = float((g > 0.04).mean())
    r['lap_var'] = float(((np.roll(L,1,0)+np.roll(L,-1,0)+np.roll(L,1,1)+np.roll(L,-1,1)-4*L)[2:-2,2:-2]/mean).var())
    # slope of log band energy vs octave (spectral slope)
    e = np.log2(np.array(r['bands'])+1e-9)
    r['slope'] = float(np.polyfit(np.arange(len(e)), e, 1)[0])
    # fine/coarse: energy at 2-8 px vs 16-64 px: crispness vs cloudiness
    r['fine_over_coarse'] = float((r['bands'][0]**2+r['bands'][1]**2)**.5/((r['bands'][3]**2+r['bands'][4]**2)**.5+1e-9))
    return r
