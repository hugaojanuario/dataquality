import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
ColumnLayout {
    id: root
    property string label: ""
    property alias model: combo.model
    property alias currentIndex: combo.currentIndex
    property alias textRole: combo.textRole
    property alias valueRole: combo.valueRole
    property alias currentText: combo.currentText
    property alias currentValue: combo.currentValue
    property var iconSources: []
    signal activated(int index)
    function iconSourceAt(index) {
        return index >= 0 && root.iconSources && index < root.iconSources.length ? root.iconSources[index] : ""
    }
    spacing: Tokens.xs
    implicitWidth: Tokens.sidebarWidth
    AppLabel { text: root.label; visible: text.length > 0; color: Tokens.muted; font.pixelSize: Tokens.caption }
    ComboBox {
        id: combo
        Layout.fillWidth: true
        implicitHeight: Tokens.fieldHeight
        font.family: Tokens.font
        font.pixelSize: Tokens.body
        palette.text: Tokens.text
        palette.buttonText: Tokens.text
        palette.base: Tokens.surface
        palette.highlight: Tokens.accentSoft
        palette.highlightedText: Tokens.text
        Accessible.name: root.label || "Filtro"
        onActivated: root.activated(index)
        leftPadding: Tokens.sm
        rightPadding: Tokens.lg
        delegate: ItemDelegate {
            required property int index
            width: combo.width
            implicitHeight: Tokens.fieldHeight
            text: combo.textAt(index)
            highlighted: combo.highlightedIndex === index
            contentItem: RowLayout {
                spacing: Tokens.sm
                Image {
                    visible: source.toString().length > 0
                    source: root.iconSourceAt(index)
                    sourceSize.width: 64
                    sourceSize.height: 64
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
                AppLabel { text: parent.parent.text; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
            }
            background: Rectangle {
                radius: Tokens.radiusSm
                color: parent.highlighted ? Tokens.accentSoft : parent.hovered ? Tokens.raised : Tokens.solidSurface
            }
        }
        contentItem: RowLayout {
            spacing: Tokens.sm
            Image {
                visible: source.toString().length > 0
                source: root.iconSourceAt(combo.currentIndex)
                sourceSize.width: 64
                sourceSize.height: 64
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
            AppLabel {
                text: combo.displayText
                Layout.fillWidth: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                wrapMode: Text.NoWrap
            }
        }
        background: Rectangle {
            color: combo.down ? Tokens.raised : Tokens.input
            radius: Tokens.radiusSm
            border.color: combo.visualFocus ? Tokens.accent : Tokens.border
            border.width: combo.visualFocus ? 2 : 1
        }
    }
}
