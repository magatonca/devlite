"""Runtime de fixture: mktemp real, sem daemon, chroot ou mount."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from pipeline.devlite.customize.executor_worker import runtime_directories
from pipeline.devlite.customize.manifest import SpecError
ROOT=Path(__file__).resolve().parents[1]

class RuntimeDirectoryTests(unittest.TestCase):
    def test_apache_lock_template_fails_without_parent_and_works_after_preparation(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            root=Path(folder);template=str(root/'run/lock/apache2.XXXXXXXXXX')
            result=subprocess.run(['mktemp','-d',template],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            runtime_directories(root)
            self.assertEqual((root/'run/lock').stat().st_mode & 0o7777,0o1777)
            self.assertTrue((root/'run/apache2').is_dir())
            self.assertTrue((root/'var/lib/devlite-executor/lists/partial').is_dir())
            result=subprocess.run(['mktemp','-d',template],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            generated=Path(result.stdout.strip());self.assertEqual(generated.parent,root/'run/lock');generated.rmdir()

    def test_runtime_directory_preparation_refuses_symlink_escape(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            root=Path(folder)/'root';outside=Path(folder)/'outside';root.mkdir();outside.mkdir();(root/'run').symlink_to(outside)
            with self.assertRaises(SpecError):runtime_directories(root)
            self.assertEqual(list(outside.iterdir()),[])
