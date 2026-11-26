#!/usr/bin/env python3
"""Explicitly authorized metadata preflight and bounded cleanup; never automatic."""
import argparse,datetime,json,os,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite import final_cleanup as cleanup
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
 if os.geteuid()!=0:p.error('Global process/private metadata preflight requires separately approved root execution')
 report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deleted':[],'status':'preflight','plan_sha256':a.plan_sha256,'resource_checks':[]}
 fd,name=tempfile.mkstemp(prefix='limpeza-controlada-',suffix='.json',dir=ROOT/'docs/evidencias')
 try:
  paths=cleanup.validate_plan(a.plan,a.plan_sha256)
  cleanup.resources_clear(paths,report['resource_checks'])
  identities,size=cleanup.inventory(paths);report['unique_allocated_bytes']=size;report['entries']=len(identities)
  cleanup.verify_sources()
  cleanup.resources_clear(paths,report['resource_checks'])
  if a.execute_authorized:
   # Record progress even if a later candidate fails; no rollback claim.
   for path in paths:
    report['deleted']+=cleanup.delete_paths([path],identities)
    report['status']='cleaning'
    with open(name,'w') as stream:json.dump(report,stream,indent=2);stream.write('\n')
   report['status']='completed'
  else:report['status']='audit_only'
 except BaseException as error:
  report.update(status='stopped',error=str(error))
  if isinstance(error,cleanup.ResourceBlocked):report['resource_block']=error.evidence
  raise
 finally:
  import shutil
  report['free_bytes_after']=shutil.disk_usage(ROOT).free
  os.close(fd)
  with open(name,'w') as stream:json.dump(report,stream,indent=2);stream.write('\n')
  os.chmod(name,0o444);print(name)
