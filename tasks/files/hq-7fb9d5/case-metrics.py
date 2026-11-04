import sys,os,glob,json,collections
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
from turn_pause import replay
from turn_pause.limits import Limits
cases=[('mm','claude-code','c67f4b5f-818d-4533-83b0-172009b992c2','2026-11-02T19:10:25Z'),('fam','claude-code','f5ed2d6a-dc73-443e-ac25-c0a4357da4cb','2026-11-02T14:04:40Z'),('minutes','codex','01a19f20-a422-75b0-8476-0ed9ba0dd8c9','2026-11-03T09:57:35Z'),('warning-tasks','codex','01a1a10b-15de-7a00-81ba-4469c83141b8','2026-11-03T21:28:45Z'),('combined','codex','01a1a10b-15de-7a00-81ba-4469c83141b8','2026-11-04T01:11:20Z'),('spawn-tasks','codex','01a1a368-49dd-7552-84a0-019d41d3bc0e','2026-11-04T02:21:26Z'),('warning-dots','codex','01a1a0ca-e9f8-7e91-9095-4e88cd515d24','2026-11-04T03:23:25Z')]
children=replay.codex_children(os.environ);output=[]
for label,h,sid,end in cases:
 if h=='codex':
  p=glob.glob(os.path.expanduser('~/.codex/sessions/**/*'+sid+'*'),recursive=True)[0];kids=children.get(sid,[])
  root,steps=replay.read_codex_tree(p,kids,replay.codex_unhooked())
 else:
  p=glob.glob(os.path.expanduser('~/.claude/projects/*/'+sid+'.jsonl'))[0];kids=glob.glob(p[:-6]+'/subagents/*.jsonl');root,steps=replay.read_claude_tree(p,kids)
 # Compare actual old 4h default for first two; unchanged other counters.
 lim=Limits((4 if h=='claude-code' else 16)*3600,500,30,2)
 turns=replay.replay(h,sid,steps,lim,'audit',t1=replay.ts(end),problems=collections.Counter())
 assert turns, label
 t=turns[-1];s=t.state
 row=dict(case=label,harness=h,session=sid,cutoff=end,root_path=p,child_files=len(kids),turn_start=replay.iso(t.start),active_hours=round(s.active/3600,4),calls=s.calls,spawns=s.spawns,counted_compactions=s.compactions,pause=None if not t.pause else t.pause._asdict(),last_usage=None)
 if h=='codex':
  for n,line in enumerate(open(p),1):
   r=json.loads(line)
   if r.get('timestamp','')>=end:continue
   q=r.get('payload',{})
   if q.get('type')=='token_count' and q.get('info'):row['last_usage']=dict(line=n,timestamp=r['timestamp'],total=q['info'].get('total_token_usage'))
 output.append(row)
 print(label,json.dumps({k:v for k,v in row.items() if k not in ['root_path','last_usage']}),row['last_usage'])
Path(os.environ['WORK_ROOT'],'hq/hq-7fb9d5/case-metrics.json').write_text(json.dumps(output,indent=2))
