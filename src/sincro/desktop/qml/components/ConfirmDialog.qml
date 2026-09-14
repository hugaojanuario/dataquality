import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
Dialog {
    id: root
    parent: Overlay.overlay
    property string message: ""
    property string acceptText: "Confirmar"
    property bool needsReason: false
    property alias reason: reasonField.text
    modal: true
    implicitWidth: 540
    width: Math.min(parent.width - Tokens.xxl, implicitWidth)
    anchors.centerIn: parent
    padding: Tokens.lg
    background: GlassPanel { solid: true }
    header: AppLabel { text: root.title; font.pixelSize: Tokens.heading; font.weight: Font.DemiBold; padding: Tokens.lg }
    contentItem: ColumnLayout {
        spacing: Tokens.md
        AppLabel { text: root.message; Layout.fillWidth: true }
        AppTextField { id: reasonField; label: "Justificativa obrigatória"; visible: root.needsReason; Layout.fillWidth: true; placeholderText: "Explique a exclusão, sem dados pessoais" }
    }
    footer: RowLayout {
        spacing: Tokens.sm
        Item { Layout.fillWidth: true }
        SecondaryButton { text: "Voltar"; onClicked: root.reject(); Layout.bottomMargin: Tokens.lg }
        PrimaryButton { text: root.acceptText; enabled: !root.needsReason || reasonField.text.trim().length > 0; onClicked: root.accept(); Layout.rightMargin: Tokens.lg; Layout.bottomMargin: Tokens.lg }
    }
    Overlay.modal: Rectangle { color: Qt.alpha(Tokens.canvas, 0.75) }
}
