from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / 'linuxfs/overlay/usr/local/bin/droiddeck-cjk-face'


def rules(face):
    return subprocess.run(['sh', str(SCRIPT), face], capture_output=True, text=True, check=True).stdout


class CjkFaceTest(unittest.TestCase):
    def test_face_goes_before_each_generic_family_and_last(self):
        root = ET.fromstring(rules('TC'))
        matches = root.findall('match')
        self.assertEqual(4, len(matches))
        for match, generic in zip(matches, ['sans-serif', 'serif', 'monospace']):
            self.assertEqual(generic, match.find('test').find('string').text)
            self.assertEqual('family', match.find('test').get('name'))
            self.assertEqual('prepend', match.find('edit').get('mode'))
            self.assertEqual('Noto Sans CJK TC', match.find('edit').find('string').text)
        last = matches[3]
        self.assertIsNone(last.find('test'))
        self.assertEqual('append_last', last.find('edit').get('mode'))
        self.assertEqual('Noto Sans CJK TC', last.find('edit').find('string').text)

    def test_untagged_text_never_tests_a_language(self):
        for face in ['SC', 'TC', 'HK', 'JP', 'KR']:
            text = rules(face)
            self.assertIn('Noto Sans CJK ' + face, text)
            self.assertNotIn('name="lang"', text)

    def test_other_languages_get_no_rules(self):
        for face in ['', 'EN', 'tc', 'Noto Sans CJK TC']:
            self.assertEqual('', rules(face))


if __name__ == '__main__':
    unittest.main()
