import QtQuick
import QtQuick.Layouts
import ".."
GlassPanel {
    id: root
    property string title: "Nenhum resultado ainda"
    property string description: "Configure as conexões para iniciar sua auditoria."
    property string iconName: "discover"
    implicitHeight: Tokens.xxl * 4
    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width - Tokens.xxl * 2
        spacing: Tokens.md
        AppIcon { name: root.iconName; Layout.alignment: Qt.AlignHCenter; color: Tokens.accent }
        AppLabel { text: root.title; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold; Layout.alignment: Qt.AlignHCenter }
        AppLabel { text: root.description; color: Tokens.muted; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
    }
}
