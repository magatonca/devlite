"""Testes offline de rejeição, sem tocar na ISO original."""
import hashlib
import importlib.util
import tempfile
import subprocess
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("validar_iso", Path(__file__).resolve().parents[1] / "scripts/validar-iso.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ValidationTests(unittest.TestCase):
    def test_missing_and_duplicate_entries(self):
        line = "a" * 64 + " *" + module.NAME
        for value in ("", line + "\n" + line):
            with self.assertRaises(ValueError):
                module.expected_hash(value)
        self.assertEqual(module.expected_hash(line), "a" * 64)

    def test_invalid_digest(self):
        with self.assertRaises(ValueError):
            module.expected_hash("z" * 64 + " *" + module.NAME)

    def test_wrong_signer_or_missing_signature(self):
        self.assertFalse(module.valid_signature(""))
        self.assertFalse(module.valid_signature("[GNUPG:] VALIDSIG " + "0" * 40))
        self.assertTrue(module.valid_signature("[GNUPG:] VALIDSIG " + module.FINGERPRINT))

    def test_real_gpg_rejects_modified_checksums(self):
        source = module.ROOT / 'sources'
        keyring = source / 'verification/trustedkeys.gpg'
        if not keyring.exists():
            self.skipTest('Aquisição local necessária para teste GPG integrado')
        with tempfile.TemporaryDirectory() as folder:
            sums = Path(folder) / 'SHA256SUMS'
            sums.write_bytes((source / 'SHA256SUMS').read_bytes() + b'\nmodified\n')
            result = subprocess.run([
                'gpgv', '--homedir', str(source / 'verification'),
                '--keyring', str(keyring), '--status-fd', '1',
                str(source / 'SHA256SUMS.gpg'), str(sums)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(module.valid_signature(result.stdout))

    def test_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample"
            path.write_bytes(b"original")
            digest = hashlib.sha256(b"original").hexdigest()
            self.assertEqual(module.verify_digest(path, digest), digest)
            path.write_bytes(b"alterado")
            with self.assertRaises(ValueError):
                module.verify_digest(path, digest)


if __name__ == "__main__":
    unittest.main()
