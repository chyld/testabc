import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.Button {
    id: control
    property bool primary: false
    property bool quiet: false
    property bool compact: false
    padding: Style.space(compact ? 7 : 11)
    horizontalPadding: Style.space(compact ? 10 : 15)
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    font.weight: primary ? Font.DemiBold : Font.Medium
    opacity: enabled ? 1 : 0.4
    hoverEnabled: true
    contentItem: Text {
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: control.primary ? Color.background : control.quiet ? Qt.alpha(Color.popups.text, 0.75) : Color.popups.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        color: control.primary ? (control.down ? Qt.darker(Color.accent, 1.15) : control.hovered ? Qt.lighter(Color.accent, 1.08) : Color.accent) : Qt.alpha(Color.popups.text, control.down ? 0.12 : control.hovered ? 0.08 : control.quiet ? 0 : 0.04)
        border.width: control.activeFocus ? 2 : control.quiet || control.primary ? 0 : 1
        border.color: control.activeFocus ? Color.accent : Qt.alpha(Color.popups.text, 0.12)
        radius: Math.max(Style.cornerRadius, Style.space(7))
        Behavior on color {
            ColorAnimation {
                duration: 120
            }
        }
    }
}
