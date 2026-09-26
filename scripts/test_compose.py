"""使用合成色块验证结构，不使用或公开私人照片。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

SCRIPT = Path(__file__).with_name('compose.py')


class ComposeTest(unittest.TestCase):
    def test_structure_and_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo, lower, out = root/'photo.png', root/'lower.png', root/'poster.png'
            image = Image.new('RGB', (600, 400))
            image.putdata([(x % 256, y % 256, (x+y) % 256) for y in range(400) for x in range(600)])
            image.save(photo)
            Image.new('RGB', (600, 400), '#f3eddf').save(lower)
            cmd = [sys.executable, str(SCRIPT), '--photo', str(photo), '--lower', str(lower), '--output', str(out), '--width', '600']
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with Image.open(out) as poster:
                self.assertEqual(poster.size, (600, 800))
                self.assertEqual(poster.crop((0, 0, 600, 400)).tobytes(), image.tobytes())
                self.assertEqual(poster.getpixel((300, 400)), (243, 237, 223))
            self.assertTrue(json.loads(out.with_suffix('.json').read_text())['upper_matches_source_transform'])
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            # Portrait subject cannot fit the 3:2 crop without clipping.
            Image.new('RGB', (400, 600)).save(photo)
            cmd[cmd.index('--output') + 1] = str(root/'portrait.png')
            self.assertNotEqual(subprocess.run(cmd + ['--subject-box', '0,0,1,1'], capture_output=True).returncode, 0)
            Image.new('RGB', (600, 400)).save(photo)
            Image.new('RGB', (400, 400)).save(lower)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(cmd + ['--crop-lower'], capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
