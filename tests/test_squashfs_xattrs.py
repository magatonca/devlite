"""Ausência comprovada de tabela xattr não equivale a ignorar erros genéricos."""
import errno
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import minimal_root as meta,release_resume as resume,release_pack as pack
from pipeline.devlite.customize.manifest import SpecError


class XattrAbsenceTests(unittest.TestCase):
    def temp(self):return tempfile.TemporaryDirectory(dir=resume.ROOT/'work')
    def header(self,root,table=0xffffffffffffffff):
        header=bytearray(256);struct.pack_into('<I',header,0,0x73717368);struct.pack_into('<HH',header,28,4,0)
        struct.pack_into('<Q',header,40,256);struct.pack_into('<Q',header,56,table)
        p=root/'fixture.sqfs';p.write_bytes(header);return p

    def test_no_table_and_empty_expected_provides_exact_path_allowlist(self):
        with self.temp() as folder:
            image=self.header(Path(folder));self.assertEqual(resume.absent_xattrs(image,{'.':{'xattrs':{}},'file':{'xattrs':{}}}),frozenset({'.','file'}))

    def test_missing_capability_table_cannot_be_approved(self):
        with self.temp() as folder:
            image=self.header(Path(folder))
            with self.assertRaises(SpecError):resume.absent_xattrs(image,{'file':{'xattrs':{'security.capability':'expected'}}})

    def test_existing_table_never_allows_unsupported_xattrs(self):
        with self.temp() as folder:self.assertFalse(resume.absent_xattrs(self.header(Path(folder),128),{'.':{'xattrs':{}}}))

    def test_invalid_header_and_out_of_bounds_table_are_rejected(self):
        with self.temp() as folder:
            image=self.header(Path(folder),257)
            with self.assertRaises(SpecError):resume.absent_xattrs(image,{})
            image.write_bytes(b'not squashfs')
            with self.assertRaises(SpecError):resume.absent_xattrs(image,{})

    def test_eopnotsupp_requires_exact_path_proof(self):
        with patch.object(meta.os,'listxattr',side_effect=OSError(errno.EOPNOTSUPP,'no table')):
            self.assertEqual(meta.read_xattrs(Path('/fixture'),'.',frozenset({'.'})),{})
            with self.assertRaises(OSError):meta.read_xattrs(Path('/fixture'),'unlisted',frozenset({'.'}))
            with self.assertRaises(OSError):meta.read_xattrs(Path('/fixture'),'.',frozenset())

    def test_io_and_access_errors_remain_fatal_despite_absence_proof(self):
        for error in (errno.EIO,errno.EACCES,errno.EPERM):
            with self.subTest(error=error),patch.object(meta.os,'listxattr',side_effect=OSError(error,'failure')):
                with self.assertRaises(OSError):meta.read_xattrs(Path('/fixture'),'.',frozenset({'.'}))

    def test_reported_keys_and_getxattr_failures_are_never_discarded(self):
        with patch.object(meta.os,'listxattr',return_value=['security.capability']),patch.object(meta.os,'getxattr',side_effect=OSError(errno.EOPNOTSUPP,'failure')):
            with self.assertRaises(OSError):meta.read_xattrs(Path('/fixture'),'.',frozenset({'.'}))

    def test_snapshot_with_proof_preserves_every_other_metadata_field(self):
        with self.temp() as folder:
            root=Path(folder)/'tree';root.mkdir();(root/'file').write_bytes(b'content');expected=meta.snapshot(root)
            with patch.object(meta.os,'listxattr',side_effect=OSError(errno.EOPNOTSUPP,'no table')):
                self.assertEqual(meta.snapshot(root,xattr_absence=frozenset(expected)),expected)
                with self.assertRaises(OSError):meta.snapshot(root)

    def test_existing_unexpected_attribute_is_still_detected(self):
        with self.temp() as folder:
            root=Path(folder)/'tree';root.mkdir();expected=meta.snapshot(root)
            with patch.object(meta.os,'listxattr',return_value=['user.unexpected']),patch.object(meta.os,'getxattr',return_value=b'changed'):
                with self.assertRaises(SpecError):resume.checked_snapshot(root,expected,'fixture',frozenset(expected))

    @unittest.skipUnless(shutil.which('mksquashfs'),'mksquashfs ausente')
    def test_real_tableless_squashfs_without_mounts(self):
        with self.temp() as folder:
            root=Path(folder);source=root/'source';source.mkdir();(source/'file').write_text('fixture');expected=meta.snapshot(source)
            image=root/'real.sqfs';args=pack.compress_args(source,image,expected['.']);args[args.index('256M')]='32M'
            subprocess.run(args,check=True,capture_output=True)
            self.assertEqual(resume.absent_xattrs(image,expected),frozenset(expected))
