import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons

ColumnLayout {
    id: root
    property var service: null
    property bool advanced: false
    property bool filesView: false
    readonly property bool available: !!service && service.ready && !service.busy
    readonly property var review: service ? service.review : null
    readonly property var config: service ? service.configData : ({
            paths: [],
            repository: ""
        })
    readonly property bool uploading: !!service && service.uploading
    readonly property string repositoryUrl: {
        var name = (root.config.repository || "").trim().replace(/^https:\/\/github\.com\//, "").replace(/^git@github\.com:/, "").replace(/\/+$/, "").replace(/\.git$/, "");
        return /^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(name) && name.split("/")[1] !== "." && name.split("/")[1] !== ".." ? "https://github.com/" + name : "";
    }
    property bool showChanges: false
    signal pick(bool folder)
    signal manageFiles
    signal settings
    signal back
    spacing: Style.space(8)
    focus: true
    onReviewChanged: showChanges = false

    component Label: Text {
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        textFormat: Text.PlainText
    }
    component Caption: Label {
        color: Qt.alpha(Color.popups.text, 0.58)
        font.pixelSize: Style.space(10)
        font.letterSpacing: Style.space(1.2)
        font.weight: Font.DemiBold
    }
    component Card: Rectangle {
        default property alias contents: inner.data
        color: Qt.alpha(Color.popups.text, 0.025)
        border.color: Qt.alpha(Color.popups.text, 0.09)
        radius: Math.max(Style.cornerRadius, Style.space(10))
        implicitHeight: inner.implicitHeight + Style.space(18)
        Layout.fillWidth: true
        ColumnLayout {
            id: inner
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                margins: Style.space(9)
            }
            spacing: Style.space(8)
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(12)
        Rectangle {
            Layout.preferredWidth: Style.space(30)
            Layout.preferredHeight: width
            radius: Style.space(8)
            color: Qt.alpha(Color.accent, 0.12)
            Label {
                anchors.centerIn: parent
                text: root.advanced ? "⚙" : root.filesView ? "↳" : "󰁯"
                font.pixelSize: Style.space(20)
                color: Color.accent
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: Math.max(0, root.width - Style.space(106))
            spacing: Style.space(3)
            Label {
                text: root.advanced ? "Advanced settings" : root.filesView ? "Files & folders" : "Easy Backup"
                font.pixelSize: Style.space(18)
                font.weight: Font.DemiBold
            }
            Label {
                visible: root.advanced || root.filesView
                text: root.advanced ? "Fine-tune what gets backed up." : root.filesView ? "Choose what belongs in your backup." : "Your files. Your GitHub."
                color: Qt.alpha(Color.popups.text, 0.58)
                font.pixelSize: Style.space(11)
            }
        }
        BackupButton {
            visible: !root.advanced && !root.filesView
            text: "⚙"
            quiet: true
            compact: true
            enabled: root.available
            Accessible.name: "Advanced settings"
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Advanced settings"
            onClicked: root.settings()
        }
    }
    SelectedPaths {
        visible: root.filesView
        Layout.fillWidth: true
        service: root.service
        onPick: function (folder) {
            root.pick(folder);
        }
        onBack: root.back()
    }
    AdvancedSettings {
        visible: root.advanced
        Layout.fillWidth: true
        service: root.service
        onBack: root.back()
    }
    ColumnLayout {
        visible: !root.advanced && !root.filesView
        Layout.fillWidth: true
        spacing: Style.space(8)
        Card {
            RowLayout {
                Layout.fillWidth: true
                Caption {
                    text: "DESTINATION"
                    Layout.fillWidth: true
                }
                Label {
                    visible: !!root.review
                    text: root.review ? (root.review.private ? "Private" : "Public") + " · " + root.review.branch : ""
                    font.pixelSize: Style.space(10)
                    color: Color.accent
                }
                BackupButton {
                    text: root.service && root.service.busy && root.service.operation === "verify" ? "Verifying…" : root.service && root.service.repositoryVerified ? "Verified ✓" : "Verify"
                    compact: true
                    enabled: root.available && root.config.repository.trim() !== ""
                    onClicked: root.service.run("verify")
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: "Check repository access on GitHub"
                }
                BackupButton {
                    text: "GitHub ↗"
                    quiet: true
                    compact: true
                    enabled: root.repositoryUrl !== ""
                    Accessible.name: "Open backup repository on GitHub"
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: "Open repository on GitHub"
                    onClicked: {
                        if (!Qt.openUrlExternally(root.repositoryUrl) && root.service)
                            root.service.error = "Could not open the repository in your default browser.";
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Style.space(8)
                Label {
                    text: ""
                    font.pixelSize: Style.space(20)
                    color: Qt.alpha(Color.popups.text, 0.75)
                }
                Controls.TextField {
                    id: repo
                    Layout.fillWidth: true
                    enabled: root.available
                    text: root.config.repository || ""
                    placeholderText: "https://github.com/you/backups"
                    color: Color.popups.text
                    placeholderTextColor: Qt.alpha(Color.popups.text, 0.4)
                    selectionColor: Color.accent
                    selectedTextColor: Color.background
                    font.family: Style.font.family
                    font.pixelSize: Style.space(12)
                    padding: Style.space(7)
                    background: Rectangle {
                        color: repo.activeFocus ? Qt.alpha(Color.accent, 0.05) : "transparent"
                        radius: Style.space(5)
                        border.color: repo.activeFocus ? Color.accent : "transparent"
                    }
                    onTextEdited: root.service.edit("repository", text)
                    onAccepted: if (root.available)
                        root.service.run("verify")
                }
            }
        }
        Card {
            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: "Files & folders"
                    font.weight: Font.DemiBold
                }
                Label {
                    text: root.config.paths.length + " selected"
                    color: Qt.alpha(Color.popups.text, 0.58)
                    font.pixelSize: Style.space(11)
                }
                BackupButton {
                    text: "Manage  →"
                    compact: true
                    enabled: root.available
                    onClicked: root.manageFiles()
                }
            }
        }
        Card {
            visible: !!root.review
            Caption {
                text: "READY TO BACK UP"
            }
            RowLayout {
                Layout.fillWidth: true
                Repeater {
                    model: root.review ? [
                        {
                            count: root.review.changes.added.length,
                            label: "added"
                        },
                        {
                            count: root.review.changes.modified.length,
                            label: "changed"
                        },
                        {
                            count: root.review.changes.removed.length,
                            label: "removed"
                        }
                    ] : []
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: (root.width - Style.space(56)) / 3
                        spacing: Style.space(3)
                        Label {
                            text: modelData.count
                            font.pixelSize: Style.space(23)
                            font.weight: Font.DemiBold
                            color: modelData.label === "removed" && modelData.count > 0 ? Color.urgent : Color.accent
                        }
                        Label {
                            text: modelData.label
                            font.pixelSize: Style.space(11)
                            color: Qt.alpha(Color.popups.text, 0.6)
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: root.review ? root.review.count + " files · " + (root.review.bytes / 1048576).toFixed(1) + " MiB" : ""
                    font.pixelSize: Style.space(11)
                    color: Qt.alpha(Color.popups.text, 0.6)
                }
                BackupButton {
                    text: root.showChanges ? "Hide details ↑" : "View changes ↓"
                    quiet: true
                    compact: true
                    onClicked: root.showChanges = !root.showChanges
                }
            }
            Controls.ScrollView {
                visible: root.showChanges
                Layout.fillWidth: true
                Layout.preferredHeight: Style.space(140)
                clip: true
                BackupTextArea {
                    readOnly: true
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.WrapAnywhere
                    text: {
                        var r = root.review;
                        if (!r)
                            return "";
                        return r.changes.added.map(function (p) {
                            return "+ " + p;
                        }).concat(r.changes.modified.map(function (p) {
                            return "~ " + p;
                        }), r.changes.removed.map(function (p) {
                            return "− " + p;
                        }), r.skipped.map(function (p) {
                            return "Excluded: " + p;
                        })).join("\n") || "No changes.";
                    }
                }
            }
            Label {
                visible: !!root.review && !root.review.private
                Layout.fillWidth: true
                text: "Public repository · Anyone can view these files."
                color: Color.urgent
                font.pixelSize: Style.space(11)
                wrapMode: Text.WordWrap
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)
            UploadSpinner {
                visible: !!root.service && root.service.busy
                running: visible
            }
            BackupButton {
                Layout.fillWidth: true
                primary: true
                compact: true
                text: root.uploading ? "Uploading to GitHub…" : root.service && root.service.busy && root.service.operation === "stage" ? "Preparing snapshot…" : root.review ? "↑  Back up now" : "Review backup  →"
                enabled: root.available && root.service.repositoryVerified && root.config.paths.length > 0
                onClicked: root.review ? root.service.run("upload", {
                    token: root.review.token
                }) : root.service.run("stage")
            }
        }
    }
    Label {
        Layout.fillWidth: true
        text: root.service ? root.service.error || root.service.message : "Loading…"
        visible: text !== ""
        wrapMode: Text.WrapAnywhere
        color: root.service && root.service.error ? Color.urgent : Color.accent
        font.pixelSize: Style.space(11)
    }
    ColumnLayout {
        visible: !root.advanced && !root.filesView
        Layout.fillWidth: true
        spacing: Style.space(8)
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Qt.alpha(Color.popups.text, 0.09)
        }
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: root.config.lastBackup ? "Last backup · " + Qt.formatDateTime(new Date(root.config.lastBackup), "MMM d, h:mm AP") : "Your first backup starts here."
                color: Qt.alpha(Color.popups.text, 0.5)
                font.pixelSize: Style.space(10)
            }
            BackupButton {
                readonly property var commit: root.config.lastCommit || null
                visible: !!commit && !!commit.sha
                quiet: true
                compact: true
                text: commit ? commit.sha.slice(0, 8) + " ↗" : ""
                onClicked: Qt.openUrlExternally("https://github.com/" + commit.repository + "/commit/" + commit.sha)
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: commit ? commit.repository + "\n" + commit.sha : ""
                Accessible.name: "View backup commit on GitHub"
            }
        }
    }
}
