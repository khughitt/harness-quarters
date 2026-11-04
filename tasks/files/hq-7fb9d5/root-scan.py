import json,os,time
from pathlib import Path
from datetime import datetime
out=Path(os.environ['WORK_ROOT'])/'hq/hq-7fb9d5'
cut=datetime.fromisoformat('2026-11-01T00:00:00+00:00').timestamp(); rows=[]; files=0;bad=0;start=time.time()
for h,home,pat in [('claude-code','.claude','projects/*/*.jsonl'),('claude-code','.claude-work','projects/*/*.jsonl'),('codex','.codex','sessions/**/*.jsonl'),('codex','.codex','archived_sessions/*.jsonl'),('codex','.codex-work','sessions/**/*.jsonl'),('codex','.codex-work','archived_sessions/*.jsonl')]:
 for p in (Path.home()/home).glob(pat):
  if p.stat().st_mtime<cut:continue
  with p.open(errors='replace') as f:
   first=json.loads(next(f));meta=first.get('payload',{}) if h=='codex' else first
   if h=='codex' and (meta.get('agent_id') or meta.get('thread_source','user')!='user' or isinstance(meta.get('source'),dict)):continue
   files+=1
   for n,line in enumerate(f,2):
    low=line.lower()
    if not any(w in low for w in ['paus','budget','limit','compact','halt','stopp']):continue
    try:r=json.loads(line)
    except ValueError:bad+=1;continue
    stamp=r.get('timestamp','')
    if stamp and stamp<'2026-11-01':continue
    if h=='codex':
     q=r.get('payload',{})
     if r.get('type')!='response_item' or q.get('type')!='message' or q.get('role') not in ['assistant','developer']:continue
     kind=q['role'];c=q.get('content',[])
    else:
     if r.get('type')!='assistant':continue
     kind='assistant';c=r.get('message',{}).get('content',[])
    t=c if isinstance(c,str) else '\n'.join(b.get('text','') for b in c if isinstance(b,dict))
    if t and any(w in t.lower() for w in ['paus','budget','limit','compact','halt','stopp']): rows.append(dict(harness=h,path=str(p),line=n,timestamp=stamp,kind=kind,text=t))
(out/'root-matches.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(dict(files=files,rows=len(rows),bad=bad,seconds=time.time()-start)))
for r in rows:
 t=r['text']
 if any(w in t.lower() for w in ['paused at','stopped at','parked after','turn-pause:','turn limit','16-minute','budget:','30-agent','turn-pause hook halted','turn-pause hook ended','stopped partway']):
  print(Path(r['path']).stem,r['line'],r['timestamp'],t[-1200:].replace('\n',' '))
