"""Prepare an authenticated payload in a new project workspace, never in a rootfs.

No network, mounts, subprocesses, package manager or maintainer scripts. The result
still requires a separately approved isolated application and a new sealed contract.
"""
import hashlib,json,os,shutil,shlex,stat,tarfile,tempfile
from pathlib import Path,PurePosixPath
from .final_artifacts import verify
from .final_archive import inspect

IDS=('node-lts','typescript','@typescript/typescript-linux-x64')

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def relative(value):
    p=PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or str(p)=='.':
        raise ValueError('Unsafe relative destination')
    return p

def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('Regular file required: '+str(path))

def safe_directory(root,rel):
    current=root
    for part in relative(rel).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Symlink ancestor')
        current.mkdir(exist_ok=True)
        if not current.is_dir():raise ValueError('Non-directory ancestor')
    return current

def write_new(root,name,data,mode=0o644):
    rel=relative(name);parent=root if str(rel.parent)=='.' else safe_directory(root,str(rel.parent))
    path=parent/rel.name
    with path.open('xb') as stream:stream.write(data)
    path.chmod(mode)
    return path

def unpack(source,destination,prefix,limit):
    """Inspect first; materialize regular files before internal symlinks."""
    inventory=inspect(source,prefix,limit)
    destination.mkdir(mode=0o755,parents=True,exist_ok=False)
    files=inventory['entries']
    # Extract to a fresh owned tree, no pre-existing symlink ancestors.
    with tarfile.open(source,'r|*') as archive:
        for member in archive:
            name=PurePosixPath(*PurePosixPath(member.name).parts[1:]).as_posix()
            expected=files.get(name)
            if expected is None or expected['archive_member']!=member.name:raise ValueError('Archive changed')
            if expected['type']=='dir':
                if name!='.':safe_directory(destination,name)
            elif expected['type']=='file':
                rel=relative(name);parent=destination if str(rel.parent)=='.' else safe_directory(destination,str(rel.parent))
                target=parent/rel.name
                with archive.extractfile(member) as incoming,target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming,outgoing,1024*1024)
                if target.stat().st_size!=expected['size'] or sha(target)!=expected['sha256']:raise ValueError('Archive payload changed')
                target.chmod(int(expected['mode'],8))
    for name,item in files.items():
        if item['type']=='symlink':
            rel=relative(name);parent=destination if str(rel.parent)=='.' else safe_directory(destination,str(rel.parent))
            (parent/rel.name).symlink_to(item['target'])
    for name,item in files.items():
        if item['type']=='symlink' and not (destination/name).resolve().is_relative_to(destination.resolve()):raise ValueError('Resolved link escapes prefix')
    return inventory

def copy_overlay(project,tree,branding):
    source=project/branding['overlay']
    # Every staged file is pinned. Extra files and symlinks fail closed.
    actual=set()
    for base,dirs,names in os.walk(source,followlinks=False):
        for name in dirs:
            if (Path(base)/name).is_symlink():raise ValueError('Overlay symlink directory')
        for name in names:
            p=Path(base)/name;regular(p);actual.add(p.relative_to(source).as_posix())
    if actual!=set(branding['files']):raise ValueError('Overlay manifest differs')
    for name,item in sorted(branding['files'].items()):
        relative(name);path=source/name
        if item['uid']!=0 or item['gid']!=0 or item['mode'] not in ('0644','0755'):raise ValueError('Unexpected overlay ownership/mode')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Overlay digest differs')
        write_new(tree,name,data,int(item['mode'],8))

def stage(project,cache,plan,branding):
    project=Path(project).resolve();work=project/'work'
    if os.geteuid()==0:raise ValueError('Payload preparation must run as normal project user')
    if work.is_symlink() or work.stat().st_uid!=os.geteuid():raise ValueError('Project work ownership')
    if tuple(i['id'] for i in plan['artifacts'])!=IDS:raise ValueError('Exactly the three public artifacts are required')
    node,ts,native=plan['artifacts'];version=node['version'];tsversion=ts['version']
    if any(not all(c.isdigit() or c=='.' for c in v) or len(v.split('.'))!=3 for v in (version,tsversion)):
        raise ValueError('Unsafe version')
    prefixes=[f'opt/devlite/node/v{version}',f'opt/devlite/typescript/{tsversion}/node_modules/typescript',f'opt/devlite/typescript/{tsversion}/node_modules/@typescript/typescript-linux-x64']
    if native['version']!=tsversion or [i['prefix'].lstrip('/') for i in plan['artifacts']]!=prefixes:
        raise ValueError('Unexpected public prefix/version')
    verify(plan,cache)
    job=Path(tempfile.mkdtemp(prefix='public-payload-',dir=work));job.chmod(0o700)
    state={'status':'preparing','image_modified':False,'programs_executed':False,'application_authorized':False}
    try:
        snapshot=job/'archives';snapshot.mkdir(mode=0o700)
        for item in plan['artifacts']:
            source=Path(cache)/item['filename'];regular(source)
            with source.open('rb') as incoming,(snapshot/item['filename']).open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing,1024*1024)
        verified=verify(plan,snapshot)
        tree=job/'payload';tree.mkdir(mode=0o755)
        inventories=[]
        for item,prefix in zip(plan['artifacts'],prefixes):
            limit=plan['max_unpacked_node_bytes'] if item['id']=='node-lts' else plan['max_unpacked_typescript_bytes']
            inventories.append(unpack(snapshot/item['filename'],tree/prefix,'node-v'+version+'-linux-x64' if item['id']=='node-lts' else 'package',limit))
        # Also detect any mutation between the inspection/materialization passes.
        verify(plan,snapshot)
        nodebin=tree/prefixes[0]/'bin/node';regular(nodebin)
        with nodebin.open('rb') as stream:header=stream.read(20)
        if len(header)<20 or header[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(header[18:20],'little')!=62:
            raise ValueError('Node must be ELF64 little-endian x86_64')
        if not nodebin.stat().st_mode&0o111:raise ValueError('Node executable mode missing')
        for item,prefix in ((ts,prefixes[1]),(native,prefixes[2])):
            package_path=tree/prefix/'package.json';regular(package_path)
            data=json.loads(package_path.read_text())
            if data.get('name')!=item['id'] or data.get('version')!=item['version']:raise ValueError('Package identity differs')
            if item is native and (data.get('os')!=['linux'] or data.get('cpu')!=['x64']):raise ValueError('Native platform differs')
        tsdata=json.loads((tree/prefixes[1]/'package.json').read_text())
        bins=tsdata.get('bin',{})
        if not isinstance(bins,dict) or 'tsc' not in bins:raise ValueError('TypeScript tsc mapping missing')
        copy_overlay(project,tree,branding)
        for command in ('node','npm','npx'):
            target=tree/prefixes[0]/'bin'/command
            if not target.exists() or not target.resolve().is_relative_to((tree/prefixes[0]).resolve()):raise ValueError('Missing/escaping Node command')
            script=f'#!/bin/sh\nPATH="/{prefixes[0]}/bin:$PATH"\nexport PATH\nexec "/{prefixes[0]}/bin/{command}" "$@"\n'
            write_new(tree,'usr/local/bin/'+command,script.encode(),0o755)
        for command in ('tsc','tsserver'):
            if command not in bins:continue
            binpath=relative(bins[command]);target=tree/prefixes[1]/str(binpath)
            regular(target)
            # The generic package provides Node launchers; native provider is a sibling.
            script=f'#!/bin/sh\nPATH="/{prefixes[0]}/bin:$PATH"\nexport PATH\nexec "/{prefixes[0]}/bin/node" {shlex.quote('/'+prefixes[1]+'/'+str(binpath))} "$@"\n'
            write_new(tree,'usr/local/bin/'+command,script.encode(),0o755)
        total=sum(p.stat().st_size for p in tree.rglob('*') if p.is_file() and not p.is_symlink())
        if total>plan['installed_bytes_reserve_per_full_view']:raise ValueError('Combined payload budget exceeded')
        manifest={}
        for base,dirs,names in os.walk(tree,followlinks=False):
            for name in dirs+names:
                p=Path(base)/name;rel=p.relative_to(tree).as_posix();info=p.lstat()
                if stat.S_ISLNK(info.st_mode):entry={'type':'symlink','target':os.readlink(p),'mode':'0777'}
                elif stat.S_ISDIR(info.st_mode):entry={'type':'dir','mode':'0755'}
                elif stat.S_ISREG(info.st_mode):entry={'type':'file','sha256':sha(p),'size':info.st_size,'mode':f'{stat.S_IMODE(info.st_mode):04o}'}
                else:raise ValueError('Special payload entry')
                manifest[rel]={**entry,'uid':0,'gid':0}
        # Ownership is a declaration for future isolated application, never host chown.
        state.update(status='staged_only_application_blocked',payload=str(tree),artifacts=verified,manifest=manifest,unpacked_bytes=total,source_plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),application_requirement='New sealed contract, disposable Base/Live copies, approved isolated runner; no direct host-rootfs application')
    except BaseException as error:
        state.update(status='quarantined',error=str(error));raise
    finally:
        with (job/'payload-report.json').open('x') as stream:json.dump(state,stream,indent=2);stream.write('\n')
    return job
