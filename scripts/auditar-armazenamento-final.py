#!/usr/bin/env python3
"""Somente inventaria. Não contém rotina de limpeza ou opção de remoção."""
import argparse,json,os,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.final_storage import scan,usage,subset,candidate
from pipeline.devlite.runtime import owned_directory

def main():
 if os.geteuid()==0 or os.getuid()!=1000:raise ValueError('Executar como magaton')
 work=owned_directory(ROOT/'work','final-storage-');rows,errors=scan(ROOT)
 (work/'inventory.json').write_text(json.dumps(rows,ensure_ascii=False)+'\n')
 groups={}
 for row in rows:
  relative=Path(row['path']).relative_to(ROOT);parts=relative.parts
  name='/'.join(parts[:2]) if parts and parts[0] in ('work','artifacts') else (parts[0] if parts else '.')
  groups.setdefault(name,[]).append(row)
 sizes=sorted([{'path':str(ROOT/name),**usage(values)} for name,values in groups.items()],key=lambda i:i['allocated_bytes'],reverse=True)
 for group in sizes:
  path=Path(group['path']);blocked=[e for e in errors if Path(e['path'])==path or path in Path(e['path']).parents];group['complete_inventory']=not blocked
  if blocked:group['reclaimable_bytes_if_all_listed_paths_removed']=None;group['allocated_bytes_are_lower_bound']=True
 candidates=[]
 job=ROOT/'work/release-63m6oz2_'
 for logs in sorted(job.glob('iso-*/logs')):
  for name in ('source-tree','result-tree'):
   path=logs.parent/name
   if path.is_dir():candidates.append(candidate(rows,errors,path,'Árvore externa de auditoria regenerável pelas ISOs preservadas; logs/relatórios fora do candidato','Perde a cópia extraída; reextrair sob autorização se necessária'))
 older=ROOT/'work/phase3b-frka50es'
 for name in ('source-tree','result-tree'):
  path=older/name
  if path.is_dir():candidates.append(candidate(rows,errors,path,'Árvore de auditoria antiga 3B, com ISOs/fontes e inventários preservados','Perde cópia extraída; confirmar que nenhum contrato ativo a usa'))
 path=ROOT/'work/phase3b-reproduction-jvzarclv/reproduced.iso'
 if path.is_file():candidates.append(candidate(rows,errors,path,'Reprodução histórica 3B; relatório de reprodução e ISO experimental 3B preservados','Remover somente após revalidar a igualdade por SHA-256 com a referência'))
 path=ROOT/'artifacts/release-22snj8_v/devlite-os-1.0-ubuntu-experimental.iso'
 if path.is_file():candidates.append(candidate(rows,errors,path,'Segunda ISO bit a bit idêntica; principal e prova de reprodução preservadas','Opcional: perde segunda cópia física; preservar se desejada para auditoria'))
 result={'status':'read_only_audit_with_access_limits' if errors else 'read_only_audit_complete','uid':os.getuid(),'workspace':str(work),'project_usage_lower_bound':usage(rows),'largest_groups':sizes[:25],'access_errors':errors,'candidates':candidates,'free_bytes':shutil.disk_usage(ROOT).free,'deleted':False,'approved_for_cleanup':False,'scope_note':'Blocos reais e hardlinks considerados. Diretórios privados inacessíveis não são estimados como vazios; consumo total é limite inferior. Grupos podem compartilhar inodes; não somar seus totais cegamente.'}
 (work/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'docs/evidencias/auditoria-armazenamento-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'largest_groups':sizes[:15],'candidates':candidates,'access_errors':len(errors),'free_GiB':result['free_bytes']/2**30},ensure_ascii=False,indent=2))
if __name__=='__main__':
 argparse.ArgumentParser(description=__doc__).parse_args();main()
