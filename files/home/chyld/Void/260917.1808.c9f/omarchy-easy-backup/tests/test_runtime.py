"""Exercise the real QML service and Python channel in an isolated offscreen shell."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory(prefix='easy-backup-runtime-') as temporary:
        temp = Path(temporary)
        qml = '''import QtQuick
    import Quickshell
    import "REPO" as Plugin
    ShellRoot {
        Plugin.Service { id: service }
        property int step: 0
        Timer {
            interval: 50; running: true; repeat: true
            onTriggered: {
                if (service.error) { console.error(service.error); Qt.quit(); return; }
                if (!service.ready || service.busy) return;
                if (step === 0) {
                    if (service.configData.excludes.indexOf(".ssh") < 0) { console.error("Missing defaults"); Qt.quit(); return; }
                    service.edit("repository", "test/example");
                    service.edit("paths", ["/tmp/example"]);
                    step = 1;
                    service.run("save");
                } else if (step === 1) {
                    service.edit("repository", "temporary/value");
                    step = 2;
                    service.run("load");
                } else {
                    if (service.configData.repository === "test/example" && service.configData.paths[0] === "/tmp/example") console.log("EASY_BACKUP_RUNTIME_PASS");
                    else console.error("Configuration round trip failed");
                    Qt.quit();
                }
            }
        }
    }'''.replace('REPO', ROOT.as_uri())
        shell = temp / 'shell.qml'
        shell.write_text(qml)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_CONFIG_HOME=str(temp / 'config'), XDG_CACHE_HOME=str(temp / 'cache'))
        result = subprocess.run(['quickshell', '-p', str(shell)], capture_output=True, text=True, env=env, timeout=15)
        output = result.stdout + result.stderr
        if 'EASY_BACKUP_RUNTIME_PASS' not in output:
            raise SystemExit(output)
        data = json.loads((temp / 'config/omarchy/easy-backup.json').read_text())
        assert data['repository'] == 'test/example'
        assert (temp / 'config/omarchy/easy-backup.json').stat().st_mode & 0o777 == 0o600
        print('QML/Python runtime round trip passed; configuration is private.')


if __name__ == "__main__":
    main()
