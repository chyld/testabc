#!/usr/bin/env python3
"""Easy Backup helper. JSON requests on stdin; JSON responses on stdout."""
import datetime
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'omarchy/easy-backup.json'
CACHE = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'omarchy/easy-backup'
MAX_TOTAL = 250 * 1024 * 1024
MAX_FILES = 10000
DEFAULT_EXCLUDES = ['.cache', '__pycache__', 'node_modules', '.ssh', '.gnupg', '.env', '.env.*', '*.pem', '*.key']


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def defaults():
    return dict(version=1, repository='', paths=[], excludes=DEFAULT_EXCLUDES, lastBackup='')


def validate(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported configuration.')
    if not isinstance(data.get('repository'), str):
        raise ValueError('Repository must be a URL or owner/name.')
    data = {k: v for k, v in data.items() if k not in ('computer', 'deviceId')}
    for key in ['paths', 'excludes']:
        if not isinstance(data.get(key), list) or len(data[key]) > 1000 or any(not isinstance(x, str) or not x or '\x00' in x for x in data[key]):
            raise ValueError('Invalid ' + key)
    if any(not Path(p).is_absolute() for p in data['paths']):
        raise ValueError('Choose absolute source paths.')
    data['excludes'] = [pattern for pattern in data['excludes'] if pattern != '.git']
    return data


def load():
    data = json.loads(CONFIG.read_text()) if CONFIG.exists() else defaults()
    original = dict(data)
    data = validate(data)
    if data != original or not CONFIG.exists():
        atomic(CONFIG, data)
    return data


def repository(value):
    value = value.strip().removeprefix('https://github.com/').removeprefix('git@github.com:').rstrip('/').removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', value) or value.split('/')[1] in ['.', '..']:
        raise ValueError('Enter a github.com repository URL or owner/name.')
    return value


def api(endpoint, payload=None, method=None):
    cmd = ['gh', 'api', '--hostname', 'github.com', endpoint]
    if payload is not None:
        cmd += ['--method', method or 'POST', '--input', '-']
    result = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, timeout=120,
                            env={**os.environ, 'GH_PROMPT_DISABLED': '1'})
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1200] or 'GitHub request failed. Run gh auth login in a terminal.')
    return json.loads(result.stdout)


def verify_repository(repo):
    info = api('repos/' + repo)
    if info.get('archived') or info.get('disabled'):
        raise ValueError('This repository is archived or disabled and cannot receive backups.')
    if not info.get('permissions', {}).get('push', False):
        raise ValueError('Your GitHub account needs write access to this repository.')
    return info


def remote(repo):
    prefix = 'repos/' + repo
    info = verify_repository(repo)
    state = dict(branch=info['default_branch'], head=None, tree=None,
                 entries={}, private=info['private'])
    if not api(prefix + '/branches?per_page=1'):
        return state
    ref = api(prefix + '/git/ref/heads/' + quote(state['branch'], safe=''))
    state['head'] = ref['object']['sha']
    commit = api(prefix + '/git/commits/' + state['head'])
    state['tree'] = commit['tree']['sha']
    tree = api(prefix + '/git/trees/' + state['tree'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Repository is too large to review safely.')
    state['entries'] = {e['path']: {k: e[k] for k in ('sha', 'mode')}
                        for e in tree['tree'] if e['type'] != 'tree'}
    return state


def profile(data):
    repo = repository(data['repository'])
    return CACHE / hashlib.sha256(repo.lower().encode()).hexdigest()[:16]


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def snapshot(data, destination):
    entries, skipped = {}, set()
    total = 0
    cache_real = CACHE.resolve()

    def visit(path):
        nonlocal total
        # Never recursively back up the shadow directory, even through an alias.
        if path.resolve().is_relative_to(cache_real):
            skipped.add(str(path)); return
        if any(fnmatch.fnmatch(part, pattern) for part in path.parts for pattern in data['excludes']) or '.git' in path.parts:
            skipped.add(str(path)); return
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)
            return
        if stat.S_ISLNK(info.st_mode):
            content, mode = os.fsencode(os.readlink(path)), '120000'
        elif stat.S_ISREG(info.st_mode):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError(f'Not a regular file: {path}')
                content = stream.read(MAX_TOTAL + 1)
                if len(content) > MAX_TOTAL:
                    raise ValueError('Backup exceeds the 250 MiB total snapshot limit.')
                after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError(f'File changed during staging; try again: {path}')
            mode = '100755' if before.st_mode & 0o111 else '100644'
        else:
            raise ValueError(f'Cannot back up a device, socket, or pipe: {path}')
        name = 'files/' + str(path).lstrip('/')
        if name in entries:
            return
        total += len(content)
        if total > MAX_TOTAL or len(entries) >= MAX_FILES:
            raise ValueError('Backup exceeds the 250 MiB or 10,000 file limit.')
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(content)
        entries[name] = dict(sha=blob_sha(content), mode=mode)

    for source in data['paths']:
        path = Path(os.path.abspath(source))
        if not path.exists() and not path.is_symlink():
            raise ValueError(f'Selected source is missing: {path}. Remove it from the selection to remove it from the backup.')
        visit(path)
    if not entries:
        raise ValueError('No files to back up. Check your selections and exclusions.')
    return entries, sorted(skipped), total


def changes(old, new):
    return dict(added=sorted(new.keys() - old.keys()), removed=sorted(old.keys() - new.keys()),
                modified=sorted(k for k in old.keys() & new.keys() if old[k] != new[k]))


def stage(data):
    repo = repository(data['repository'])
    state = remote(repo)
    folder = profile(data)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    work = Path(tempfile.mkdtemp(prefix='staging-', dir=folder))
    try:
        entries, skipped, total = snapshot(data, work)
        review = dict(repository=repo, remote=state, entries=entries, skipped=skipped, bytes=total,
                      changes=changes(state['entries'], entries), settings=data,
                      token=os.urandom(16).hex())
        atomic(work / 'manifest.json', review)
        shadow = folder / 'shadow'
        if shadow.exists():
            shutil.rmtree(shadow)
        work.rename(shadow)
        return dict(token=review['token'], repository=repo, branch=state['branch'], private=state['private'],
                    changes=review['changes'], skipped=skipped, bytes=total, count=len(entries))
    finally:
        if work.exists():
            shutil.rmtree(work)


def remote_url(repo):
    return 'https://github.com/' + repo + '.git'


def git(directory, args, content=None, stream=None, identity=None):
    # Isolate backup objects from user filters, signing, hooks, and Git overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1', GH_PROMPT_DISABLED='1')
    if identity:
        env.update(identity)
    command = ['git', '--git-dir=' + str(directory),
               '-c', 'core.hooksPath=/dev/null', '-c', 'credential.helper=',
               '-c', 'credential.helper=!gh auth git-credential',
               '-c', 'commit.gpgsign=false', *args]
    result = subprocess.run(command, input=content, stdin=stream, capture_output=True,
                            timeout=600, env=env)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode(errors='replace').strip()
        raise RuntimeError('Git ' + args[0] + ' failed: ' + detail[-1200:])
    return result.stdout.decode().strip()


def push_snapshot(repo, shadow, entries, current, timestamp):
    directory = shadow.parent / 'git-partial'
    git(directory, ['init', '--bare', '--template=', '--object-format=sha1', str(directory)])
    url = remote_url(repo)
    git(directory, ['config', 'remote.origin.url', url])
    git(directory, ['config', 'remote.origin.promisor', 'true'])
    git(directory, ['config', 'remote.origin.partialclonefilter', 'blob:none'])
    branch = 'refs/heads/' + current['branch']
    git(directory, ['check-ref-format', branch])
    git(directory, ['read-tree', '--empty'])
    index = bytearray()
    for name, entry in entries.items():
        with (shadow / name).open('rb') as source:
            sha = git(directory, ['hash-object', '-w', '--stdin'], stream=source)
        if sha != entry['sha']:
            raise ValueError('The shadow copy changed. Review again.')
        index.extend((entry['mode'] + ' ' + sha + '\t' + name).encode() + b'\0')
    git(directory, ['update-index', '-z', '--index-info'], content=bytes(index))
    own_tree = git(directory, ['write-tree'])
    account = api('user')
    identity = dict(GIT_AUTHOR_NAME=account['login'], GIT_COMMITTER_NAME=account['login'],
                    GIT_AUTHOR_EMAIL=f"{account['id']}+{account['login']}@users.noreply.github.com",
                    GIT_COMMITTER_EMAIL=f"{account['id']}+{account['login']}@users.noreply.github.com")
    refs = git(directory, ['ls-remote', '--heads', 'origin', branch])
    head = refs.split()[0] if refs else None
    if head != current['head']:
        raise ValueError('The repository changed on GitHub. Review again before uploading.')
    if head:
        git(directory, ['fetch', '--no-tags', '--depth=1', '--filter=blob:none', 'origin', branch])
        if git(directory, ['rev-parse', 'FETCH_HEAD']) != head:
            raise ValueError('The repository changed on GitHub. Review again before uploading.')
    args = ['commit-tree', own_tree] + (['-p', head] if head else [])
    commit = git(directory, args, content=('Easy Backup: ' + timestamp + '\n').encode(), identity=identity)
    try:
        git(directory, ['push', '--porcelain', 'origin', commit + ':' + branch])
    except RuntimeError:
        latest = git(directory, ['ls-remote', '--heads', 'origin', branch])
        latest_head = latest.split()[0] if latest else None
        if latest_head == commit:
            return commit
        if latest_head != head:
            raise ValueError('The repository changed on GitHub. Review again before uploading.')
        raise
    return commit


def upload(data, token):
    repo = repository(data['repository'])
    shadow = profile(data) / 'shadow'
    review = json.loads((shadow / 'manifest.json').read_text())
    if review['token'] != token or review['settings'] != data:
        raise ValueError('Settings changed. Review the backup again.')
    current = remote(repo)
    if current['head'] != review['remote']['head'] or current['branch'] != review['remote']['branch']:
        raise ValueError('The repository changed on GitHub. Review again before uploading.')
    entries = review['entries']
    # Check the entire staged snapshot before any remote mutation.
    for name, entry in entries.items():
        if blob_sha((shadow / name).read_bytes()) != entry['sha']:
            raise ValueError('The shadow copy changed. Review again.')
    if current['entries'] == entries:
        data = dict(data, lastCommit=dict(sha=current['head'], repository=repo))
        atomic(CONFIG, data)
        return dict(message='Already up to date.', data=data)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    commit_sha = push_snapshot(repo, shadow, entries, current, timestamp)
    data = dict(data, lastBackup=timestamp, lastCommit=dict(sha=commit_sha, repository=repo))
    atomic(CONFIG, data)
    return dict(message='Backup complete.', data=data)


def choose(folder):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib
    Gtk.init()
    loop, paths = GLib.MainLoop(), []
    dialog = Gtk.FileChooserNative.new('Choose folders to back up' if folder else 'Choose files to back up', None,
        Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN, 'Add', 'Cancel')
    dialog.set_select_multiple(True)
    def response(chooser, code):
        if code == Gtk.ResponseType.ACCEPT:
            files = chooser.get_files()
            for index in range(files.get_n_items()):
                path = files.get_item(index).get_path()
                if path:
                    paths.append(path)
        chooser.destroy()
        loop.quit()
    dialog.connect('response', response)
    dialog.show()
    loop.run()
    return paths


def dispatch(request):
    op = request['op']
    if op == 'load':
        return dict(data=load())
    if op == 'choose':
        return dict(paths=choose(request.get('folder', False)))
    data = validate(request['data'])
    if op == 'verify':
        data = dict(data, verifiedRepository='')
        atomic(CONFIG, data)
        info = verify_repository(repository(data['repository']))
        data = dict(data, verifiedRepository=data['repository'])
        atomic(CONFIG, data)
        return dict(data=data, message='Verified · Write access · ' + ('Private' if info['private'] else 'Public'))
    if op == 'open-local':
        folder = profile(data) / 'shadow'
        if not (folder / 'manifest.json').is_file():
            raise ValueError('No local backup yet. Click Review backup to create a snapshot first.')
        from gi.repository import Gio
        # Ask the desktop to launch the registered handler. Waiting on xdg-open
        # can wait for the file manager itself (or its inherited output pipes).
        if not Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None):
            raise RuntimeError('Could not open the default file manager.')
        return dict(opened=True)
    if op == 'save':
        atomic(CONFIG, data)
        return dict(data=data)
    if op == 'stage':
        atomic(CONFIG, data)
        return stage(data)
    if op == 'upload':
        return upload(data, request['token'])
    raise ValueError('Unknown operation.')


def main():
    os.umask(0o077)
    request = {}
    try:
        request = json.loads(sys.stdin.read(1048577))
        CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (CACHE / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = dispatch(request)
        response = dict(id=request.get('id'), ok=True, result=result)
    except Exception as error:
        response = dict(id=request.get('id'), ok=False, error=str(error)[:1500])
    print(json.dumps(response))


if __name__ == '__main__':
    main()
