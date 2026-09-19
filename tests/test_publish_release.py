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
from publish_release import beijing_day, identify_archive, next_build_number, reserve_tag, stamp_archive
import package as package_script
import publish_release


class ReleaseVersionTest(unittest.TestCase):
    def test_beijing_day_and_daily_sequence(self):
        self.assertEqual(beijing_day(datetime(2026, 9, 17, 17, tzinfo=timezone.utc)), '20260918')
        refs = ['refs/tags/v20260918(1)', 'refs/tags/v20260918(3)',
                'refs/tags/v20260917(8)', 'refs/tags/v20260918-draft']
        self.assertEqual(next_build_number(refs, '20260918'), 4)
        self.assertEqual(next_build_number(refs, '20260919'), 1)

    def test_stamped_opk_matches_release_version(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'OlivaDiceWebUI-dev.opk'
            with ZipFile(original, 'w') as archive:
                archive.writestr('app.json', json.dumps({
                    'namespace': 'OlivaDiceWebUI', 'version': 'dev'}))
                archive.writestr('main.py', 'print("ok")')
            stamped = stamp_archive(original, '20260918(2)')
            self.assertEqual(stamped.name, 'OlivaDiceWebUI-20260918.2.opk')
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('app.json'))['version'], '20260918(2)')
                self.assertEqual(archive.read('main.py'), b'print("ok")')
            self.assertEqual(stamp_archive(stamped, '20260918(2)'), stamped)
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('app.json'))['version'], '20260918(2)')

    def test_standalone_opk_uses_same_release_version(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'OlivaDiceWebUIStandalone-dev.opk'
            with ZipFile(original, 'w') as archive:
                archive.writestr('app.json', json.dumps({
                    'namespace': 'OlivaDiceWebUIStandalone', 'version': 'dev'}))
                archive.writestr('main.py', 'print("standalone")')
            namespace, base_name, label = identify_archive(original)
            self.assertEqual(namespace, 'OlivaDiceWebUIStandalone')
            self.assertEqual(base_name, 'OlivaDiceWebUIStandalone')
            self.assertIn('独立服务版', label)
            stamped = stamp_archive(original, '20260918(2)')
            self.assertEqual(stamped.name, 'OlivaDiceWebUIStandalone-20260918.2.opk')
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('app.json'))['version'], '20260918(2)')
                self.assertEqual(archive.read('main.py'), b'print("standalone")')
            self.assertEqual(stamp_archive(stamped, '20260918(2)'), stamped)
            with ZipFile(stamped) as archive:
                self.assertEqual(json.loads(archive.read('app.json'))['version'], '20260918(2)')

    def test_reservation_moves_to_next_number_after_collision(self):
        results = [SimpleNamespace(stdout='refs/tags/v20260918(1)\n', returncode=0),
                   SimpleNamespace(stderr='already exists', returncode=1),
                   SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
        with patch('publish_release.gh', side_effect=results):
            self.assertEqual(reserve_tag('owner/repo', '012345', '20260918'), 'v20260918(3)')

    def test_single_source_builds_two_self_contained_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            original_dist = package_script.DIST
            package_script.DIST = Path(directory)
            try:
                official, standalone = package_script.main()
            finally:
                package_script.DIST = original_dist
            self.assertTrue(official.name.startswith('OlivaDiceWebUI-'))
            self.assertTrue(standalone.name.startswith('OlivaDiceWebUIStandalone-'))
            with ZipFile(official) as archive:
                names = set(archive.namelist())
                self.assertIn('app.json', names)
                self.assertIn('bridge.py', names)
                self.assertIn('service.py', names)
                self.assertNotIn('server.py', names)
                self.assertFalse(any(name.startswith('OlivaDiceWebUI/') for name in names))
            with ZipFile(standalone) as archive:
                names = set(archive.namelist())
                self.assertIn('app.json', names)
                self.assertIn('server.py', names)
                self.assertIn('service.py', names)
                self.assertNotIn('bridge.py', names)
                self.assertFalse(any(name.startswith('OlivaDiceWebUIStandalone/') for name in names))

    def test_one_release_receives_both_editions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            official = root / 'official.opk'
            standalone = root / 'standalone.opk'
            with ZipFile(official, 'w') as archive:
                archive.writestr('app.json', json.dumps({
                    'namespace': 'OlivaDiceWebUI', 'version': 'dev'}))
            with ZipFile(standalone, 'w') as archive:
                archive.writestr('app.json', json.dumps({
                    'namespace': 'OlivaDiceWebUIStandalone', 'version': 'dev'}))
            result = SimpleNamespace(stdout='https://example.test/release')
            with patch.object(sys, 'argv', ['publish_release.py', str(official), str(standalone)]), \
                    patch.dict('os.environ', {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_SHA': 'abc123'}), \
                    patch('publish_release.reserve_tag', return_value='v20260920(1)'), \
                    patch('publish_release.gh', return_value=result) as mocked_gh:
                publish_release.main()
            args = mocked_gh.call_args.args
            self.assertEqual(args[:3], ('release', 'create', 'v20260920(1)'))
            self.assertTrue(any('OlivaDiceWebUI-20260920.1.opk#OlivaDice WebUI（官方接入版）' in value
                                for value in args))
            self.assertTrue(any('OlivaDiceWebUIStandalone-20260920.1.opk#OlivaDice WebUI（独立服务版）' in value
                                for value in args))


if __name__ == '__main__':
    unittest.main()
