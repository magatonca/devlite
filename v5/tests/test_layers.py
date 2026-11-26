import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from v5 import metadata,branding,layers
from pipeline.devlite.structure import digest

class MetadataTests(unittest.TestCase):
    def test_catalog_changes_only_path_and_measured_size(self):
        s="- id: xubuntu-desktop-minimal\n  path: minimal.visual.fix.squashfs\n  size: 1000\n  type: fsimage-layered\n"
        new=metadata.render_catalog(s,1000,123)
        self.assertEqual(new,s.replace("minimal.visual.fix.squashfs",metadata.INSTALL).replace("1000","1123"))
        for document,size,added in [(s+s,1000,123),(s,999,123),(s,1000,-1)]:
            with self.assertRaises(ValueError):metadata.render_catalog(document,size,added)
    def test_grub_keeps_boot_and_identity_arguments(self):
        s="menuentry 'Live' {\n linux /casper/vmlinuz locale=pt_BR.UTF-8 layerfs-path=minimal.visual.live.fix.squashfs username=devlite hostname=devlite quiet ---\n initrd /casper/initrd\n}\n"
        self.assertEqual(metadata.render_grub(s),s.replace(metadata.OLD_LIVE,metadata.LIVE))
        with self.assertRaises(ValueError):metadata.render_grub(s.replace("hostname=devlite","hostname=other"))
    def test_new_manifests_do_not_rewrite_inherited_base_or_drop_snap(self):
        result=metadata.package_manifests({"old":"1","openssh-server":"2"},{"old":"1","openssh-server":"2","live":"1"},"old\t1\n","old\t1\nlive\t1\nsnap:installer\t123\t456\n")
        self.assertNotIn("minimal.manifest",result)
        self.assertNotIn("minimal.live.manifest",result)
        self.assertIn("snap:installer\t123\t456",result["filesystem.manifest"])
        self.assertIn("+openssh-server",result[metadata.INSTALL.removesuffix(".squashfs")+".manifest"])
    def test_seven_layers_only_with_no_duplicates(self):
        inherited={name:"a"*64 for name in ["minimal.squashfs","minimal.visual.squashfs",metadata.OLD_INSTALL,"minimal.visual.live.squashfs",metadata.OLD_LIVE]}
        text="".join(h+" *"+name+"\n" for name,h in inherited.items())
        new={metadata.INSTALL:"b"*64,metadata.LIVE:"c"*64}
        self.assertEqual(len(metadata.checksum_layers(text,new).splitlines()),7)
        with self.assertRaises(ValueError):metadata.checksum_layers(text+text.splitlines(True)[0],new)
    def test_branding_preserves_technical_flavor_and_page_behaviour(self):
        s='flavor: xubuntu\npages:\n  locale:\n    image: "mascot.png"\n  done:\n    image: "mascot.png"\n  try-or-install:\n    image: "mascot.png"\n  accessibility:\n    visible: false\n'
        result=branding.whitelabel(s)
        self.assertIn('app-name: "Instalar DevLite OS 1.0"',result)
        self.assertIn('flavor: xubuntu',result)
        self.assertIn('visible: false',result)
        self.assertEqual(result.count('image: "devlite.png"'),3)
        with self.assertRaises(ValueError):branding.whitelabel(result)
    def test_welcome_does_not_blindly_replace_upstream_attributions(self):
        s='<h1>Welcome to Xubuntu</h1><p>Based on Xubuntu</p><img src="mascot.svg">'
        result=branding.welcome(s)
        self.assertIn('Welcome to DevLite OS',result)
        self.assertIn('Based on Xubuntu',result)
        self.assertIn('src="devlite.svg"',result)
    def test_diagnostic_browser_can_never_release_pack(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job=root/'work/release-v5-abcdefgh';job.mkdir(parents=True)
            files={'contract.json':'{}','browser-profile.source':'enforce fixture','namespace-cleanup.json':json.dumps({'absent':True}),
                'browser-result.json':json.dumps({'status':'diagnostic_only_not_approved','cleanup_errors':[],'results':{'base':{},'live':{}}})}
            for name,content in files.items():(job/name).write_text(content)
            (job/'browser-visual-review.json').write_text(json.dumps({'contract_sha256':digest(job/'contract.json'),'profile_sha256':digest(job/'browser-profile.source')}))
            for p in job.iterdir():p.chmod(0o444)
            real=Path.stat
            def trusted(path,*args,**kwargs):
                value=real(path,*args,**kwargs)
                if path.parent==job:
                    values=list(value);values[4]=0;return __import__('os').stat_result(values)
                return value
            with patch.object(layers,'ROOT',root),patch.object(Path,'stat',trusted):
                with self.assertRaisesRegex(ValueError,'not approved'):layers.require_browser(job)
