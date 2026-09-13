import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
GlassPanel {
    id: root
    property var rows: []
    property var columns: []
    property bool selectable: false
    signal rowClicked(var row)
    signal selectionChanged(var row, bool selected)
    implicitHeight: Math.min(Tokens.xxl * 8, Tokens.rowHeight * (rows.length + 1))
    clip: true
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Tokens.fieldHeight
            color: Tokens.raised
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Tokens.md
                anchors.rightMargin: Tokens.md
                spacing: Tokens.sm
                Item { visible: root.selectable; Layout.preferredWidth: Tokens.xl }
                Repeater {
                    model: root.columns
                    AppLabel {
                        required property var modelData
                        text: modelData.title
                        Layout.fillWidth: true
                        Layout.preferredWidth: modelData.width || 100
                        font.pixelSize: Tokens.caption
                        font.weight: Font.Medium
                        color: Tokens.muted
                        elide: Text.ElideRight
                        wrapMode: Text.NoWrap
                    }
                }
            }
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.rows
            onModelChanged: forceLayout()
            Component.onCompleted: forceLayout()
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { }
            delegate: ItemDelegate {
                id: delegateRoot
                required property var modelData
                width: list.width
                height: Tokens.rowHeight
                padding: 0
                leftPadding: Tokens.md
                rightPadding: Tokens.md
                Accessible.name: Object.values(modelData).join(" ")
                onClicked: root.rowClicked(modelData)
                background: Rectangle {
                    color: delegateRoot.down ? Tokens.accentSoft : delegateRoot.hovered ? Tokens.raised : Tokens.transparent
                    border.color: delegateRoot.visualFocus ? Tokens.accent : Tokens.transparent
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Tokens.border; opacity: 0.5 }
                }
                contentItem: RowLayout {
                    spacing: Tokens.sm
                    anchors.leftMargin: Tokens.md
                    anchors.rightMargin: Tokens.md
                    CheckBox {
                        visible: root.selectable
                        Layout.preferredWidth: Tokens.xl
                        enabled: delegateRoot.modelData.side === "source"
                        checked: delegateRoot.modelData.selected || false
                        Accessible.name: "Selecionar " + (delegateRoot.modelData.name || "tabela")
                        onClicked: root.selectionChanged(delegateRoot.modelData, checked)
                    }
                    Repeater {
                        model: root.columns
                        Item {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: modelData.width || 100
                            Layout.fillHeight: true
                            AppLabel {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: String(delegateRoot.modelData[parent.modelData.key] ?? "")
                                color: parent.modelData.key === "status" ? Tokens.semantic(delegateRoot.modelData.tone || "pending") : Tokens.text
                                elide: Text.ElideRight
                                wrapMode: Text.NoWrap
                                font.pixelSize: Tokens.body
                            }
                        }
                    }
                }
            }
        }
    }
}
