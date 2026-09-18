"""Check verification state across edits, retries, and backend failures."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='easy-backup-verify-test-') as temporary:
    temp = Path(temporary)
    clone = temp / 'plugin'
    shutil.copytree(root, clone, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    (clone / 'backend/main.py').write_text('''import json, sys
r = json.load(sys.stdin)
data = r['data']
result = dict(data=data)
if r['op'] == 'verify':
    if data['repository'] == 'test/missing':
        print(json.dumps(dict(id=r['id'], ok=False, error='Repository not found')))
        sys.exit()
    data['verifiedRepository'] = data['repository']
    result['message'] = 'Verified'
print(json.dumps(dict(id=r['id'], ok=True, result=result)))
''')
    tools = temp / 'bin'
    tools.mkdir()
    notifier = tools / 'notify-send'
    notifier.write_text('#!/bin/sh\nexit 0\n')
    notifier.chmod(0o700)
    (temp / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "PLUGIN" as Plugin
ShellRoot {
    Plugin.Service { id: service }
    property int step: 0
    function check(value) {
        if (!value) { console.error("VERIFY_STATE_FAIL", step); Qt.quit(); }
        return value;
    }
    Timer {
        interval: 25; running: true; repeat: true
        onTriggered: {
            if (!service.ready || service.busy) return;
            if (step === 0) {
                service.edit("repository", "test/first");
                if (!check(!service.repositoryVerified)) return;
                service.run("verify"); step++;
            } else if (step === 1) {
                if (!check(service.repositoryVerified)) return;
                service.edit("paths", ["/tmp/example"]);
                if (!check(service.repositoryVerified)) return;
                service.edit("repository", "test/missing");
                if (!check(!service.repositoryVerified && service.message === "")) return;
                service.run("verify"); step++;
            } else if (step === 2) {
                if (!check(!service.repositoryVerified && service.error === "Repository not found")) return;
                service.edit("repository", "test/second");
                service.run("verify"); step++;
            } else {
                if (check(service.repositoryVerified && service.error === "")) console.log("VERIFY_STATE_PASS");
                Qt.quit();
            }
        }
    }
}'''.replace('PLUGIN', clone.as_uri()))
    result = subprocess.run(['quickshell', '-p', str(temp / 'shell.qml')], capture_output=True, text=True, timeout=15,
        env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], QT_QPA_PLATFORM='offscreen',
                 XDG_CONFIG_HOME=str(temp / 'config'), XDG_CACHE_HOME=str(temp / 'cache')))
    output = result.stdout + result.stderr
    assert 'VERIFY_STATE_PASS' in output and 'VERIFY_STATE_FAIL' not in output, output
    print('Verification success, address edits, failure, and retry state passed.')
