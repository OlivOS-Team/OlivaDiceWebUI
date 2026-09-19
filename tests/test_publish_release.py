import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_release import beijing_day, next_build_number, reserve_tag, stamp_archive


class ReleaseVersionTest(unittest.TestCase):
    def test_beijing_day_and_daily_sequence(self):
        self.assertEqual(beijing_day(datetime(2026, 9, 17, 17, tzinfo=timezone.utc)), '20260918')
        refs = ['refs/tags/v20260918(1)', 'refs/tags/v20260918(3)',
                'refs/tags/v20260917(8)', 'refs/tags/v20260918-draft']
        self.assertEqual(next_build_number(refs, '20260918'), 4)
        self.assertEqual(next_build_number(refs, '20260919'), 1)

    def test_stamped_zip_matches_release_version(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'OlivaDiceWebUIStandalone-dev.zip'
            with ZipFile(original, 'w') as archive:
                archive.writestr('OlivaDiceWebUIStandalone/app.json', json.dumps({'version': 'dev'}))
                archive.writestr('OlivaDiceWebUIStandalone/main.py', 'print("ok")')
            stamped = stamp_archive(original, '20260918(2)')
            self.assertEqual(stamped.name, 'OlivaDiceWebUIStandalone-20260918.2.zip')
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('OlivaDiceWebUIStandalone/app.json'))['version'],
                                 '20260918(2)')
                self.assertEqual(archive.read('OlivaDiceWebUIStandalone/main.py'), b'print("ok")')
            self.assertEqual(stamp_archive(stamped, '20260918(2)'), stamped)
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('OlivaDiceWebUIStandalone/app.json'))['version'],
                                 '20260918(2)')

    def test_reservation_moves_to_next_number_after_collision(self):
        results = [SimpleNamespace(stdout='refs/tags/v20260918(1)\n', returncode=0),
                   SimpleNamespace(stderr='already exists', returncode=1),
                   SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
        with patch('publish_release.gh', side_effect=results):
            self.assertEqual(reserve_tag('owner/repo', '012345', '20260918'), 'v20260918(3)')


if __name__ == '__main__':
    unittest.main()
