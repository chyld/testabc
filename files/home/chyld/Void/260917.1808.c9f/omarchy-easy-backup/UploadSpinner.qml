import QtQuick
import qs.Commons

Item {
    id: root
    property bool running: false
    implicitWidth: Style.space(24)
    implicitHeight: implicitWidth
    Item {
        anchors.fill: parent
        Repeater {
            model: 8
            Item {
                required property int index
                width: root.width
                height: root.height
                rotation: index * 45
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Style.space(1)
                    width: Style.space(4)
                    height: width
                    radius: width / 2
                    color: Color.accent
                    opacity: (index + 1) / 8
                }
            }
        }
        RotationAnimator on rotation {
            running: root.running
            from: 0
            to: 360
            duration: 900
            loops: Animation.Infinite
        }
    }
}
