"""Contrast check for docs/design/redesign/phase3/tokens.css (WCAG 2.2 AA). Run: python3 contrast.py"""
def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
    la,lb=sorted([lum(a),lum(b)],reverse=True); return (la+0.05)/(lb+0.05)
D=dict(bg='#0B0B0D',surface='#151517',s2='#1E1E21',s3='#28282C',border='#2A2A2F',bstrong='#64646E',text='#F3F2EF',muted='#A3A1A9',faint='#6E6C75',
 accent='#F4A940',on='#1B1206',asoft='#2E2414',atext='#F7C27A',ok='#5BD08A',oksoft='#12261A',warn='#F2C14E',warnsoft='#2A2312',danger='#FF8A7E',dsoft='#33191A',focus='#F7C27A',
 dis_bg='#26262A',dis_text='#8E8C95',aborder='#F4A940')
L=dict(bg='#F5F3EE',surface='#FFFFFF',s2='#EFECE5',s3='#E6E2D9',border='#E2DED5',bstrong='#8F8A81',text='#1C1B19',muted='#5E5B55',faint='#8A867E',
 accent='#F4A940',on='#1B1206',asoft='#FCEFD9',atext='#8A4B00',ok='#1F7A3D',oksoft='#E4F3E8',warn='#8A5A00',warnsoft='#FCF0DC',danger='#B42318',dsoft='#FDE8E6',focus='#B45F06',
 dis_bg='#E6E2D9',dis_text='#5E5B55',aborder='#B8740F')
checks=[('text','bg',4.5),('text','surface',4.5),('text','s2',4.5),('muted','bg',4.5),('muted','surface',4.5),('muted','s2',4.5),('muted','s3',4.5),
 ('on','accent',4.5),('atext','asoft',4.5),('atext','surface',4.5),('ok','oksoft',4.5),('ok','surface',4.5),('warn','warnsoft',4.5),('danger','dsoft',4.5),('danger','surface',4.5),
 ('bstrong','surface',3),('focus','bg',3),('focus','surface',3),('aborder','bg',3),('dis_text','dis_bg',4.5)]
for name,P in (('DARK',D),('LIGHT',L)):
    print(name)
    for a,b,need in checks:
        r=cr(P[a],P[b]); print(f'  {a:9} on {b:8} {r:5.2f} {"ok" if r>=need else "FAIL"} (needs {need})')
