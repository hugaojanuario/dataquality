import QtQuick
import QtQuick.Layouts
import ".."
GlassPanel {
    property string label: ""
    property string value: "—"
    property string note: ""
    property string iconName: "overview"
    property color valueColor: Tokens.text
    implicitHeight: Tokens.xxl * 3
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.md; spacing: Tokens.xs
        RowLayout {
            Rectangle {
                implicitWidth: Tokens.xl; implicitHeight: Tokens.xl; radius: Tokens.radiusSm; color: Tokens.accentSoft
                AppIcon { anchors.centerIn: parent; name: iconName; color: Tokens.accent; width: Tokens.md; height: Tokens.md }
            }
            Item { Layout.fillWidth: true }
            AppLabel { text: label; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
        }
        AppLabel { text: value; color: valueColor; font.pixelSize: Tokens.display; font.weight: Font.DemiBold }
        AppLabel { text: note; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
    }
}
