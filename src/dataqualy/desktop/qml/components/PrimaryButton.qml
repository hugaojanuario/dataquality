import QtQuick
import QtQuick.Controls
import ".."
Button {
    id: control
    implicitHeight: Tokens.fieldHeight
    implicitWidth: Math.max(Tokens.xxl * 2, contentItem.implicitWidth + Tokens.xl)
    leftPadding: Tokens.md
    rightPadding: Tokens.md
    hoverEnabled: true
    opacity: enabled ? 1 : Tokens.disabledOpacity
    font.family: Tokens.font
    font.pixelSize: Tokens.body
    font.weight: Font.DemiBold
    Accessible.name: text
    contentItem: Text {
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: Tokens.accentText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Tokens.fieldHeight / 2
        color: control.down ? Qt.darker(Tokens.accentFill, 1.15) : control.hovered ? Qt.lighter(Tokens.accentFill, 1.09) : Tokens.accentFill
        border.width: control.visualFocus ? 2 : 0
        border.color: Tokens.text
        Behavior on color { ColorAnimation { duration: Tokens.fast } }
    }
}
