import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons

ColumnLayout {
    id: root
    required property var service
    readonly property bool available: !!service && service.ready && !service.busy
    readonly property var config: service ? service.configData : ({
            paths: []
        })
    signal pick(bool folder)
    signal back
    spacing: Style.space(14)
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
        implicitHeight: inner.implicitHeight + Style.space(28)
        Layout.fillWidth: true
        ColumnLayout {
            id: inner
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                margins: Style.space(14)
            }
            spacing: Style.space(10)
        }
    }

    BackupButton {
        text: "← Back to backup"
        quiet: true
        compact: true
        onClicked: root.back()
    }
    RowLayout {
        Layout.fillWidth: true
        Label {
            text: "Files & folders"
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }
        Caption {
            text: root.config.paths.length + " SELECTED"
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(3)
        Repeater {
            model: root.config.paths
            Rectangle {
                id: fileRow
                required property string modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: Style.space(58)
                radius: Style.space(8)
                color: rowHover.hovered ? Qt.alpha(Color.popups.text, 0.045) : "transparent"
                HoverHandler {
                    id: rowHover
                }
                Controls.ToolTip.visible: rowHover.hovered
                Controls.ToolTip.delay: 600
                Controls.ToolTip.text: modelData
                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: Style.space(10)
                        rightMargin: Style.space(4)
                    }
                    spacing: Style.space(11)
                    Label {
                        text: "↳"
                        color: Color.accent
                        font.pixelSize: Style.space(22)
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(4)
                        Label {
                            Layout.fillWidth: true
                            text: fileRow.modelData.split("/").filter(function (p) {
                                return p.length > 0;
                            }).pop() || "/"
                            elide: Text.ElideMiddle
                            font.weight: Font.Medium
                        }
                        Label {
                            Layout.fillWidth: true
                            text: fileRow.modelData.substring(0, fileRow.modelData.lastIndexOf("/")) || "/"
                            elide: Text.ElideMiddle
                            color: Qt.alpha(Color.popups.text, 0.5)
                            font.pixelSize: Style.space(10)
                        }
                    }
                    BackupButton {
                        text: "×"
                        compact: true
                        quiet: true
                        enabled: root.available
                        Accessible.name: "Remove " + fileRow.modelData
                        onClicked: root.service.removePath(fileRow.index)
                    }
                }
            }
        }
        Card {
            visible: root.config.paths.length === 0
            Label {
                text: "Start with the files that matter."
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
            }
            Label {
                text: "Add files or entire folders from your computer."
                color: Qt.alpha(Color.popups.text, 0.5)
                font.pixelSize: Style.space(11)
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
    RowLayout {
        spacing: Style.space(8)
        BackupButton {
            text: "+  Add files"
            compact: true
            enabled: root.available
            onClicked: root.pick(false)
        }
        BackupButton {
            text: "+  Add folders"
            compact: true
            enabled: root.available
            onClicked: root.pick(true)
        }
        Item {
            Layout.fillWidth: true
        }
    }
}
