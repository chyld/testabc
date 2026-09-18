import QtQuick
import Quickshell

Item {
    id: root
    property var shell: null
    property var manifest: null
    property var configData: ({
            version: 1,
            repository: "",
            paths: [],
            excludes: [],
            lastBackup: ""
        })
    property var review: null
    property bool ready: false
    property string message: ""
    property string error: ""
    onErrorChanged: {
        if (!error)
            return;
        var labels = {
            load: "Could not load settings",
            save: "Could not save settings",
            verify: "Repository verification failed",
            choose: "Could not select files",
            stage: "Could not prepare backup",
            upload: "Backup failed",
            "open-local": "Could not open local backup"
        };
        var body = error.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        Quickshell.execDetached(["notify-send", "--app-name=Easy Backup", "--urgency=critical", "--icon=dialog-error", "--", "Easy Backup — " + (labels[operation] || "Error"), body]);
    }
    property string operation: ""
    property int sequence: 0
    readonly property bool busy: channel.busy
    readonly property bool uploading: busy && operation === "upload"
    readonly property bool repositoryVerified: !!configData.repository && configData.verifiedRepository === configData.repository
    signal localOpened
    signal picked

    function run(op, fields) {
        if (busy)
            return;
        error = "";
        message = "";
        operation = op;
        if (op === "verify") {
            configData = Object.assign({}, configData, {
                verifiedRepository: ""
            });
            review = null;
        }
        if (op === "stage")
            review = null;
        if (!channel.start(Object.assign({
            id: ++sequence,
            op: op,
            data: configData
        }, fields || {})))
            error = "Could not start the operation. The request may be too large.";
    }
    function edit(field, value) {
        if (busy || !ready)
            return;
        var next = Object.assign({}, configData);
        next[field] = value;
        if (field === "repository" && configData[field] !== value) {
            next.lastBackup = "";
            next.lastCommit = null;
            next.verifiedRepository = "";
            message = "";
            error = "";
        }
        configData = next;
        review = null;
    }
    function removePath(index) {
        var paths = configData.paths.slice();
        paths.splice(index, 1);
        edit("paths", paths);
        run("save");
    }
    Component.onCompleted: run("load")
    BackendChannel {
        id: channel
        onCompleted: function (response) {
            if (!response.ok) {
                root.error = response.error;
                if (root.operation === "choose")
                    root.picked();
                return;
            }
            var result = response.result;
            if (root.operation === "open-local")
                root.localOpened();
            if (result.data) {
                root.configData = result.data;
                root.ready = true;
            }
            if (root.operation === "save")
                root.message = "Settings saved.";
            if (root.operation === "verify")
                root.message = result.message;
            if (root.operation === "stage")
                root.review = result;
            if (root.operation === "upload") {
                root.message = result.message;
                root.review = null;
            }
            if (root.operation === "choose") {
                var paths = root.configData.paths.slice();
                result.paths.forEach(function (path) {
                    if (paths.indexOf(path) < 0)
                        paths.push(path);
                });
                root.edit("paths", paths);
                root.picked();
                Qt.callLater(function () {
                    root.run("save");
                });
            }
        }
    }
}
