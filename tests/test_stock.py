"""Check stock adaptation patches without commercial assets or target hardware."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('stock', SCRIPTS / 'install-stock.py')
stock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stock)


class StockTests(unittest.TestCase):
    def test_binary_patch_rejects_unknown_and_duplicate_matches(self):
        good = b'fixture'.join(bytes.fromhex(x) for x, _ in stock.PATCHES)
        result = stock.patch_binary(good)
        self.assertEqual(len(result), len(good))
        self.assertNotEqual(result, good)
        for data in (b'unrelated executable', good + good, result):
            with self.assertRaises(ValueError):
                stock.patch_binary(data)

    def test_menu_bindings_preserve_shooting_and_start_select(self):
        original = '5-0="68" 7-0="83" 14-0="32" 14-1="257" 15-0="256" 15-1="-1"'
        result = stock.menu_buttons(original)
        self.assertEqual(result, '5-0="68" 7-0="83" 14-0="68" 14-1="257" 15-0="256" 15-1="83"')
        self.assertEqual(stock.menu_buttons(result), result)
        with self.assertRaises(ValueError):
            stock.menu_buttons('unexpected configuration')

    def test_stock_existing_saves_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save = root / 'tboirebirth/conf/save'
            save.parent.mkdir(parents=True)
            save.write_bytes(b'keep my progress')
            with patch.object(stock, 'check_hardware'), patch.object(stock.isaac, 'verify_bundle', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                    stock.install(root / 'bundle', root, True)
            self.assertEqual(save.read_bytes(), b'keep my progress')


if __name__ == '__main__':
    unittest.main()
