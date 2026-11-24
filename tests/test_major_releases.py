import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('watch', Path(__file__).resolve().parents[1] / 'scripts/watch_major_releases.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def release(tag, **kwargs):
    return dict(tag_name=tag, **kwargs)


class MajorReleaseTests(unittest.TestCase):
    def test_stable_majors_not_latest_publication(self):
        releases = [release('v2.12.0'), release('v3.0.0'), release('v3.1.0'),
                    release('v4.0.0-rc.1'), release('v5.0.0', prerelease=True),
                    release('v6.0.0', draft=True), release('v4.0.0'), release('garbage')]
        self.assertEqual([r['tag_name'] for r in watch.candidates('v2.11.9', releases)], ['v3.1.0', 'v4.0.0'])

    def test_zero_major_and_already_migrated(self):
        self.assertEqual(watch.candidates('v0.14.1', [release('v0.15.0')]), [])
        self.assertEqual(len(watch.candidates('v0.14.1', [release('v1.0.0')])), 1)
        self.assertEqual(watch.candidates('v3.0.0', [release('v3.1.0'), release('v2.12.0')]), [])

    def test_closed_alert_not_recreated(self):
        key = watch.marker('owner/repo', release('v3.1.0'))
        self.assertTrue(watch.already_reported([{'state': 'closed', 'body': key}], key))
        self.assertFalse(watch.already_reported([{'pull_request': {}, 'body': key}], key))
        self.assertEqual(key, watch.marker('owner/repo', release('v3.2.0')))

    def test_pagination(self):
        from unittest.mock import patch
        with patch.object(watch, 'api', side_effect=[[{}] * 100, [{}]]) as api:
            self.assertEqual(len(list(watch.pages('repos/test/releases'))), 101)
            self.assertTrue(api.call_args.args[0].endswith('page=2'))


if __name__ == '__main__':
    unittest.main()
