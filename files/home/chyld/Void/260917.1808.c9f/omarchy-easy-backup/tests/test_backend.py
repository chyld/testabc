import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backup', Path(__file__).parents[1] / 'backend/main.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(b, 'CACHE', self.root / 'cache').start()
        patch.object(b, 'CONFIG', self.root / 'settings.json').start()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.file = self.source / 'binary'
        self.file.write_bytes(b'\0\xff\n')
        self.data = dict(b.defaults(), repository='https://github.com/chyld/test.git', paths=[str(self.source)])
        self.remote = dict(branch='main', head='old', tree='old-tree', entries={}, private=True)

    def snapshot(self):
        dest = self.root / 'stage'
        dest.mkdir(exist_ok=True)
        return b.snapshot(self.data, dest)

    def test_repo_validation(self):
        self.assertEqual(b.repository(self.data['repository']), 'chyld/test')
        for value in ['https://evil.com/u/r', '../repo', 'u/..', 'u/r;echo secret']:
            with self.assertRaises(ValueError): b.repository(value)

    def test_verify_saves_repository_after_access_check(self):
        with patch.object(b, 'api', return_value=dict(private=True, permissions=dict(push=True))) as api:
            result = b.dispatch(dict(op='verify', data=self.data))
        api.assert_called_once_with('repos/chyld/test')
        self.assertEqual(result['data']['verifiedRepository'], self.data['repository'])
        self.assertIn('Write access', result['message'])
        self.assertEqual(b.load(), result['data'])

    def test_verify_rejects_unwritable_repositories_and_clears_previous_success(self):
        for info in [dict(permissions=dict(push=False)), dict(archived=True), dict(disabled=True)]:
            with self.subTest(info=info), patch.object(b, 'api', return_value=info):
                with self.assertRaises(ValueError):
                    b.dispatch(dict(op='verify', data=dict(self.data, verifiedRepository=self.data['repository'])))
                self.assertEqual(b.load()['verifiedRepository'], '')

    def test_verify_reports_github_errors(self):
        with patch.object(b, 'api', side_effect=RuntimeError('Not Found (HTTP 404)')):
            with self.assertRaisesRegex(RuntimeError, '404'):
                b.dispatch(dict(op='verify', data=self.data))
        self.assertEqual(b.load()['verifiedRepository'], '')

    def test_open_local_launches_repository_snapshot(self):
        from gi.repository import Gio
        folder = b.profile(self.data) / 'shadow'
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text('{}')
        with patch.object(Gio.AppInfo, 'launch_default_for_uri', return_value=True) as launch:
            self.assertEqual(b.dispatch(dict(op='open-local', data=self.data)), dict(opened=True))
            launch.assert_called_once_with(folder.as_uri(), None)

    def test_open_local_reports_launch_failure(self):
        from gi.repository import Gio, GLib
        folder = b.profile(self.data) / 'shadow'
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text('{}')
        with patch.object(Gio.AppInfo, 'launch_default_for_uri', side_effect=GLib.Error('Launch failed')):
            with self.assertRaisesRegex(GLib.Error, 'Launch failed'):
                b.dispatch(dict(op='open-local', data=self.data))

    def test_open_local_requires_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'Review backup'):
            b.dispatch(dict(op='open-local', data=self.data))

    def test_binary_symlink_exclusions_overlap(self):
        (self.source / 'link').symlink_to('/missing/target')
        (self.source / '.env').write_text('secret')
        self.file.chmod(0o755)
        self.data['paths'].append(str(self.file))
        entries, skipped, total = self.snapshot()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries['files/' + str(self.file).lstrip('/')]['mode'], '100755')
        self.assertEqual(entries['files/' + str(self.source / 'link').lstrip('/')]['mode'], '120000')
        self.assertIn(str(self.source / '.env'), skipped)
        self.assertEqual(total, 3 + len('/missing/target'))

    def test_missing_source_and_special_file_fail(self):
        self.data['paths'] = [str(self.root / 'missing')]
        with self.assertRaisesRegex(ValueError, 'missing'): self.snapshot()
        import os
        os.mkfifo(self.source / 'pipe')
        self.data['paths'] = [str(self.source)]
        with self.assertRaisesRegex(ValueError, 'pipe'): self.snapshot()

    def test_cache_is_excluded(self):
        b.CACHE.mkdir()
        (b.CACHE / 'private').write_text('private')
        self.data['paths'] = [str(self.root)]
        # Keep destination outside the selected source.
        with tempfile.TemporaryDirectory() as dest:
            entries, skipped, _ = b.snapshot(self.data, Path(dest))
        self.assertIn(str(b.CACHE), skipped)
        self.assertFalse(any('private' in p for p in entries))

    def test_changes_include_mode_and_deletion(self):
        self.assertEqual(b.changes({'old': {}, 'mode': {'mode': '100644'}}, {'new': {}, 'mode': {'mode': '100755'}}),
                         dict(added=['new'], removed=['old'], modified=['mode']))

    def stage(self):
        with patch.object(b, 'remote', return_value=self.remote):
            return b.stage(self.data)

    def test_snapshot_is_used_and_commit_is_saved(self):
        review = self.stage()
        self.file.write_text('source changed after review')
        def push(repo, shadow, entries, current, timestamp):
            self.assertEqual((shadow / ('files/' + str(self.file).lstrip('/'))).read_bytes(), b'\0\xff\n')
            return 'new-commit'
        with patch.object(b, 'remote', return_value=self.remote), patch.object(b, 'push_snapshot', side_effect=push):
            result = b.upload(self.data, review['token'])
        self.assertEqual(result['message'], 'Backup complete.')
        self.assertEqual(result['data']['lastCommit'], {'sha': 'new-commit', 'repository': 'chyld/test'})
        self.assertTrue(json.loads(b.CONFIG.read_text())['lastBackup'])

    def test_remote_race_and_tampering_prevent_writes(self):
        review = self.stage()
        with patch.object(b, 'remote', return_value=dict(self.remote, head='raced')), patch.object(b, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'changed on GitHub'): b.upload(self.data, review['token'])
            api.assert_not_called()
        shadow = next(b.CACHE.glob('*/shadow'))
        (shadow / ('files/' + str(self.file).lstrip('/'))).write_text('tampered')
        with patch.object(b, 'remote', return_value=self.remote), patch.object(b, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'shadow copy changed'): b.upload(self.data, review['token'])
            api.assert_not_called()

    def test_upload_failure_keeps_snapshot_and_last_success(self):
        review = self.stage()
        with patch.object(b, 'remote', return_value=self.remote), patch.object(b, 'push_snapshot', side_effect=RuntimeError('network failed')):
            with self.assertRaisesRegex(RuntimeError, 'network failed'): b.upload(self.data, review['token'])
        self.assertTrue(next(b.CACHE.glob('*/shadow/manifest.json')).exists())
        self.assertFalse(b.CONFIG.exists())

    def test_unchanged_does_not_write(self):
        review = self.stage()
        manifest = json.loads(next(b.CACHE.glob('*/shadow/manifest.json')).read_text())
        with patch.object(b, 'remote', return_value=dict(self.remote, entries=manifest['entries'])), patch.object(b, 'api') as api:
            result = b.upload(self.data, review['token'])
            self.assertEqual(result['message'], 'Already up to date.')
            self.assertEqual(result['data']['lastCommit']['sha'], 'old')
            api.assert_not_called()

    def test_file_above_previous_25_mib_cap(self):
        content = b'x' * (26 * 1024 * 1024)
        self.file.write_bytes(content)
        entries, _, total = self.snapshot()
        self.assertEqual(total, len(content))
        entry = entries['files/' + str(self.file).lstrip('/')]
        self.assertEqual(entry['sha'], b.blob_sha(content))
        self.assertEqual((self.root / 'stage' / ('files/' + str(self.file).lstrip('/'))).read_bytes(), content)

    def test_total_snapshot_limit(self):
        with patch.object(b, 'MAX_TOTAL', 1):
            with self.assertRaisesRegex(ValueError, 'limit'): self.snapshot()

    def test_legacy_config_removes_computer_fields(self):
        old = dict(self.data, computer='origin', deviceId='a' * 32)
        b.atomic(b.CONFIG, old)
        first = b.load()
        self.assertNotIn('computer', first)
        self.assertNotIn('deviceId', first)
        self.assertEqual(first, self.data)
        self.assertEqual(b.load(), first)

    def test_review_shows_removal_of_old_layout(self):
        self.remote['entries'] = {'computers/origin/files/old': dict(sha='old', mode='100644')}
        review = self.stage()
        self.assertEqual(review['changes']['removed'], ['computers/origin/files/old'])
        self.assertEqual(review['count'], 1)

    def test_remote_reads_root_entries_without_downloading_files(self):
        responses = [dict(default_branch='main', private=True, permissions=dict(push=True)),
                     [{}], dict(object=dict(sha='head')), dict(tree=dict(sha='tree')),
                     dict(tree=[dict(path='files', type='tree', sha='subtree', mode='040000'),
                                dict(path='files/test', type='blob', sha='blob', mode='100644')])]
        with patch.object(b, 'api', side_effect=responses) as api:
            state = b.remote('test/backup')
        self.assertEqual(state['entries'], {'files/test': dict(sha='blob', mode='100644')})
        self.assertEqual(api.call_args.args[0], 'repos/test/backup/git/trees/tree?recursive=1')



class GitUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = self.root / 'server.git'
        b.git(self.server, ['init', '--bare', '--template=', str(self.server)])
        b.git(self.server, ['config', 'uploadpack.allowFilter', 'true'])
        self.shadow = self.root / 'profile/shadow'
        (self.shadow / 'files').mkdir(parents=True)
        (self.shadow / 'files/binary').write_bytes(b'\x00\xff\r\n')
        (self.shadow / 'files/link').write_bytes(b'/missing/target')
        self.entries = {
            'files/binary': dict(sha=b.blob_sha(b'\x00\xff\r\n'), mode='100755'),
            'files/link': dict(sha=b.blob_sha(b'/missing/target'), mode='120000'),
        }
        self.addCleanup(patch.stopall)
        patch.object(b, 'remote_url', return_value=self.server.as_uri()).start()
        patch.object(b, 'api', return_value=dict(login='tester', id=123)).start()
        self.empty = dict(branch='main', head=None)

    def push(self, current):
        return b.push_snapshot('test/backup', self.shadow, self.entries, current, '2026-09-17')

    def test_empty_repo_one_commit_preserves_binary_and_modes(self):
        commit = self.push(self.empty)
        self.assertEqual(b.git(self.server, ['rev-parse', 'main']), commit)
        self.assertEqual(b.git(self.server, ['rev-list', '--count', 'main']), '1')
        tree = b.git(self.server, ['ls-tree', '-r', 'main'])
        for name, entry in self.entries.items():
            self.assertIn(entry['mode'] + ' blob ' + entry['sha'] + '\t' + name, tree)

    def test_subsequent_backup_deletes_removed_files(self):
        first = self.push(self.empty)
        del self.entries['files/link']
        second = self.push(dict(branch='main', head=first))
        self.assertEqual(b.git(self.server, ['rev-parse', second + '^']), first)
        self.assertNotIn('files/link', b.git(self.server, ['ls-tree', '-r', 'main']))

    def change_content(self):
        content = b'changed snapshot'
        (self.shadow / 'files/binary').write_bytes(content)
        self.entries['files/binary']['sha'] = b.blob_sha(content)

    def test_remote_change_after_review_prevents_push(self):
        self.push(self.empty)
        self.change_content()
        with self.assertRaisesRegex(ValueError, 'changed on GitHub'):
            self.push(self.empty)

    def test_old_layout_is_replaced_without_downloading_blobs(self):
        identity = dict(GIT_AUTHOR_NAME='seed', GIT_AUTHOR_EMAIL='seed@example.com',
                        GIT_COMMITTER_NAME='seed', GIT_COMMITTER_EMAIL='seed@example.com')
        blob = b.git(self.server, ['hash-object', '-w', '--stdin'], content=b'old-layout-content')
        tree = b.git(self.server, ['mktree'], content=('100644 blob ' + blob + '\tlegacy.txt\n').encode())
        seed = b.git(self.server, ['commit-tree', tree], content=b'Old backup', identity=identity)
        b.git(self.server, ['update-ref', 'refs/heads/main', seed])
        result = self.push(dict(branch='main', head=seed))
        self.assertNotIn('legacy.txt', b.git(self.server, ['ls-tree', '-r', result]))
        self.assertEqual(b.git(self.server, ['rev-parse', result + '^']), seed)
        objects = b.git(self.shadow.parent / 'git-partial', ['cat-file', '--batch-all-objects', '--batch-check=%(objectname)'])
        self.assertNotIn(blob, objects)

    def test_concurrent_push_is_rejected(self):
        first = self.push(self.empty)
        self.change_content()
        original = b.git
        peer = []
        def racing_git(directory, args, **kwargs):
            if args[0] == 'push' and not peer:
                tree = original(self.server, ['mktree'], content=b'')
                identity = dict(GIT_AUTHOR_NAME='peer', GIT_AUTHOR_EMAIL='peer@example.com',
                                GIT_COMMITTER_NAME='peer', GIT_COMMITTER_EMAIL='peer@example.com')
                peer.append(original(self.server, ['commit-tree', tree, '-p', first], content=b'Concurrent change', identity=identity))
                original(self.server, ['update-ref', 'refs/heads/main', peer[0]])
            return original(directory, args, **kwargs)
        with patch.object(b, 'git', side_effect=racing_git):
            with self.assertRaisesRegex(ValueError, 'repository changed'):
                self.push(dict(branch='main', head=first))
        self.assertEqual(original(self.server, ['rev-parse', 'main']), peer[0])


if __name__ == '__main__': unittest.main()
