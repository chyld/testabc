"""Check upload activity ends on success and failure without accessing GitHub."""
import os
import json
import time
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='easy-backup-upload-test-') as temporary:
        temp = Path(temporary)
        tools = temp / 'bin'
        tools.mkdir()
        notification_log = temp / 'notification.json'
        notifier = tools / 'notify-send'
        notifier.write_text('#!/usr/bin/python3\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ["NOTIFICATION_LOG"]).write_text(json.dumps(sys.argv[1:]))\n')
        notifier.chmod(0o700)
        clone = temp / 'plugin' 
        shutil.copytree(root, clone, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        (clone / 'backend/main.py').write_text('''import json, sys, time
r = json.load(sys.stdin)
if r['op'] == 'upload':
    time.sleep(0.3)
    if r.get('token') == 'failure':
        print(json.dumps(dict(id=r['id'], ok=False, error='Upload failed')))
        sys.exit()
data = dict(r['data'])
if r['op'] == 'upload':
    data['lastCommit'] = dict(sha='abc123456789', repository='test/example')
print(json.dumps(dict(id=r['id'], ok=True, result=dict(data=data, message='Backup complete.'))))
''')
        (temp / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "PLUGIN" as Plugin
ShellRoot {
    Plugin.Service { id: service }
    property int step: 0
    property bool sawUploading: false
    Timer {
        interval: 25; running: true; repeat: true
        onTriggered: {
            if (service.uploading) sawUploading = true;
            if (!service.ready || service.busy) return;
            if (step === 0) {
                step = 1;
                service.run("upload", {token: "success"});
            } else if (step === 1) {
                if (!sawUploading || service.uploading || service.configData.lastCommit.sha !== "abc123456789") {
                    console.error("Upload completion state failed"); Qt.quit(); return;
                }
                step = 2; sawUploading = false;
                service.run("upload", {token: "failure"});
            } else {
                if (sawUploading && !service.uploading && service.error === "Upload failed" && service.configData.lastCommit.sha === "abc123456789") console.log("UPLOAD_STATE_PASS");
                else console.error("Upload error state failed");
                Qt.quit();
            }
        }
    }
}'''.replace('PLUGIN', clone.as_uri()))
        result = subprocess.run(['quickshell', '-p', str(temp / 'shell.qml')], capture_output=True, text=True, timeout=15,
            env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], NOTIFICATION_LOG=str(notification_log), QT_QPA_PLATFORM='offscreen', XDG_CONFIG_HOME=str(temp / 'config'), XDG_CACHE_HOME=str(temp / 'cache')))
        output = result.stdout + result.stderr
        if 'UPLOAD_STATE_PASS' not in output:
            raise SystemExit(output)
        for _ in range(100):
            if notification_log.exists(): break
            time.sleep(0.02)
        args = json.loads(notification_log.read_text())
        assert '--urgency=critical' in args
        assert args[-2:] == ['Easy Backup — Backup failed', 'Upload failed'], args
        print('Error popup notification verified.')
        print('Upload activity stops on success and failure; successful commit remains available.')


if __name__ == '__main__':
    main()
