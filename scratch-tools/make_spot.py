"""Rich Home screen with a chosen first Spotlight trader. make_spot.py BAL GAIN HANDLE AMOUNT out.png"""
import sys, subprocess
from PIL import Image, ImageDraw, ImageFont
F='/usr/share/fonts/opentype/inter/'
bal,gain,handle,amt,out=sys.argv[1:6]
subprocess.run([sys.executable,'-I','make_home.py',bal,gain,out],check=True,capture_output=True)
im=Image.open(out).convert('RGB'); d=ImageDraw.Draw(im)
card=im.getpixel((200,395))
d.rectangle((44,330,352,378),fill=card)        # avatar + handle row
d.rectangle((44,400,352,458),fill=card)        # coin + amount row
d.ellipse((48,336,84,372),fill=(235,235,245))  # ghost avatar
d.ellipse((56,346,64,356),fill=(20,20,30)); d.ellipse((68,346,76,356),fill=(20,20,30))
f=ImageFont.truetype(F+'Inter-SemiBold.otf',25)
d.text((96,339),'@'+handle,font=f,fill=(225,225,232))
d.ellipse((48,406,100,456),fill=(124,77,255)); d.text((74,431),'G',font=ImageFont.truetype(F+'Inter-Bold.otf',26),fill='white',anchor='mm')
d.text((114,412),amt,font=ImageFont.truetype(F+'Inter-SemiBold.otf',28),fill=(76,175,80))
im.save(out); print(out)
