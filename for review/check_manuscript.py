#!/usr/bin/env python3
"""
check_manuscript.py — verify every table cell in the manuscript against DATA_REFERENCE.md

    python analysis/data_reference.py > docs/DATA_REFERENCE.md
    python analysis/check_manuscript.py manuscript.docx

Reads the docx tables directly and compares cell by cell. Run after any edit.
"""
import sys, re, zipfile, os
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ref=open(os.path.join(HERE,'docs','DATA_REFERENCE.md'),encoding='utf-8').read()
docx=sys.argv[1] if len(sys.argv)>1 else os.path.join(HERE,'manuscript.docx')
xml=zipfile.ZipFile(docx).read('word/document.xml').decode('utf-8')
def norm(s): return s.replace('\u2212','-').replace('\u2011','-').strip()
tables=[[[norm(re.sub(r'<[^>]+>','',c)) for c in re.findall(r'<w:tc>.*?</w:tc>',tr,re.S)]
         for tr in re.findall(r'<w:tr[^>]*>.*?</w:tr>', m.group(0), re.S)]
        for m in re.finditer(r'<w:tbl>.*?</w:tbl>', xml, re.S)]
def ref_rows(a,b):
    i=ref.find(a); j=ref.find(b,i)
    return [[norm(c) for c in l.strip('|').split('|')]
            for l in ref[i:j].splitlines() if l.startswith('| ') and not l.startswith('|---')][1:]
T=B=0
def check(doc, rmap, cols, label):
    global T,B
    bad=chk=0
    for row in doc:
        if len(row)<3: continue
        key=(row[0],row[1])
        if key not in rmap: continue
        r=rmap[key]
        for di,ri,lab in cols:
            if di>=len(row) or ri>=len(r): continue
            dv,rv=row[di],r[ri]
            if not dv or dv in ('—','-') or rv in ('—','-'): continue
            chk+=1
            if dv!=rv: bad+=1; print(f"  MISMATCH {label} {key[0]}/{key[1]} {lab}: manuscript={dv} reference={rv}")
    print(f"  {label:16} {chk:4} cells  {bad} mismatch"); T+=chk; B+=bad
def find(pred):
    m=[t for t in tables if pred(t)]
    return m[0] if m else None
t=find(lambda t: len(t)==30 and t[0][:2]==['Model','Format'])
if t: check(t,{(r[0],r[1]):r for r in ref_rows('## §4.2','## §4.5 — Experiment 2, large')},
            [(2,3,'h'),(3,4,'s'),(4,5,'c'),(5,6,'η'),(6,7,'Δh')],'Table 3')
t=find(lambda t: len(t)==18 and 'Cohen d' in t[0])
if t: check(t,{(r[0],r[1]):r for r in ref_rows('## §4.5 — Experiment 2, large','## §4.5 — Experiment 2, small')},
            [(2,3,'h'),(3,7,'Δh'),(4,8,'d')],'Table 8 large')
t=find(lambda t: len(t)==12 and 'Cohen d' in t[0])
if t: check(t,{(r[0],r[1]):r for r in ref_rows('## §4.5 — Experiment 2, small','## §4.6')},
            [(2,3,'h'),(3,7,'Δh'),(4,8,'d')],'Table 8 small')
t=find(lambda t: len(t)==14 and 'Cohen d' in t[0])
if t: check(t,{(r[0],r[1]):r for r in ref_rows('## §4.6','## §4.5.6')},
            [(2,3,'h'),(3,7,'Δh'),(4,8,'d')],'Table 11')
t=find(lambda t: t[0][:2]==['Model','Baseline'])
if t:
    cur=None; fixed=[]
    for row in t:
        if row[0]: cur=row[0]
        fixed.append([cur]+row[1:])
    rmap={(r[0],r[1]):r for r in ref_rows('### Hybrid minus each baseline','### Mean h by condition')}
    bad=chk=0
    for row in fixed[1:]:
        b=row[1].split('·')[0].strip(); key=(row[0],'Baseline '+b)
        if key not in rmap: continue
        r=rmap[key]
        for di,ri,lab in [(3,3,'h hyb'),(4,4,'h base'),(5,5,'Δh'),(6,6,'d')]:
            chk+=1
            if row[di]!=r[ri]: bad+=1; print(f"  MISMATCH Table 12 {key} {lab}: manuscript={row[di]} reference={r[ri]}")
    print(f"  {'Table 12':16} {chk:4} cells  {bad} mismatch"); T+=chk; B+=bad
print(f"\n  {T} cells checked, {B} mismatches")
sys.exit(1 if B else 0)
