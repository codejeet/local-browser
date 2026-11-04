"""Compose store screenshots from the real packaged-browser smoke captures."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT.parent/'artifacts';OUT=ROOT/'docs/store'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def text(d,xy,s,size=22,color='#c4d8bd',bold=False):d.text(xy,s,font=ImageFont.truetype(BOLD if bold else FONT,size),fill=color,spacing=12)
def slide(name,title,body,source,label):
 im=Image.new('RGB',(1280,800),'#143e30');d=ImageDraw.Draw(im)
 d.ellipse((-300,520,770,1390),fill='#1a4835')
 logo=Image.open(ROOT/'extension/icons/icon128.png');im.paste(logo,(46,48),logo)
 text(d,(176,89),'LOCAL BROWSER',23,'#b6e57c',True)
 text(d,(72,234),title,46,'#f4f8ea',True)
 text(d,(75,420),body,23)
 text(d,(75,678),label,17,'#b6e57c')
 shot=Image.open(RAW/source).convert('RGB')
 # Actual captured UI, not a mockup. Fit without losing any controls.
 if shot.height>710:shot=shot.resize((round(shot.width*710/shot.height),710),Image.Resampling.LANCZOS)
 x=1280-76-shot.width;y=(800-shot.height)//2
 d.rounded_rectangle((x-10,y-10,x+shot.width+10,y+shot.height+10),radius=20,fill='#4c7454')
 im.paste(shot,(x,y));im.save(OUT/name)
slide('screenshot-connected.png','Give your agent\nyour real browser.','Read pages, fill forms and capture\nscreenshots in the Chrome profile\nyou already use.','connected-ui.png','Works with Hermes Agent and MCP clients')
slide('screenshot-setup.png','Put your browser\nto work.','Pair with your own relay, then\ngive your agent a browser task.\nYour logins stay in Chrome.','setup-ui.png','Python relay + MCP setup required')
slide('screenshot-paused.png','Pause when\nyou need to.','Stop new browser commands\nfrom the extension. Resume\nwhen you’re ready.','paused-ui.png','Your connection stays under your control')
Image.open(RAW/'workflow.png').convert('RGB').save(OUT/'screenshot-workflow.png')
