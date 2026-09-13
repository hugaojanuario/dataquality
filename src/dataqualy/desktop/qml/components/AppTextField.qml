import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
ColumnLayout {
    id: root
    property string label: ""
    property alias text: field.text
    property alias placeholderText: field.placeholderText
    property alias readOnly: field.readOnly
    property alias echoMode: field.echoMode
    property alias inputMethodHints: field.inputMethodHints
    signal edited(string value)
    spacing: Tokens.xs
    implicitWidth: Tokens.sidebarWidth
    AppLabel {
        text: root.label
        visible: text.length > 0
        font.pixelSize: Tokens.caption
        color: Tokens.muted
        MouseArea { anchors.fill: parent; onClicked: field.forceActiveFocus() }
    }
    TextField {
        id: field
        objectName: "input-" + root.label
        Layout.fillWidth: true
        implicitHeight: Tokens.fieldHeight
        font.family: Tokens.font
        font.pixelSize: Tokens.body
        color: Tokens.text
        placeholderTextColor: Tokens.muted
        selectionColor: Tokens.accentSoft
        selectedTextColor: Tokens.text
        leftPadding: Tokens.sm
        rightPadding: Tokens.sm
        selectByMouse: true
        Accessible.name: root.label || placeholderText
        onTextEdited: root.edited(text)
        background: Rectangle {
            radius: Tokens.radiusSm
            color: field.enabled ? Tokens.input : Tokens.surface
            border.color: field.activeFocus ? Tokens.accent : field.hovered ? Tokens.muted : Tokens.border
            border.width: field.activeFocus ? 2 : 1
        }
    }
}
