import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.TextArea {
    id: control
    color: Color.popups.text
    selectionColor: Color.accent
    selectedTextColor: Color.background
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    padding: Style.space(12)
    background: Rectangle {
        color: Qt.alpha(Color.popups.text, 0.025)
        border.color: control.activeFocus ? Color.accent : Qt.alpha(Color.popups.text, 0.12)
        radius: Math.max(Style.cornerRadius, Style.space(7))
    }
}
