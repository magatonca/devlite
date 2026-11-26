#!/usr/bin/env python3
"""Prepare, verify readable preserved inputs, or execute the exact eight-path cleanup."""
import argparse,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.cleanup_eight import prepare,read,sha,canonical,execute

def readable_preflight(job,approval):
 if os.geteuid()==0 or os.getuid()!=1000:raise ValueError('Read-only preparation as magaton')
 data=read(job,approval)
 deferred_allowed={name for name in data['protected_sha256'] if name.endswith(('/attempt/base.ext4','/attempt/live.ext4'))}
 verified=[];deferred=[]
 for name,value in data['protected_sha256'].items():
  print('Verificando: '+name,flush=True)
  try:
   p=canonical(ROOT/name)
   if sha(p)!=value:raise ValueError('Preserved hash mismatch: '+name)
   verified.append(name)
  except PermissionError:
   if name not in deferred_allowed:raise
   deferred.append(name)
 result={'status':'readable_inputs_verified_private_checks_pending','verified':verified,
         'deferred_private_images':deferred,'deleted':[],'root_used':False,'plan_sha256':approval}
 with (Path(job)/'readable-preflight.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(Path(job)/'readable-preflight.json')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
 g.add_argument('--prepare',action='store_true');g.add_argument('--verify-readable',action='store_true');g.add_argument('--execute-authorized',action='store_true')
 p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');a=p.parse_args()
 try:
  if a.prepare:
   if a.job or a.approval_sha256:p.error('Preparation creates a new job')
   job,value=prepare();print(job);print(value)
  else:
   if not a.job or not a.approval_sha256:p.error('Job and sealed approval hash required')
   if a.verify_readable:readable_preflight(a.job,a.approval_sha256)
   else:print(execute(a.job,a.approval_sha256,True))
 except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
