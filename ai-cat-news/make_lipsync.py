import wave, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE="assets/base.jpg"
AUDIO="voice.wav"
OUT="output/mouth_anim_silent.mp4"
FPS=15

base=Image.open(BASE).convert("RGBA")
W,H=base.size
with wave.open(AUDIO,"rb") as wf:
    sr=wf.getframerate()
    raw=wf.readframes(wf.getnframes())
    x=np.frombuffer(raw,dtype=np.int16).astype(np.float32)/32768.0

duration=len(x)/sr
nframes=math.ceil(duration*FPS)
rms=[]
for i in range(nframes):
    a=int(i*sr/FPS); b=min(len(x),int((i+1)*sr/FPS))
    v=x[a:b]
    rms.append(float(np.sqrt(np.mean(v*v))) if len(v) else 0)
rms=np.asarray(rms)
if len(rms)>=3:
    rms=np.convolve(rms,np.ones(3)/3,mode="same")
lo=np.percentile(rms,25); hi=np.percentile(rms,92)
levels=np.clip((rms-lo)/(hi-lo+1e-6),0,1)
levels=np.where(rms<max(.012,lo*1.1),0,np.sqrt(levels))

cx,cy=285,438
mask=Image.new("L",(W,H),0)
d=ImageDraw.Draw(mask)
d.ellipse((251,421,320,468),fill=255)
mask=mask.filter(ImageFilter.GaussianBlur(5))

cmd=["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast","-crf","21","-pix_fmt","yuv420p",OUT]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)

for lvl in levels:
    img=base.copy()
    if lvl>.05:
        drop=int(1+4*lvl)
        shifted=Image.new("RGBA",(W,H),(0,0,0,0)); shifted.paste(img,(0,drop))
        img=Image.composite(shifted,img,mask)
        ov=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(ov)
        mw=int(10+10*lvl); mh=int(2+8*lvl)
        od.ellipse((cx-mw,cy-1,cx+mw,cy+mh),fill=(48,25,26,int(150+80*lvl)))
        ov=ov.filter(ImageFilter.GaussianBlur(.6))
        img=Image.alpha_composite(img,ov)
    p.stdin.write(np.asarray(img.convert("RGB"),dtype=np.uint8).tobytes())

p.stdin.close()
raise SystemExit(p.wait())
