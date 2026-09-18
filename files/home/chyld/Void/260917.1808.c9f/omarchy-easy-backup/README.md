# Easy Backup

Back up files and folders from across your filesystem to a dedicated GitHub repository.

## Use

1. Install Git, `github-cli`, Python 3, PyGObject, and GTK 4 on an Omarchy Quattro desktop. Authenticate once with `gh auth login`.
2. Install the plugin:

   ```sh
   omarchy plugin add https://github.com/chyld/omarchy-easy-backup.git --enable
   omarchy restart shell
   ```

3. Click the backup icon beside PinDeck (or wherever you place it in your bar).
4. Enter the URL of a **dedicated backup repository for this computer** and click **Verify** to check that it exists, is writable, and is not archived or disabled. After verification, open **Files & folders → Manage** to add files or folders using the native picker. The selected paths and remove controls live in this separate view. Both pickers support multiple selections.
5. Click **Review backup** to create a local snapshot and compare it with GitHub. Review additions, modifications, removals, exclusions, and repository visibility.
6. Click **Back up now** to upload the reviewed snapshot using Git on the repository's default branch, authenticated through `gh`. The bar icon and panel spinner animate while uploading and stop when the request finishes. A successful backup shows a clickable commit ID, saved for the next session. Errors produce a desktop popup notification even when the panel is closed, and remain visible in the panel.

The plugin source repository and your backup destination are separate repositories. No files are uploaded until you click **Back up now**.

## Storage and behavior

Settings live in `~/.config/omarchy/easy-backup.json`. Shadow copies live in `~/.cache/omarchy/easy-backup/<repository-id>/shadow/`. XDG configuration and cache overrides are respected. A bare Git object store lives alongside the shadow directory at `<repository-id>/git-partial/`. Local settings, snapshots, and Git objects are private to your user. Create a snapshot with **Review backup** first. Clearing the cache is safe; review again to rebuild it.

Absolute paths are preserved: `/home/alex/notes.txt` becomes `files/home/alex/notes.txt` in the backup repository. The shadow directory contains actual copies. Symlink targets are staged as text and uploaded as Git symlinks; targets are not traversed. Executable bits are preserved. Empty folders, ownership, ACLs, timestamps, and extended attributes are not backed up.

Use **one repository per computer**. The repository's default branch contains the reviewed snapshot under a single `files/` root. Files outside the snapshot are shown as removals during review and removed by the next backup. Previous versions remain in Git history. Removing a selection removes those files from the next backup. A missing selected source stops the backup so an unmounted drive cannot silently erase its contents from the current version.

The editable default exclusions omit `.cache`, `__pycache__`, `node_modules`, `.ssh`, `.gnupg`, `.env`, `.env.*`, `*.pem`, and `*.key`. Patterns match any path component. The `.git` name and Easy Backup's own cache are always excluded. Use the header’s settings button to open **Advanced settings** to edit the exclusion list in a separate view, then click **Save exclusions**. Returning without saving discards those edits. These are convenience exclusions, not a comprehensive secret scanner; backups are not encrypted.

Each changed snapshot becomes a commit. Empty repositories receive the complete snapshot in their first commit. No-change backups do not create commits. Uploads never force-push. Changes on GitHub after review require a fresh review before uploading. Failed uploads keep the shadow copy and local Git objects for retry. Commits become visible on GitHub only after a successful push.

Version 0.1 supports one destination, manual backups, at most 10,000 files and 250 MiB total per snapshot. There is no separate per-file size cap in the plugin; GitHub enforces its own file limits. Unreadable sources and special files stop staging with an error. It never requests elevated permissions. The repository address saves when you click **Verify** (or press Enter). Editing it clears verification and disables backup until verified again. Verification checks current account access; uploads still check GitHub for errors and branch restrictions. Use **Save exclusions** in Advanced settings after editing patterns; selections and reviewed settings save automatically. Use **GitHub ↗** to open the repository in your browser. Restore through GitHub or a normal Git checkout; a restore interface is not included yet.

## Upgrading from the shared-repository layout

Existing selections and repository settings are preserved; computer names and device identities are removed from local settings. New snapshots use the repository-level cache and `files/` at the repository root. Review shows any old `computers/` paths as removals. Use a separate repository for each computer before uploading a new snapshot. Old cache directories are left untouched and can be removed manually when no longer needed.

Git fetches use `--depth=1 --filter=blob:none`, with no working-tree checkout or full-history download. The UI and helper run on Linux.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile backend/main.py
# Requires Quickshell, uses isolated settings and an offscreen window:
python3 tests/test_runtime.py
python3 tests/test_picker_runtime.py
python3 tests/test_upload_runtime.py
```

`Service.qml` shares state across bar instances, `BarWidget.qml` provides the panel, and `BackendChannel.qml` sends JSON to the Python helper. The helper uses `gh api` to read repository metadata, Git to create and push commits, `gh auth git-credential` to authenticate Git requests, and GTK for pickers. Backup Git commands use isolated configuration and bypass hooks, content filters, and signing; your global Git settings are unchanged. Automated tests exercise real pushes to temporary local Git repositories and mock GitHub metadata; desktop loading and picker behavior require an Omarchy session.

For local development, symlink the checkout to `~/.config/omarchy/plugins/chyld.easy-backup`, restart the shell to discover it, then run:

```sh
omarchy bar put chyld.easy-backup --after chyld.pindeck
omarchy restart shell
```

## License

MIT · Chyld Medford. The helper channel is adapted from [PinDeck](https://github.com/chyld/omarchy-pindeck), also MIT licensed.
