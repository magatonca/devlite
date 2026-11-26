"""Aquisição: testes offline com bytes fictícios, sem transferência real."""
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from pipeline.devlite.customize import package_acquisition as m
from pipeline.devlite.customize.manifest import SpecError

ROOT=m.ROOT
URL='https://archive.ubuntu.com/ubuntu/pool/main/d/demo/demo_2_amd64.deb'

def artifact(data=b'debs'):
    return {'package':'demo','version':'2','architecture':'amd64','filename':'pool/main/d/demo/demo_2_amd64.deb','sha256':hashlib.sha256(data).hexdigest(),'download_bytes':len(data),'urls':[URL]}

def response(data=b'debs',url=URL,length='4'):
    result=io.BytesIO(data);result.status=200;result.headers={} if length is None else {'Content-Length':length};result.geturl=lambda:url
    return result

class AcquisitionTests(unittest.TestCase):
    def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')

    def test_only_official_https_package_urls(self):
        self.assertEqual(m.valid_url(URL),URL)
        for url in ('http://archive.ubuntu.com/ubuntu/pool/demo.deb','https://evil.test/ubuntu/pool/demo.deb','https://user@archive.ubuntu.com/ubuntu/pool/demo.deb','https://archive.ubuntu.com:444/ubuntu/pool/demo.deb','https://archive.ubuntu.com/ubuntu/pool/%2e%2e/demo.deb',URL+'?token=1'):
            with self.subTest(url=url),self.assertRaises(SpecError):m.valid_url(url)

    def test_redirect_refuses_external_host_before_request(self):
        handler=m.OfficialRedirect()
        with self.assertRaises(SpecError):handler.redirect_request(urllib.request.Request(URL),None,302,'',{},'https://evil.test/ubuntu/pool/demo.deb')

    def test_duplicate_base_live_artifact_has_signed_provenance(self):
        with self.temp() as folder:
            w=Path(folder);(w/'lists').mkdir();item=artifact()
            name='archive.ubuntu.com_ubuntu_dists_noble_main_binary-amd64_Packages';file=w/'lists'/name
            # Sem parágrafo vazio final: o scanner também deve processar EOF.
            file.write_text('Package: demo\nVersion: 2\nArchitecture: amd64\nFilename: '+item['filename']+'\nSize: 4\nSHA256: '+item['sha256']+'\n')
            evidence=[{'suite':'noble','inrelease_sha256':'b'*64,'signer':'official'},{'index':name,'sha256':m.sha(file)}]
            plan={'targets':{k:{'changes':[dict(item)]} for k in ('base','live')}}
            result=m.entries(plan,w,evidence)
            self.assertEqual(len(result),1);self.assertEqual(result[0]['targets'],['base','live']);self.assertEqual(result[0]['origins'][0]['signer'],'official')
            plan['targets']['live']['changes'][0]['sha256']='f'*64
            with self.assertRaises(SpecError):m.entries(plan,w,evidence)

    def test_signed_index_hash_is_required(self):
        with self.temp() as folder:
            w=Path(folder);(w/'lists').mkdir();name='archive.ubuntu.com_ubuntu_dists_noble_main_binary-amd64_Packages';(w/'lists'/name).write_text('tampered')
            with self.assertRaises(SpecError):m.entries({'targets':{}},w,[{'index':name,'sha256':'a'*64}])

    def test_exact_metadata_age_and_expiry(self):
        now=datetime(2026,11,16,tzinfo=timezone.utc)
        m.fresh_metadata([{'suite':'noble','date':'Thu, 25 Apr 2024 15:10:33 UTC'}],now)
        for item in ({'suite':'noble-updates','date':'Sun, 08 Nov 2026 23:59:59 UTC'},{'suite':'noble-security','date':'Tue, 17 Nov 2026 00:00:00 UTC'},{'suite':'noble','date':'Thu, 25 Apr 2024 15:10:33 UTC','valid_until':'Sun, 15 Nov 2026 00:00:00 UTC'}):
            with self.assertRaises(SpecError):m.fresh_metadata([item],now)

    def test_permission_false_never_creates_network_client(self):
        with patch.object(m,'normal_user'),patch.object(m,'opener') as op:
            with self.assertRaisesRegex(SpecError,'não autorizado'):m.download(Path('absent'),'a'*64)
            op.assert_not_called()

    def test_root_is_refused(self):
        with patch.object(m.os,'geteuid',return_value=0):
            with self.assertRaises(SpecError):m.normal_user()

    def test_wrong_approval_hash_blocks_before_network(self):
        with self.temp() as folder:
            p=Path(folder)/'download-plan.json';p.write_text('{}')
            with patch.object(m,'normal_user'),patch.object(m.json,'loads',return_value={'download_pacotes_autorizado':True}),patch.object(m,'opener') as op:
                with self.assertRaisesRegex(SpecError,'Hash'):m.download(p,'a'*64)
                op.assert_not_called()

    def test_verified_bytes_published_once(self):
        with self.temp() as folder:
            client=Mock();client.open.return_value=response();w=Path(folder)
            result=m.fetch_one(artifact(),w,client,reserve=0)
            self.assertEqual(Path(result['file']).read_bytes(),b'debs');self.assertFalse(result['cached']);self.assertFalse(list(w.glob('*.part-*')))

    def test_bad_hash_keeps_partial_and_never_publishes(self):
        with self.temp() as folder:
            client=Mock();client.open.return_value=response(b'evil');w=Path(folder)
            with self.assertRaises(SpecError):m.fetch_one(artifact(),w,client,reserve=0)
            self.assertFalse((w/'demo_2_amd64.deb').exists());self.assertEqual(len(list(w.glob('*.part-*'))),1)

    def test_truncated_or_overlong_bytes_are_rejected(self):
        for data in (b'deb',b'debss'):
            with self.temp() as folder:
                client=Mock();client.open.return_value=response(data,length=None);w=Path(folder)
                with self.assertRaises(SpecError):m.fetch_one(artifact(),w,client,reserve=0)
                self.assertFalse((w/'demo_2_amd64.deb').exists())

    def test_content_length_mismatch_rejected(self):
        with self.temp() as folder:
            client=Mock();client.open.return_value=response(length='999')
            with self.assertRaises(SpecError):m.fetch_one(artifact(),Path(folder),client,reserve=0)

    def test_valid_cache_reused_without_connection_and_invalid_not_overwritten(self):
        with self.temp() as folder:
            w=Path(folder);file=w/'demo_2_amd64.deb';file.write_bytes(b'debs');client=Mock()
            self.assertTrue(m.fetch_one(artifact(),w,client)['cached']);client.open.assert_not_called()
            file.write_bytes(b'evil')
            with self.assertRaises(SpecError):m.fetch_one(artifact(),w,client)
            self.assertEqual(file.read_bytes(),b'evil')

    def test_disk_reserve_stops_before_publication(self):
        with self.temp() as folder:
            client=Mock();client.open.return_value=response()
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
                with self.assertRaisesRegex(SpecError,'Reserva'):m.fetch_one(artifact(),Path(folder),client,reserve=10)

    def test_404_stops_without_changing_version(self):
        with self.temp() as folder:
            client=Mock();client.open.side_effect=urllib.error.HTTPError(URL,404,'Not found',{},None)
            with self.assertRaisesRegex(SpecError,'indisponível'):m.fetch_one(artifact(),Path(folder),client,reserve=0)
            self.assertEqual(client.open.call_count,1)

if __name__=='__main__':unittest.main()
