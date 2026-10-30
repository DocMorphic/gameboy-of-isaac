"""File-integrity and destination-safety tests; no game assets or hardware needed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts/isaac.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InstallerTests(unittest.TestCase):
    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../escape', '/absolute', 'tboirebirth/../../escape', 'a\\b'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    m.safe_path(Path(tmp), name)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root'
            root.mkdir()
            (root / 'escape').symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                m.safe_path(root, 'escape/file')

    def test_corrupt_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'data'
            p.write_bytes(b'original')
            expected = {'sha256': m.digest(p), 'size': 8}
            p.write_bytes(b'modified')
            with self.assertRaises(ValueError):
                m.check_file(p, expected)

    def test_zip_traversal_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            z = root / 'bad.zip'
            with zipfile.ZipFile(z, 'w') as out:
                out.writestr('../escape', b'bad')
            with self.assertRaises(ValueError):
                m.extract_port(z, root / 'out')
            self.assertFalse((root / 'escape').exists())

    def test_existing_install_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ports, pm, bundle = root / 'ports', root / 'pm', root / 'bundle'
            for p in (ports, pm, bundle):
                p.mkdir()
            for name in ('control.txt', 'runtimes/love_11.5/love.txt', 'runtimes/love_11.5/love.aarch64'):
                p = pm / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            save = ports / 'tboirebirth/conf/save.dat'
            save.parent.mkdir(parents=True)
            save.write_bytes(b'my save')
            with patch.object(m, 'verify_bundle', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                    m.install(bundle, ports, pm, True)
            self.assertEqual(save.read_bytes(), b'my save')

    def test_dry_run_then_install_verifies_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ports, pm, bundle = root / 'ports', root / 'pm', root / 'bundle'
            for p in (ports, pm, bundle):
                p.mkdir()
            for name in ('control.txt', 'runtimes/love_11.5/love.txt', 'runtimes/love_11.5/love.aarch64'):
                p = pm / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            for name in ('ports/tboirebirth/gamefiles/test', 'ports/' + m.LAUNCHER,
                         'dependencies/weston_pkg_0.2.squashfs'):
                p = bundle / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'test fixture')
            manifest = m.inventory(bundle)
            with patch.object(m, 'verify_bundle', return_value=manifest):
                m.install(bundle, ports, pm, False)
                self.assertEqual(list(ports.iterdir()), [])
                self.assertFalse((pm / 'libs').exists())
                m.install(bundle, ports, pm, True)
            self.assertEqual((ports / 'tboirebirth/gamefiles/test').read_bytes(), b'test fixture')
            self.assertEqual((pm / 'libs/weston_pkg_0.2.squashfs').read_bytes(), b'test fixture')
            self.assertTrue((ports / m.LAUNCHER).is_file())


if __name__ == '__main__':
    unittest.main()
