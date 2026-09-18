"""Exercise picker completion through the real QML/Python channel, without a dialog."""
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='easy-backup-picker-test-') as temporary:
        clone = Path(temporary) / 'plugin'
        shutil.copytree(root, clone, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        helper = clone / 'backend/main.py'
        helper.write_text(helper.read_text().replace(
            "return dict(paths=choose(request.get('folder', False)))",
            "return dict(paths=['/tmp/picker-selected-file'])"))
        runtime = clone / 'tests/test_runtime.py'
        runtime.write_text(runtime.read_text()
            .replace('service.edit("paths", ["/tmp/example"]);', '')
            .replace('service.run("save");', 'service.run("choose");')
            .replace('service.configData.paths[0] === "/tmp/example"',
                     'service.configData.paths[0] === "/tmp/picker-selected-file"'))
        subprocess.run(['python3', str(runtime)], check=True, timeout=20)
        print('Picker result is applied and persists after reload.')


if __name__ == '__main__':
    main()
