import json, os, re, sys, time
from pathlib import Path
from datetime import datetime, timezone
SINCE='2026-11-01T00:00:00Z'
cut=datetime.fromisoformat(SINCE.replace('Z','+00:00')).timestamp()
# Only extract actual assistant messages/tool results, never injected instructions or tool inputs.
patterns=re.compile(r'turn paused|turn-pause:|pause report|pause-report|30.agent limit|500.call|compaction limit|past (?:its|the) range|turn limit|pause budget|budget: (?:[0-9]+h)',re.I)
def parts(r,h):
    if h=='codex':
        p=r.get('payload',{})
        if r.get('type')=='response_item' and p.get('type')=='message' and p.get('role')=='assistant':
            return 'assistant', '\n'.join(b.get('text','') for b in p.get('content',[]) if isinstance(b,dict))
        if r.get('type')=='response_item' and p.get('type') in ('function_call_output','custom_tool_call_output'):
            return 'result',str(p.get('output',''))
        return '', ''
    if r.get('type')=='assistant':
        c=r.get('message',{}).get('content',[])
        return 'assistant','\n'.join(b.get('text','') for b in c if isinstance(b,dict) and b.get('type')=='text') if isinstance(c,list) else c
    if r.get('type')=='user':
        c=r.get('message',{}).get('content',[])
        return 'result','\n'.join(str(b.get('content','')) for b in c if isinstance(b,dict) and b.get('type')=='tool_result') if isinstance(c,list) else ''
    if r.get('type')=='attachment': return 'attachment',str(r.get('attachment',''))
    return '', ''
assert parts({'type':'response_item','payload':{'type':'message','role':'user','content':[{'text':'turn paused'}]}},'codex')==('','')
assert parts({'type':'assistant','message':{'content':[{'type':'tool_use','input':'turn paused'}]}},'claude-code')==('assistant','')
out=Path(os.environ['WORK_ROOT'])/'hq/hq-7fb9d5'
files=[]
for h,home in [('claude-code','.claude'),('claude-code','.claude-work'),('codex','.codex'),('codex','.codex-work')]:
    root=Path.home()/home
    globs=['projects/**/*.jsonl'] if h=='claude-code' else ['sessions/**/*.jsonl','archived_sessions/*.jsonl']
    for g in globs:
        for p in root.glob(g):
            if p.stat().st_mtime>=cut: files.append((h,p))
rows=[]; errors=[]; total=0; start=time.time()
for h,p in files:
    meta={}; bad=0
    with p.open(errors='replace') as f:
        for n,line in enumerate(f,1):
            total+=len(line)
            if n==1:
                try:
                    r=json.loads(line);meta=r.get('payload',{}) if h=='codex' else r
                except ValueError: pass
            if not patterns.search(line): continue
            try:r=json.loads(line)
            except ValueError: bad+=1;continue
            ts=r.get('timestamp','')
            if ts and ts<SINCE: continue
            kind,t=parts(r,h)
            if t and patterns.search(t):
                rows.append(dict(harness=h,path=str(p),line=n,timestamp=ts,kind=kind,session=meta.get('id',p.stem),cwd=meta.get('cwd'),source=meta.get('source'),text=t))
    if bad:errors.append([str(p),bad])
(out/'matches.json').write_text(json.dumps(rows,indent=2))
summary=dict(since=SINCE,files=len(files),files_by_harness={h:sum(a==h for a,b in files) for h in ['claude-code','codex']},matches=len(rows),matched_files=len(set(r['path'] for r in rows)),bytes=total,seconds=round(time.time()-start,2),parse_errors_on_matching_lines=errors)
(out/'scan-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
from collections import defaultdict
by=defaultdict(list)
for r in rows: by[r['path']].append(r)
for p,rs in by.items():
    print(rs[0]['harness'],p,len(rs))
    for r in rs:
        if r['kind']=='assistant' and re.search(r'paused|stop|park|limit|budget:',r['text'],re.I):
            print(' ',r['line'],r['timestamp'],r['text'][-800:].replace('\n',' ')[:800])
