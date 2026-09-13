import QtQuick
import QtQuick.Controls
import ".."
PrimaryButton {
    id: control
    contentItem: Text {
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: Tokens.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Tokens.fieldHeight / 2
        color: control.down ? Tokens.accentSoft : control.hovered ? Tokens.raised : Tokens.surface
        border.color: control.visualFocus ? Tokens.accent : Tokens.border
        border.width: control.visualFocus ? 2 : 1
        Behavior on color { ColorAnimation { duration: Tokens.fast } }
    }
}
