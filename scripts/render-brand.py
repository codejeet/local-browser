"""Render the Local Browser brand mark at extension and store sizes."""
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
def icon(size):
    im=Image.new('RGBA',(512,512));d=ImageDraw.Draw(im)
    d.rounded_rectangle((64,64,448,448),radius=95,fill='#215d43')
    d.rounded_rectangle((121,139,389,346),radius=27,fill='#e9f4d9')
    d.rounded_rectangle((139,180,371,328),radius=11,fill='#215d43')
    for x in (145,163,181):d.ellipse((x,155,x+8,163),fill='#215d43')
    d.line((207,218,180,249,207,278),fill='#b6e57c',width=14,joint='curve')
    d.line((290,218,317,249,290,278),fill='#b6e57c',width=14,joint='curve')
    d.polygon([(278,284),(290,398),(316,368),(351,402),(373,380),(337,347),(376,335)],fill='#b6e57c',outline='#215d43',width=6)
    return im.resize((size,size),Image.Resampling.LANCZOS)
if __name__=='__main__':
    out=ROOT/'extension/icons';out.mkdir(parents=True,exist_ok=True)
    for n in (16,32,48,128):icon(n).save(out/f'icon{n}.png')
    out=ROOT/'docs/store';out.mkdir(parents=True,exist_ok=True)
    icon(128).save(out/'store-icon.png')
    for name,w,h in [('promo-small',440,280),('promo-marquee',1400,560)]:
        im=Image.new('RGB',(w,h),'#143e30');d=ImageDraw.Draw(im)
        # Quiet connected-browser motif, readable without promotional text.
        scale=h/280
        for side in (-1,1):
            x=w/2+side*h*.73; y=h*.48; bw=h*.60;bh=h*.43
            d.rounded_rectangle((x-bw/2,y-bh/2,x+bw/2,y+bh/2),radius=int(14*scale),fill='#235b43',outline='#4c8a60',width=max(1,int(scale)))
            d.line((x-bw/2,y-bh*.24,x+bw/2,y-bh*.24),fill='#4c8a60',width=max(1,int(scale)))
            d.line((w/2,y,x,y),fill='#a9d87b',width=int(3*scale))
            for n in range(3):d.rounded_rectangle((x-bw*.34,y+bh*(n*.17-.08),x+bw*(.28 if n!=1 else .1),y+bh*(n*.17-.05)),radius=2,fill='#77a36a')
        logo=icon(int(h*.83));im.paste(logo,(int((w-logo.width)/2),int((h-logo.height)/2)),logo)
        im.save(out/f'{name}.png')
