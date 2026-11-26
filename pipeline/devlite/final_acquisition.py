"""Acquire only the three pinned public archives after explicit approval."""
import json,os,tempfile,urllib.request
from pathlib import Path
from .final_artifacts import verify
from .final_cleanup import digest
URLS=(
'https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz',
'https://registry.npmjs.org/typescript/-/typescript-7.0.2.tgz',
'https://registry.npmjs.org/@typescript/typescript-linux-x64/-/typescript-linux-x64-7.0.2.tgz')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect not approved; stop acquisition')

def fetch(url,target,expected_size,limit,opener):
 if url not in URLS:raise ValueError('URL outside the three approved official files')
 request=urllib.request.Request(url,headers={'User-Agent':'DevLite-OS/1.0 controlled acquisition','Accept-Encoding':'identity'})
 with opener.open(request,timeout=30) as response:
  if response.geturl()!=url or response.status!=200:raise ValueError('Unexpected response origin/status')
  if response.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Unexpected content encoding')
  declared=response.headers.get('Content-Length')
  if declared is not None:
   declared=int(declared)
   if declared<0 or declared>limit or expected_size is not None and declared!=expected_size:raise ValueError('Response size exceeds approval')
  total=0
  with Path(target).open('xb') as stream:
   while True:
    block=response.read(min(1024*1024,limit-total+1))
    if not block:break
    total+=len(block)
    if total>limit:raise ValueError('Download cap exceeded')
    stream.write(block)
  if declared is not None and total!=declared or expected_size is not None and total!=expected_size:raise ValueError('Truncated/incorrect archive size')
  return total

def acquire(project,expected_plan,authorized=False):
 if not authorized:raise ValueError('Specific program acquisition approval required')
 if os.geteuid()==0:raise ValueError('Download as the normal project user')
 project=Path(project).resolve();plan_path=project/'packages/final-external-plan.json'
 if plan_path.is_symlink() or digest(plan_path)!=expected_plan:raise ValueError('Approved program plan changed')
 plan=json.loads(plan_path.read_text())
 if tuple(x['url'] for x in plan['artifacts'])!=URLS:raise ValueError('Program versions/origins changed')
 work=project/'work'
 if work.is_symlink() or work.stat().st_uid!=os.geteuid():raise ValueError('Unsafe work directory')
 job=Path(tempfile.mkdtemp(prefix='public-acquisition-',dir=work));job.chmod(0o700)
 cache=job/'downloads';cache.mkdir(mode=0o700)
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 report={'status':'acquiring','iso_generated':False,'image_modified':False,'host_packages_installed':False,'plan_sha256':expected_plan,'downloads':[]}
 try:
  remaining=plan['download_cap_bytes']
  for item in plan['artifacts']:
   filename=item['filename']
   if Path(filename).name!=filename or filename in ('','.','..'):raise ValueError('Unsafe archive name')
   temporary=cache/(filename+'.partial')
   print('Acquiring approved archive: '+filename,flush=True)
   size=fetch(item['url'],temporary,item.get('download_bytes'),remaining,opener)
   temporary.rename(cache/filename);remaining-=size
   report['downloads'].append({'file':filename,'url':item['url'],'bytes':size,'sha256':digest(cache/filename)})
  report['verified_artifacts']=verify(plan,cache)
  report['status']='verified_not_installed'
  # Persist the acquisition receipt before a separate local staging job.
  with (job/'acquisition-report.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
  return job
 except BaseException as error:
  report.update(status='quarantined',error=str(error))
  with (job/'acquisition-report.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
  raise
