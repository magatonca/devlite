"""Verified incremental SquashFS leaves over the immutable v4 chains."""
import gc
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from pipeline.devlite.minimal_root import snapshot, EPOCH
from pipeline.devlite.release_layers import recipe, materialize, delta_manifest, full_manifest, metadata
from pipeline.devlite.release_pack import compress_args
from pipeline.devlite.release_resume import absent_xattrs, checked_snapshot
from pipeline.devlite.runtime import Runner
from pipeline.devlite.structure import digest
from pipeline.devlite.customize.installation import installed
from v5.execution import ROOT, CASPER, STACKS, RESERVE, save
from v5.image import put, finalize
from v5.worker import apply_payload
from v5.browser_probe import inventory_digest
LEAVES={"base":"minimal.visual.fix.v5.squashfs","live":"minimal.visual.live.fix.v5.squashfs"}


def require_browser(job):
    import re
    if job.is_symlink() or job.resolve()!=job or job.parent!=ROOT/"work" or not re.fullmatch(r"release-v5-[a-z0-9_]{8}",job.name):
        raise ValueError("Unexpected browser job")
    result_path=job/"browser-result.json";review_path=job/"browser-visual-review.json"
    for path in (result_path,review_path,job/"namespace-cleanup.json"):
        if path.is_symlink() or path.stat().st_uid!=0 or path.stat().st_mode&0o022:
            raise ValueError("Browser receipt not trusted")
    result=json.loads(result_path.read_text());review=json.loads(review_path.read_text())
    if review.get("contract_sha256")!=digest(job/"contract.json") or review.get("profile_sha256")!=digest(job/"browser-profile.source"):
        raise ValueError("Review not bound to browser execution/profile")
    if result["status"]!="confined_processes_running_visual_review_required" or result["cleanup_errors"] or set(result["results"])!={"base","live"}:
        raise ValueError("Real confined browser test not approved")
    if json.loads((job/"namespace-cleanup.json").read_text())["absent"] is not True:
        raise ValueError("Policy namespace not cleaned up")
    for target in ("base","live"):
        screenshot=Path(result["results"][target]["screenshot"])
        item=review["targets"][target]
        if item["rendered_page"] is not True or item["javascript_ok"] is not True or item["screenshot_sha256"]!=digest(screenshot):
            raise ValueError("Screenshot not accepted or changed")
    return result,review


def layer_absence(image,mount):
    names={".":{"xattrs":{}}}
    names.update({str(p.relative_to(mount)):{"xattrs":{}} for p in mount.rglob("*")})
    return set(absent_xattrs(image,names)),set(names)


def visible_absence(chain,records,extra=()):
    result=set()
    for name in chain:
        absent,names=records[name]
        result.difference_update(names);result.update(absent)
    for root in extra:
        result.discard(".")
        result.difference_update(str(p.relative_to(root)) for p in root.rglob("*"))
    return frozenset(result)


def invalidate_browser_cache(root):
    removed=[]
    for directory in ("var/cache/apparmor","etc/apparmor.d/cache"):
        base=root/directory
        if not base.exists():continue
        if base.is_symlink():raise ValueError("Symlink policy cache")
        for p in base.rglob("epiphany"):
            if p.is_symlink() or not p.is_file():raise ValueError("Unexpected cached profile")
            p.unlink();removed.append(str(p.relative_to(root)))
    return removed


def guard_temperature():
    readings=[]
    for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        value=int(p.read_text().strip())
        if value<0 or value>150000:raise ValueError("Invalid thermal sensor")
        readings.append({"sensor":str(p),"millidegrees":value})
        if value>=85000:raise ValueError("Thermal stop at 85 C")
    return {"readings":readings,"physical_temperature_available":bool(readings),"cpu_quota":"100%"}


def run(job,data,approval):
    source=Path(data["pack"]["applied_job"]);browser=Path(data["pack"]["browser_job"])
    require_browser(browser)
    if digest(browser/"browser-result.json")!=data["pack"]["browser_result_sha256"] or digest(browser/"browser-visual-review.json")!=data["pack"]["browser_review_sha256"]:
        raise ValueError("Browser evidence changed")
    if digest(source/"application-result.json")!=data["pack"]["applied_result_sha256"]:
        raise ValueError("Source receipt changed")
    profile=browser/"browser-profile.source"
    if digest(profile)!=data["pack"]["profile_sha256"]:raise ValueError("Profile changed")
    for t,h in data["pack"]["upper_inventory_sha256"].items():
        if inventory_digest(source/"application"/t/"upper")!=h:raise ValueError("Source COW changed")
    attempt=job/"pack";attempt.mkdir(mode=0o700);(attempt/"logs").mkdir()
    runner=Runner(attempt/"logs",EPOCH);runner.env.pop("SOURCE_DATE_EPOCH",None)
    mounts=[];report={"status":"packing","results":{},"iso_generated":False,"thermal":guard_temperature()}
    def call(label,args):
        guard_temperature()
        if shutil.disk_usage(job).free<RESERVE:raise ValueError("20 GiB reserve")
        return runner.run(label,args)
    def mount(label,args,p):call(label,args);mounts.append(p)
    def unmount(p):call("umount-"+str(len(mounts)),["umount",str(p)]);mounts.remove(p)
    try:
        call("private",["mount","--make-rprivate","/"])
        lowers={};records={}
        for name in sorted({n for names in STACKS.values() for n in names}):
            image=CASPER/name
            if digest(image)!=data["lowers"][str(image)]:raise ValueError("v4 lower changed")
            p=attempt/("lower-"+name);p.mkdir()
            mount("lower-"+name,["mount","-t","squashfs","-o","loop,ro,nodev,nosuid",str(image),str(p)],p)
            lowers[name]=p;records[name]=layer_absence(image,p)
        for target in ("base","live"):
            stage=attempt/target;stage.mkdir()
            before_root=stage/"before";before_root.mkdir()
            chain=list(reversed(STACKS[target]));lowerdirs=":".join(str(lowers[n]) for n in chain)
            mount("before-"+target,["mount","-t","overlay","-o","ro,nodev,nosuid,lowerdir="+lowerdirs,"overlay",str(before_root)],before_root)
            upper=stage/"upper";upper.mkdir();work=stage/"work";work.mkdir();root=stage/"root";root.mkdir()
            old_upper=source/"application"/target/"upper"
            options="nodev,nosuid,lowerdir="+str(old_upper)+":"+lowerdirs+",upperdir="+str(upper)+",workdir="+str(work)+",index=off,metacopy=off,redirect_dir=off,xino=off"
            mount("after-"+target,["mount","-t","overlay","-o",options,"overlay",str(root)],root)
            before=snapshot(before_root,xattr_absence=visible_absence(STACKS[target],records))
            apply_payload(root)
            put(root,"etc/apparmor.d/epiphany",profile.read_text())
            caches=invalidate_browser_cache(root)
            if target=="live":
                from v5.branding import apply as apply_branding
                branding=apply_branding(root)
            else:branding={"live_only":True}
            final=finalize(root)
            # Project logs retain the full operation. Do not publish host-specific
            # terminal logs or generated public-key fingerprints in the ISO.
            for name in ("var/log/apt/history.log","var/log/apt/term.log","var/log/dpkg.log"):
                p=root/name
                if p.is_symlink():raise ValueError("Unexpected log symlink")
                if name in before:
                    original=before_root/name
                    temporary=p.with_name(p.name+".v5-restore")
                    if temporary.exists() or temporary.is_symlink():raise ValueError("Unexpected log temporary")
                    shutil.copyfile(original,temporary)
                    os.replace(temporary,p)
                    metadata(p,before[name])
                elif p.exists():p.unlink()
            versions=installed((root/"var/lib/dpkg/status").read_text())
            expected=json.loads(Path(data["plan"]).read_text())["targets"][target]["final_versions"]
            if versions!=expected:raise ValueError("Final versions differ from SSH plan")
            if list((root/"etc/ssh").glob("ssh_host_*_key")):raise ValueError("Private SSH host key remains")
            if (root/"etc/machine-id").read_text().strip():raise ValueError("Factory machine-id must be empty")
            after=snapshot(root,xattr_absence=visible_absence(STACKS[target],records,(old_upper,upper)))
            protected=("var/lib/snapd/snaps/","var/lib/snapd/seed/","usr/libexec/ubuntu-desktop","usr/lib/ubuntu-desktop")
            for name in before.keys()|after.keys():
                if name.startswith(protected) and before.get(name)!=after.get(name):
                    raise ValueError("Protected installer component changed: "+name)
            shadow=(root/"etc/shadow").read_text().splitlines()
            if not any(line.startswith(("root:!","root:*")) for line in shadow):raise ValueError("Root factory account must be locked")
            if (root/"usr/libexec/devlite-services-v5").stat().st_mode&0o777!=0o755:raise ValueError("Privileged helper mode")
            delta=recipe(before,after)
            save(stage/"recipe.json",delta)
            logical=sum(v.get("size",0) for v in delta["put"].values())
            if shutil.disk_usage(job).free<RESERVE+3*logical+2*1024**3:
                raise ValueError("Measured delta budget insufficient")
            delta_root=stage/"delta";expected_delta=materialize(root,delta_root,delta,EPOCH)
            output=stage/LEAVES[target]
            call("compress-"+target,compress_args(delta_root,output,expected_delta["."]))
            verify=stage/"verify";verify.mkdir()
            mount("verify-leaf-"+target,["mount","-t","squashfs","-o","loop,ro,nodev,nosuid",str(output),str(verify)],verify)
            checked_snapshot(verify,expected_delta,"v5 leaf",absent_xattrs(output,expected_delta))
            merged=stage/"composed";merged.mkdir()
            mount("verify-compose-"+target,["mount","-t","overlay","-o","ro,nodev,nosuid,lowerdir="+str(verify)+":"+lowerdirs,"overlay",str(merged)],merged)
            # If the leaf has an xattr table, the kernel can return [] itself.
            leaf_absent,names=layer_absence(output,verify)
            composed_absence=set(visible_absence(STACKS[target],records));composed_absence.difference_update(names);composed_absence.update(leaf_absent)
            checked_snapshot(merged,after,"v5 kernel composition",frozenset(composed_absence))
            unmount(merged);unmount(verify);unmount(root);unmount(before_root)
            usage=call("measure-leaf-"+target,["du","-sx","-B1",str(delta_root)])
            allocated=int(usage.split()[0])
            manifest=full_manifest(versions)
            (stage/"packages.manifest.full").write_text(manifest)
            report["results"][target]={"file":str(output),"sha256":digest(output),"bytes":output.stat().st_size,
              "uncompressed_allocated_bytes":allocated,"logical_put_bytes":logical,"package_count":len(versions),"cache_invalidated":caches,"policy":final,
              "whiteout_count":len(delta["whiteouts"]),"composition_verified":True,"branding":branding}
            del before,after,delta,expected_delta;gc.collect()
        from pipeline.devlite.customize.isolation_validation import critical_files
        if critical_files()!=data["host_critical_files"]:raise ValueError("Host critical state changed")
        report["status"]="v5_layers_verified"
    except BaseException as e:report.update(status="quarantined",error=str(e));raise
    finally:
        failures=[]
        for p in reversed(mounts[:]):
            try:unmount(p)
            except Exception as e:failures.append(str(e))
        report["cleanup_errors"]=failures
        if failures:report["status"]="quarantined"
        save(job/"pack-result.json",report)
    if report["status"]=="v5_layers_verified" and not report["cleanup_errors"]:
        from pipeline.devlite.customize.isolation_validation import critical_files
        if critical_files()!=data["host_critical_files"]:raise ValueError("Host critical state changed")
        publish=job/"published";publish.mkdir(mode=0o755)
        for target,item in report["results"].items():
            original=Path(item["file"]);out=publish/original.name
            if digest(original)!=item["sha256"]:raise ValueError("Verified output changed")
            shutil.copyfile(original,out);out.chmod(0o444)
            manifest=publish/(target+".manifest.full")
            shutil.copyfile(attempt/target/"packages.manifest.full",manifest);manifest.chmod(0o444)
            item["file"]=str(out);item["manifest"]=str(manifest);item["manifest_sha256"]=digest(manifest)
        report["contract_sha256"]=approval;report["host_critical_files_unchanged"]=True
        save(publish/"pack-result.json",report);(publish/"pack-result.json").chmod(0o444)
        job.chmod(0o711)
        save(job/"pack-result.json",report)
    return report
