import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
ItemDelegate {
    id: root
    property string iconName: "overview"
    property bool selected: false
    property bool collapsed: false
    implicitHeight: Tokens.xxl
    hoverEnabled: true
    Accessible.name: text
    ToolTip.visible: collapsed && hovered
    ToolTip.text: text
    contentItem: RowLayout {
        spacing: Tokens.sm
        AppIcon { name: root.iconName; color: root.selected ? Tokens.navigationText : Tokens.navigationMuted }
        AppLabel { text: root.text; visible: !root.collapsed; Layout.fillWidth: true; color: root.selected ? Tokens.navigationText : Tokens.navigationMuted; font.weight: root.selected ? Font.DemiBold : Font.Normal }
    }
    background: Rectangle {
        radius: Tokens.radiusSm
        color: root.down || root.selected ? Tokens.navigationSelected : root.hovered ? Tokens.navigationHover : Tokens.transparent
        border.color: root.visualFocus ? Tokens.accent : Tokens.transparent
        Behavior on color { ColorAnimation { duration: Tokens.fast } }
    }
}
