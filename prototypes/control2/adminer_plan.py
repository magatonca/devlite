"""Adminer planning only: signed metadata and offline APT; no package installer."""
import hashlib,ipaddress,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.customize.installation import snapshot_indexes,installed,compatibility
from pipeline.devlite.browser import resolve_browser,FORBIDDEN

from prototypes.control2.adminer_model import URL,IPV6_URL,LISTEN,APACHE

def prepare():
    if os.geteuid()==0:raise ValueError('Planejar sem root')
    if shutil.disk_usage(ROOT).free<20*1024**3+256*1024**2:raise ValueError('Reserva de disco insuficiente')
    source=ROOT/'work/browser-g2xb9f0m';job=owned_directory(ROOT/'work','adminer-plan-')
    for name in ('logs','empty','lists/partial','cache/archives/partial'):(job/name).mkdir(parents=True,exist_ok=True)
    for name in ('empty.conf','preferences','extended_states'):(job/name).write_text('')
    report={'schema':1,'status':'planning','source':str(source),'installation_executed':False,
      'package_downloaded':False,'release_approved':False,'remote_metadata_requests':False}
    evidence,blockers=snapshot_indexes(job)
    if blockers:raise ValueError('; '.join(blockers))
    report['authenticated_indexes']=evidence
    targets={}
    for view in ('base','live'):
        original=(source/(view+'.status')).read_text()
        target=resolve_browser(job,view,original,['adminer'],FORBIDDEN)
        before=installed(original)
        if any(target['final_versions'].get(k)!=v for k,v in before.items()):raise ValueError('Alteraria pacote homologado')
        if any(i['previous'] is not None for i in target['changes']):raise ValueError('Upgrade não permitido')
        targets[view]=target
    comp=compatibility(targets['base'],targets['live'])
    if comp['base_packages_missing_live'] or comp['common_version_conflicts']:raise ValueError('Divergência Base/Live')
    artifacts={i['filename']:i for t in targets.values() for i in t['changes']}
    report.update(status='dependencies_resolved_security_blocked',targets=targets,reconciliation=comp,
      artifacts=list(artifacts.values()),download_bytes_unique=sum(i['download_bytes'] for i in artifacts.values()),
      source_status_sha256={v:hashlib.sha256((source/(v+'.status')).read_bytes()).hexdigest() for v in ('base','live')},
      security={'review_passed':False,'ubuntu_status':'Needs evaluation',
        'references':['https://ubuntu.com/security/CVE-2025-43960','https://ubuntu.com/security/CVE-2026-56705'],
        'caveat':'Applicability and backports not confirmed; no automatic selection of another source/version'},
      chain_authenticated=True,deb_hash_verified=False,php_mariadb_runtime_tested=False,
      urls={'ipv4':URL,'ipv6':IPV6_URL},free_bytes=shutil.disk_usage(ROOT).free)
    proposal=job/'proposal';proposal.mkdir();(proposal/'ports.conf').write_text(LISTEN)
    (proposal/'devlite-adminer-local.conf').write_text(APACHE)
    (job/'adminer-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return job/'adminer-plan.json'

if __name__=='__main__':print(prepare())
