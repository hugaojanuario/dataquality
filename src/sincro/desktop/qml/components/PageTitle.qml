import QtQuick
import QtQuick.Layouts
import ".."
ColumnLayout {
    property string title: ""
    property string subtitle: ""
    spacing: Tokens.xs
    AppLabel { text: title; font.pixelSize: Tokens.display; font.weight: Font.DemiBold; Layout.fillWidth: true }
    AppLabel { text: subtitle; visible: subtitle.length > 0; color: Tokens.muted; Layout.fillWidth: true }
}
