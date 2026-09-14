import QtQuick
import ".."
Rectangle {
    id: panel
    property bool solid: false
    color: solid ? Tokens.solidSurface : Tokens.surface
    radius: Tokens.radiusLg
    border.color: Tokens.glassBorder
    border.width: 1
    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.topMargin: Tokens.shadowOffset
        anchors.bottomMargin: -Tokens.shadowOffset
        radius: panel.radius
        color: Tokens.shadow
    }
}
