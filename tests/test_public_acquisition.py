"""Controlled acquisition tests use in-memory responses only."""
import io,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from pipeline.devlite.final_acquisition import fetch,acquire,URLS,NoRedirect
ROOT=Path(__file__).resolve().parents[1]
class Response(io.BytesIO):
 status=200
 def __init__(self,data,url=URLS[0],headers=None):super().__init__(data);self.url=url;self.headers=headers or {}
 def geturl(self):return self.url
class AcquisitionTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def opener(self,response):return SimpleNamespace(open=lambda *args,**kwargs:response)
 def test_no_approval_no_acquisition(self):
  with self.assertRaisesRegex(ValueError,'approval'):acquire(ROOT,'0'*64)
 def test_only_exact_official_urls(self):
  with self.temp() as name:
   path=Path(name)/'archive'
   with self.assertRaisesRegex(ValueError,'outside'):fetch('https://example.com/file',path,None,10,None)
   self.assertFalse(path.exists())
 def test_redirects_rejected(self):
  with self.assertRaisesRegex(ValueError,'Redirect'):NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_unadvertised_size_is_bounded(self):
  with self.temp() as name:
   path=Path(name)/'archive'
   with self.assertRaisesRegex(ValueError,'cap'):fetch(URLS[0],path,None,3,self.opener(Response(b'1234')))
 def test_truncation_rejected(self):
  with self.temp() as name:
   with self.assertRaisesRegex(ValueError,'Truncated'):fetch(URLS[0],Path(name)/'a',4,10,self.opener(Response(b'123',headers={'Content-Length':'4'})))
 def test_complete_pinned_size_accepted_without_execution(self):
  with self.temp() as name:
   path=Path(name)/'a'
   size=fetch(URLS[0],path,4,10,self.opener(Response(b'data',headers={'Content-Length':'4'})))
   self.assertEqual(size,4);self.assertEqual(path.read_bytes(),b'data')
