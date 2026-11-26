"""Acquire only the two version-locked Ubuntu debs; bounded verified downloads."""
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from pipeline.devlite.customize.installation import verify_archives
ALLOWED_HOSTS={"archive.ubuntu.com","security.ubuntu.com","br.archive.ubuntu.com"}
class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        u=urlsplit(newurl)
        if u.hostname not in ALLOWED_HOSTS or u.scheme not in ("http","https") or (u.scheme=="http" and u.hostname!="br.archive.ubuntu.com") or u.username or u.password:
            raise ValueError("Non-official redirect")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def acquire(plan_path):
    plan_path=Path(plan_path);data=json.loads(plan_path.read_text());work=plan_path.parent
    cache=work / "debs";cache.mkdir(exist_ok=True)
    unique={}
    for target in data["targets"].values():
        for item in target["changes"]:
            if item["package"] not in ("openssh-server","openssh-sftp-server") or item["previous"] is not None:
                raise ValueError("Unexpected package transaction")
            name=Path(item["filename"]).name
            if item["filename"]!="pool/main/o/openssh/"+name or item["architecture"]!="amd64":
                raise ValueError("Unexpected origin path/architecture")
            if name in unique and unique[name]!=item:raise ValueError("Conflicting target versions")
            unique[name]=item
    if len(unique)!=2:raise ValueError("Expected two packages")
    evidence=[];opener=urllib.request.build_opener(OfficialRedirect())
    for name,item in sorted(unique.items()):
        dest=cache/name
        # Mirror URI is the same HTTP origin as authenticated local Ubuntu indexes.
        # Never disable TLS certificate checks; authenticity is the signed hash chain.
        url="http://br.archive.ubuntu.com/ubuntu/"+item["filename"]
        if dest.is_symlink():raise ValueError("Archive symlink")
        if not dest.exists():
            temporary=cache/(name+".partial")
            with opener.open(urllib.request.Request(url,headers={"User-Agent":"DevLiteOS/1.0 (Ubuntu package acquisition)"}),timeout=45) as response,temporary.open("xb") as out:
                total=0
                while chunk:=response.read(65536):
                    total+=len(chunk)
                    if total>item["download_bytes"]:raise ValueError("Oversized archive")
                    out.write(chunk)
            if total!=item["download_bytes"]:raise ValueError("Truncated archive")
            if hashlib.sha256(temporary.read_bytes()).hexdigest()!=item["sha256"]:raise ValueError("Archive digest mismatch")
            temporary.rename(dest)
        if dest.stat().st_size!=item["download_bytes"] or hashlib.sha256(dest.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("Archive verification failed")
        fields=subprocess.run(["dpkg-deb","-f",str(dest),"Package","Version","Architecture"],capture_output=True,text=True,check=True).stdout
        expected={"Package":item["package"],"Version":item["version"],"Architecture":item["architecture"]}
        if dict(line.split(": ",1) for line in fields.splitlines())!=expected:raise ValueError("Archive control differs")
        evidence.append({"file":str(dest),"url":url,"bytes":item["download_bytes"],"sha256":item["sha256"],"authentication":"Ubuntu signed InRelease -> Packages SHA-256 -> deb SHA-256", "control":expected})
    verify_archives(data,cache)
    receipt=work / "acquisition.json";receipt.write_text(json.dumps(evidence,indent=2)+"\n")
    print(receipt)
if __name__=="__main__":
    import sys
    acquire(Path(sys.argv[1]))
