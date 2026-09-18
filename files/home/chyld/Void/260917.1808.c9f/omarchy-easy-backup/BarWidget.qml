import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Ui
import qs.Commons

BarWidget {
    id: root
    moduleName: "chyld.easy-backup"
    readonly property var backend: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property bool uploading: backend ? backend.uploading : false
    property bool opened: false
    property bool advanced: false
    property bool filesView: false
    readonly property bool popoutSwitchClosing: popup.popoutSwitchClosing
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    function open() {
        opened = true;
    }
    function close() {
        opened = false;
        advanced = false;
        filesView = false;
    }
    function toggle() {
        if (opened)
            close();
        else
            open();
    }
    function closeForPopoutSwitch() {
        close();
    }
    function pick(folder) {
        // Hide the panel for the native picker, then return to this view.
        opened = false;
        backend.run("choose", {
            folder: folder
        });
    }
    Connections {
        target: root.backend
        function onLocalOpened() {
            root.close();
        }
        function onPicked() {
            root.open();
        }
    }
    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        hasVisualContent: true
        labelVisible: false
        implicitWidth: vertical ? barSize : Style.space(22) + scaledHorizontalMargin * 2
        implicitHeight: vertical ? Style.space(22) + scaledVerticalPadding * 2 : barSize
        tooltipText: "Easy Backup"
        Text {
            id: backupIcon
            anchors.centerIn: parent
            text: "󰁯"
            RotationAnimator on rotation {
                from: 0
                to: 360
                duration: 1100
                loops: Animation.Infinite
                running: root.uploading
            }
            Connections {
                target: root
                function onUploadingChanged() {
                    if (!root.uploading)
                        backupIcon.rotation = 0;
                }
            }
            font.family: Style.font.family
            font.pixelSize: Style.space(21)
            color: root.opened ? Color.accent : button.foreground
        }
        onPressed: function (mouseButton) {
            if (mouseButton === Qt.LeftButton)
                root.toggle();
        }
    }
    KeyboardPanel {
        id: popup
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: body
        contentWidth: fittedContentWidth(Style.space(440))
        contentHeight: fittedContentHeight(Math.min(Style.space(680), body.implicitHeight))
        padding: Style.space(14)
        Flickable {
            anchors.fill: parent
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Controls.ScrollBar.vertical: Controls.ScrollBar {}
            BackupPanel {
                id: body
                width: parent.width
                service: root.backend
                advanced: root.advanced
                filesView: root.filesView
                onManageFiles: root.filesView = true
                onPick: function (folder) {
                    root.pick(folder);
                }
                onSettings: root.advanced = true
                onBack: {
                    root.advanced = false;
                    root.filesView = false;
                }
                Keys.onEscapePressed: {
                    if (root.advanced || root.filesView) {
                        root.advanced = false;
                        root.filesView = false;
                    } else
                        root.close();
                }
            }
        }
    }
}
