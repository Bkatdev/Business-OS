from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
base=(ROOT/'templates/base.html').read_text(encoding='utf-8')
loaded=re.findall(r"filename='([^']+\.css)'",base)
print('Global CSS chain:', ' -> '.join(loaded))
assert 'v22_product.css' not in loaded and 'v23_product.css' not in loaded
inline=[]
for p in (ROOT/'templates').glob('*.html'):
    for n,line in enumerate(p.read_text(encoding='utf-8',errors='ignore').splitlines(),1):
        if re.search(r'style=["\'][^"\']*(?:color|background)\s*:',line,re.I): inline.append((p.name,n))
print('Inline color/background declarations:', len(inline), inline[:10])
assert len(inline)==0, 'Inline product color declarations remain'
v15=(ROOT/'static/v15.css').read_text(encoding='utf-8')
important=len(re.findall(r'!important',v15))
print('v15.css !important count:',important,'(legacy compatibility baseline; do not increase casually)')
assert '--bos-primary:#2563eb' in v15 and '--bos-success:#15803d' in v15
print('PASS V24 static UI drift audit')
