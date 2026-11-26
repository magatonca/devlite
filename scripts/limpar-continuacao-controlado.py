#!/usr/bin/env python3
"""One-shot exact manifest cleanup. Root execution requires separate approval."""
import argparse,datetime,hashlib,json,os,shutil,sys
from pathlib import Path
ROOT=Path('/home/magaton/DevLite-OS')
sys.path.insert(0,str(ROOT/'pipeline'))
from devlite.final_cleanup import inventory,resources_clear,delete_paths
from devlite.cleanup_eight import canonical,memory_references,verify_hashes,fingerprint,project_metadata

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(plan,expected,removed=()):
    canonical(plan)
    if sha(plan)!=expected:raise ValueError('Plan changed')
    data=json.loads(plan.read_text())
    if data['operation']!='continuacao-exact-43' or len(data['candidates'])!=43:raise ValueError('Scope mismatch')
    if any(sha(ROOT/p)!=h for p,h in data['code_sha256'].items()):raise ValueError('Code changed')
    paths=[Path(c['path']) for c in data['candidates']]
    if len(set(paths))!=43:raise ValueError('Duplicate paths')
    for p in paths:
        if ROOT not in p.parents:raise ValueError('Outside project')
        if str(p) not in removed:canonical(p);canonical(p.parent)
    if any(a in b.parents for a in paths for b in paths):raise ValueError('Overlapping paths')
    for preserved in data['protected_sha256']:
        q=ROOT/preserved
        if any(q==p or p in q.parents for p in paths):raise ValueError('Protected overlap')
    return data,paths

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--execute-authorized',action='store_true');a=ap.parse_args()
    if not a.execute_authorized or os.geteuid()!=0:raise ValueError('Separate approved root execution required')
    data,paths=load(a.plan,a.sha256)
    report_path=a.plan.parent/'execution.json'
    fd=os.open(report_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    report={'status':'preflight','removed':[],'resources':[],'mappings':[],'free_before':shutil.disk_usage(ROOT).free,'plan_sha256':a.sha256}
    def save():
        raw=(json.dumps(report,indent=2)+'\n').encode();os.lseek(fd,0,0);os.ftruncate(fd,0);os.write(fd,raw);os.fsync(fd)
    try:
        resources_clear(paths,report['resources']);memory_references(paths,report['mappings'])
        identities,size=inventory(paths)
        for path in paths:
            for name in inventory([path])[0]:
                q=Path(name)
                if q.is_symlink() or not(q.is_dir() or q.is_file()):raise ValueError('Unexpected file type: '+name)
        file_bytes=sum(Path(name).lstat().st_blocks*512 for name in identities if Path(name).is_file())
        if file_bytes!=data['recoverable_bytes']:raise ValueError('Candidate allocated size changed')
        verify_hashes(ROOT,data['protected_sha256'],report)
        for c in data['candidates']:
            q=Path(c['path'])
            if q.is_dir():
                if sorted(x.name for x in q.iterdir())!=['minimal.live.squashfs','minimal.squashfs']:raise ValueError('Unexpected packed contents')
                for f in q.iterdir():
                    if sha(f)!=sha(Path(c['preserve'])/f.name):raise ValueError('SquashFS duplicate differs')
            elif c.get('canonical') or (c.get('preserve','').endswith('.squashfs')):
                target=Path(c.get('canonical') or c['preserve'])
                value=sha(q)
                if value!=sha(target) or ('sha256' in c and value!=c['sha256']):raise ValueError('Duplicate differs: '+str(q))
            elif sha(q)!='7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db':raise ValueError('Historical ISO changed')
        before=project_metadata(ROOT,paths+[a.plan.parent])
        report['status']='preflight_passed';report['allocated_bytes']=size;save()
        for q in paths:
            load(a.plan,a.sha256,report['removed'])
            resources_clear(paths,report['resources']);memory_references(paths,report['mappings'])
            report['current_item']=str(q);save()
            report['removed']+=delete_paths([q],identities);save()
            # Removed paths are allowed in resource checks but load needs existing roots.
            # Subsequent checks below use sealed scope without re-resolving deleted roots.
        if project_metadata(ROOT,[a.plan.parent])!=before:raise ValueError('Unexpected preserved metadata change')
        if any(fingerprint(p)!=v for p,v in report['protected_verified_metadata'].items()):raise ValueError('Protected artifact changed')
        verify_hashes(ROOT,{p:h for p,h in data['protected_sha256'].items() if '/published-casper/' in p or p.endswith('.squashfs')}, {})
        report['status']='completed';report['preserved_metadata_unchanged']=True
    except BaseException as e:
        report['status']='stopped';report['error']=str(e);raise
    finally:
        report['free_after']=shutil.disk_usage(ROOT).free;report['recovered_bytes']=report['free_after']-report['free_before'];save();os.fchmod(fd,0o444);os.close(fd)
if __name__=='__main__':main()
