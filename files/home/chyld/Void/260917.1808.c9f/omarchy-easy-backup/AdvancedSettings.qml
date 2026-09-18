import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import qs.Commons

ColumnLayout {
    id: root
    required property var service
    signal back
    spacing: Style.space(14)

    onVisibleChanged: {
        if (visible && service)
            exclusions.text = service.configData.excludes.join("\n");
    }
    BackupButton {
        text: "← Back to backup"
        quiet: true
        compact: true
        enabled: !root.service || !root.service.busy
        onClicked: root.back()
    }
    Text {
        text: "Excluded files and folders"
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.bold: true
    }
    Text {
        Layout.fillWidth: true
        text: "Enter one name or pattern per line, such as node_modules or *.log. Matches are excluded anywhere in the selected paths."
        color: Qt.alpha(Color.popups.text, 0.72)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    Controls.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(230)
        clip: true
        BackupTextArea {
            id: exclusions
            enabled: root.service && root.service.ready && !root.service.busy
            wrapMode: TextEdit.Wrap
            textFormat: TextEdit.PlainText
        }
    }
    Text {
        Layout.fillWidth: true
        text: "Git metadata (.git) and Easy Backup’s cache are always excluded."
        color: Qt.alpha(Color.popups.text, 0.72)
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    BackupButton {
        text: "Save exclusions"
        primary: true
        Layout.fillWidth: true
        enabled: root.service && root.service.ready && !root.service.busy
        onClicked: {
            var patterns = exclusions.text.split("\n").map(function (s) {
                return s.trim();
            }).filter(function (s) {
                return s.length > 0;
            });
            root.service.edit("excludes", patterns);
            root.service.run("save");
        }
    }
}
