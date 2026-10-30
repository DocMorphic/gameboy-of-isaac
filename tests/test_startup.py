"""Regression coverage for physical input routing and verified fast startup."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

STOCK = Path(__file__).resolve().parents[1] / 'scripts/stock'
sys.path.insert(0, str(STOCK))
import startup
spec = importlib.util.spec_from_file_location('isaac_volume', STOCK/'volume.py')
volume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(volume)


class StartupTests(unittest.TestCase):
    def test_both_physical_key_devices_are_listened_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n, name in enumerate(['ANBERNIC-keys', 'dierct-keys-polled', 'Fake Keyboard Mouse']):
                p=root/f'event{n}/device/name';p.parent.mkdir(parents=True);p.write_text(name)
            self.assertEqual(set(volume.find_devices(root, Path('/dev/input'))),
                             {Path('/dev/input/event0'), Path('/dev/input/event1')})

    def test_perceptual_volume_steps_and_mute(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(volume, 'NODE', Path(tmp)/'volume'), patch.object(volume.subprocess,'run') as call:
                self.assertEqual(volume.set_volume(1),1)
                self.assertEqual(call.call_args_list[0].args[0][-2:],['lineout volume','13'])
                self.assertEqual(call.call_args_list[1].args[0][-2:],['digital volume','63'])
                call.reset_mock();volume.set_volume(0)
                self.assertEqual(call.call_args.args[0][-2:],['digital volume','0'])

    def test_intro_skip_preserves_endings(self):
        xml=b'<cutscenes><cutscene id="1" name="Intro"><anm2part anm2="intro.anm2"/></cutscene><cutscene id="2" name="Ending"><videopart file="ending.ogv"/></cutscene></cutscenes>'
        before=ET.fromstring(xml);after=ET.fromstring(startup.without_intro(xml))
        self.assertEqual(len(after[0]),0)
        self.assertEqual(ET.tostring(before[1]),ET.tostring(after[1]))
        with self.assertRaises(ValueError):startup.without_intro(b'<cutscenes/>')

    def test_lzw_literals_and_dictionary_special_case(self):
        for codes, plain in [([(65,8),(66,9),(67,9)],b'ABC'), ([(65,8),(256,9)],b'AAA')]:
            bits=''.join(format(n,f'0{width}b') for n,width in codes)
            bits += '0' * (-len(bits)%8)
            data=int(bits,2).to_bytes(len(bits)//8,'big')
            self.assertEqual(startup.decode_lzw(struct.pack('<I',len(data))+data,0,len(plain)),plain)
        with self.assertRaises(ValueError):startup.decode_lzw(b'\xff\xff\xff\x7f',0,10)

    def test_modified_archive_is_rejected_before_patching(self):
        with tempfile.TemporaryDirectory() as tmp:
            game=Path(tmp);(game/'runtime').mkdir()
            p=game/'gamefiles/resources/packed/config.a';p.parent.mkdir(parents=True);p.write_bytes(b'changed')
            manifest={'files':{'resources/packed/config.a':{'size':7,'sha256':hashlib.sha256(b'correct').hexdigest()}}}
            (game/'runtime/steam-depot.lock.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'verification failed'):startup.prepare(game)
            self.assertFalse((game/'gamefiles/isaac.x64.hack').exists())


if __name__ == '__main__':
    unittest.main()
