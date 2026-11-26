"""One v5 ISO from a root-verified leaf pair and the pinned v4 ISO."""
import json
import os
import re
import shutil
from pathlib import Path
from pipeline.devlite.runtime import Runner, owned_directory
from pipeline.devlite.build import detect
from pipeline.devlite.structure import digest, compare_boot_metadata, region_digest
from pipeline.devlite.validation import inventory, iso_metadata, verify_manifest
from pipeline.devlite.minimal_build import make_md5, compare_iso_trees
from pipeline.devlite.minimal_root import EPOCH
from pipeline.devlite.customize.installation import installed
from v5.execution import ROOT,RESERVE,read,code_paths,save
from v5.metadata import INSTALL,LIVE,render_catalog,render_grub,package_manifests,checksum_layers
from v5.layers import guard_temperature
SOURCE=ROOT/"artifacts/modern-release-owcgr3mg/devlite-os-1.0-amd64.iso"
SOURCE_SHA="4adf369ea22ef5dd6c49da2db9fd70ea5620219d4636489a0933a2bb57bb5564"


def package_versions(document):
    result={}
    for line in document.splitlines():
        if line.startswith("snap:"):continue
        name,version=line.split()
        if name in result:raise ValueError("Duplicate package")
        result[name]=version
    return result


def assemble(job,approval):
    if os.geteuid()==0:raise ValueError("Run ISO assembly as magaton, never root")
    job,data=read(job,approval)
    if data["phase"]!="verified-layer-pack":raise ValueError("Not a verified pack")
    receipt=job/"published/pack-result.json"
    if receipt.is_symlink() or receipt.stat().st_uid!=0 or receipt.stat().st_mode&0o222:raise ValueError("Untrusted published receipt")
    packed=json.loads(receipt.read_text())
    if packed["status"]!="v5_layers_verified" or packed["cleanup_errors"] or packed["contract_sha256"]!=approval or not packed["host_critical_files_unchanged"]:
        raise ValueError("Pack not accepted")
    tests=json.loads((ROOT/"docs/v5/evidencias/final-tests.json").read_text())
    if not tests.get("successful") or tests.get("tests_run",0)<638 or tests.get("skipped") or tests.get("code_sha256")!={str(p.relative_to(ROOT)):digest(p) for p in code_paths()}:
        raise ValueError("Complete suite missing/stale/failed")
    verification=json.loads((ROOT/"docs/v5/evidencias/final-verifier.json").read_text())
    if verification.get("returncode")!=0:raise ValueError("Project verifier not passed")
    guard_temperature()
    if shutil.disk_usage(ROOT).free<RESERVE+4*SOURCE.stat().st_size+2*1024**3:raise ValueError("ISO and verification extraction budget")
    if digest(SOURCE)!=SOURCE_SHA:raise ValueError("Pinned v4 integrity failure")
    workspace=owned_directory(ROOT/"work","v5-iso-");(workspace/"logs").mkdir()
    runner=Runner(workspace/"logs",EPOCH)
    report={"status":"building","source_v4_sha256":SOURCE_SHA,"pack_contract_sha256":approval,"boot_tested":False,"installation_tested":False}
    try:
        original=workspace/"source-tree"
        runner.xorriso("extract-reference","-osirrox","on","-indev",SOURCE,"-extract","/",original)
        before=inventory(original)
        generated=workspace/"updates";generated.mkdir();mapped={};versions={};new_hashes={}
        for target,name in (("base",INSTALL),("live",LIVE)):
            item=packed["results"][target];file=Path(item["file"])
            if file.parent!=job/"published" or file.name!=name or file.is_symlink() or file.stat().st_uid!=0 or file.stat().st_mode&0o222 or digest(file)!=item["sha256"]:
                raise ValueError("Published leaf changed")
            mapped["casper/"+name]=file;new_hashes[name]=item["sha256"]
            manifest=Path(item["manifest"])
            if manifest.parent!=job/"published" or digest(manifest)!=item["manifest_sha256"]:raise ValueError("Manifest changed")
            versions[target]=package_versions(manifest.read_text())
        old=original/"casper";catalog=(old/"install-sources.yaml").read_text()
        sizes=re.findall(r"(?m)^  size: ([0-9]+)$",catalog)
        if len(sizes)!=1:raise ValueError("Unexpected source sizes")
        sizes={t:packed["results"][t]["uncompressed_allocated_bytes"] for t in ("base","live")}
        old_size=int(re.findall(r"(?m)^  size: ([0-9]+)$",catalog)[0])
        texts={"casper/install-sources.yaml":render_catalog(catalog,old_size,sizes["base"]),
            "casper/SHA256SUMS":checksum_layers((old/"SHA256SUMS").read_text(),new_hashes),
            "casper/"+INSTALL.removesuffix("squashfs")+"size":str(sizes["base"])+"\n",
            "casper/"+LIVE.removesuffix("squashfs")+"size":str(sizes["live"])+"\n",
            "casper/filesystem.size":str(int((old/"filesystem.size").read_text())+sizes["live"])+"\n"}
        for name,text in package_manifests(versions["base"],versions["live"],(old/"devlite-base.manifest.full").read_text(),(old/"filesystem.manifest").read_text()).items():texts["casper/"+name]=text
        grub_count=0
        for p in (original/"boot/grub").glob("*.cfg"):
            text=p.read_text()
            if re.search(r"(?m)^\s*linux\s+/casper/vmlinuz",text):texts[str(p.relative_to(original))]=render_grub(text);grub_count+=1
        if grub_count<2:raise ValueError("Both GRUB paths required")
        texts["casper/devlite-v5.json"]=json.dumps({**report,"status":"candidate","services":"manual; boot disabled and unmasked","devcontrol":"2.0","snap_cloud_init":"retained for compatibility","hyper_v_validation":"pending","custom_checksums":"unsigned; original Ubuntu signatures preserved"},sort_keys=True,indent=2)+"\n"
        for name,text in texts.items():
            p=generated/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);os.utime(p,(EPOCH,EPOCH));mapped[name]=p
        md5=generated/"md5sum.txt";md5.write_text(make_md5((original/"md5sum.txt").read_text(),mapped,{}));os.utime(md5,(EPOCH,EPOCH));mapped["md5sum.txt"]=md5
        output=owned_directory(ROOT/"artifacts","devlite-v5-");partial=output/"devlite-os-1.0-v5-amd64.iso.partial"
        before_boot=detect(runner,SOURCE,"source")
        args=["-indev",str(SOURCE),"-outdev",str(partial),"-overwrite","on"]
        for name,p in mapped.items():args += ["-map",str(p),"/"+name,"-chown","0","/"+name,"--","-chgrp","0","/"+name,"--","-chmod","0444","/"+name,"--","-alter_date","m","="+str(EPOCH),"/"+name,"--"]
        args += ["-assess_indev_features","replay","-boot_image","any","replay","-volid","DevLite OS 1.0 v5","-volume_date","uuid",before_boot["timestamp"],"-end"]
        guard_temperature();runner.xorriso("assemble-single-v5",*args)
        after_boot=detect(runner,partial,"result");compare_boot_metadata(SOURCE,partial,before_boot,after_boot)
        if after_boot["timestamp"]!=before_boot["timestamp"] or after_boot["volume_id"]!="DevLite OS 1.0 v5":raise ValueError("Volume metadata differs")
        if region_digest(SOURCE,before_boot["efi_offset"],before_boot["efi_bytes"])!=region_digest(partial,after_boot["efi_offset"],after_boot["efi_bytes"]):raise ValueError("Appended EFI changed")
        result=workspace/"result-tree";runner.xorriso("extract-result","-osirrox","on","-indev",partial,"-extract","/",result)
        after=inventory(result);added=set(mapped)-set(before)
        compare_iso_trees(before,after,original,result,set(mapped)&set(before),added,set())
        for name,p in mapped.items():
            if digest(result/name)!=digest(p):raise ValueError("Mapped payload differs: "+name)
        old_meta=iso_metadata(runner.xorriso("source-metadata","-indev",SOURCE,"-find","/","-exec","lsdl","--"))
        new_meta=iso_metadata(runner.xorriso("result-metadata","-indev",partial,"-find","/","-exec","lsdl","--"))
        for name,value in old_meta.items():
            if name.lstrip("/") not in set(mapped)|{"boot.catalog"} and new_meta.get(name)!=value:raise ValueError("Inherited ISO metadata changed: "+name)
        for name in mapped:
            if new_meta["/"+name][0]!="-r--r--r--" or new_meta["/"+name][2:4]!=["0","0"]:raise ValueError("Mapped permissions differ")
        if set(p.name for p in (result/"casper").glob("*.squashfs"))!={*data["stacks"]["base"],*data["stacks"]["live"],INSTALL,LIVE}:raise ValueError("Seven-layer layout differs")
        report["md5_entries"]=verify_manifest(result,Path("md5sum.txt"),"md5")
        report["sha256_layer_entries"]=verify_manifest(result,Path("casper/SHA256SUMS"),"sha256")
        if shutil.disk_usage(ROOT).free<RESERVE:raise ValueError("Reserve violated")
        final=output/"devlite-os-1.0-v5-amd64.iso"
        if final.exists():raise ValueError("Never overwrite")
        checksum=digest(partial);partial.rename(final)
        report.update(status="structurally_verified_not_hyper_v_approved",iso=str(final),bytes=final.stat().st_size,sha256=checksum,free_bytes=shutil.disk_usage(ROOT).free,thermal=guard_temperature())
        (output/"SHA256SUMS").write_text(checksum+"  "+final.name+"\n");save(output/"validation.json",report)
    except BaseException as error:report.update(status="blocked",error=str(error));raise
    finally:save(workspace/"assembly-result.json",report)
    return report

if __name__=="__main__":
    import sys
    if len(sys.argv)!=3:raise SystemExit("Expected verified pack job and contract SHA-256")
    print(json.dumps(assemble(Path(sys.argv[1]),sys.argv[2]),indent=2))
