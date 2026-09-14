import QtQuick
import QtQuick.Layouts
import ".."
Rectangle {
    id: root
    property string text: "Pendente"
    property string tone: "pending"
    implicitWidth: badgeLabel.implicitWidth + Tokens.lg
    implicitHeight: Tokens.lg + Tokens.xxs
    radius: Tokens.radiusSm
    color: Qt.alpha(Tokens.semantic(tone), 0.10)
    border.color: Qt.alpha(Tokens.semantic(tone), 0.22)
    AppLabel {
        id: badgeLabel
        anchors.centerIn: parent
        text: root.text
        font.pixelSize: Tokens.caption
        font.weight: Font.Medium
        color: Tokens.semantic(root.tone)
        wrapMode: Text.NoWrap
    }
}
