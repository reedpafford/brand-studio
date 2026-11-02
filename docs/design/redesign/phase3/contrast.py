"""Contrast check for web/src/styles/tokens.css (WCAG 2.2 AA). Run: python3 contrast.py"""
def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
    la,lb=sorted([lum(a),lum(b)],reverse=True); return (la+0.05)/(lb+0.05)
D=dict(bg='#0E0F11',surface='#141518',s2='#1C1D21',s3='#25262B',border='#23252A',bstrong='#666A73',text='#E6E7EA',muted='#8F929B',faint='#5F626B',
 accent='#5E63D6',on='#FFFFFF',asoft='#1F2040',atext='#A9ACF7',ok='#4CB782',oksoft='#13261D',warn='#E2A33B',warnsoft='#2A2214',danger='#EB6E5E',dsoft='#331A18',focus='#8B8FF0',
 dis_bg='#1F2024',dis_text='#8A8D96',aborder='#5E63D6')
L=dict(bg='#FBFBFC',surface='#FFFFFF',s2='#F4F4F6',s3='#EBEBEF',border='#E7E7EA',bstrong='#8B8E97',text='#1B1C1F',muted='#62656E',faint='#9A9DA5',
 accent='#5E63D6',on='#FFFFFF',asoft='#EEF0FF',atext='#4146B8',ok='#1A7A4B',oksoft='#E6F4EC',warn='#8F5C12',warnsoft='#FBF1DF',danger='#C23B2F',dsoft='#FDE9E7',focus='#5E63D6',
 dis_bg='#EBEBEF',dis_text='#62656E',aborder='#5E63D6')
checks=[('text','bg',4.5),('text','surface',4.5),('text','s2',4.5),('muted','bg',4.5),('muted','surface',4.5),('muted','s2',4.5),('muted','s3',4.5),
 ('on','accent',4.5),('atext','asoft',4.5),('atext','surface',4.5),('ok','oksoft',4.5),('ok','surface',4.5),('warn','warnsoft',4.5),('danger','dsoft',4.5),('danger','surface',4.5),
 ('bstrong','surface',3),('focus','bg',3),('focus','surface',3),('aborder','bg',3),('dis_text','dis_bg',4.5)]
for name,P in (('DARK',D),('LIGHT',L)):
    print(name)
    for a,b,need in checks:
        r=cr(P[a],P[b]); print(f'  {a:9} on {b:8} {r:5.2f} {"ok" if r>=need else "FAIL"} (needs {need})')
