import QtQuick
import QtQuick.Controls
import ".."
SecondaryButton {
    id: root
    property string iconName: "menu"
    implicitWidth: Tokens.fieldHeight
    leftPadding: Tokens.xs
    rightPadding: Tokens.xs
    topPadding: Tokens.xs
    bottomPadding: Tokens.xs
    contentItem: AppIcon { name: root.iconName; color: Tokens.text }
    ToolTip.visible: hovered
    ToolTip.text: text
    ToolTip.delay: 500
}
