import QtQuick
import QtQuick.Layouts
import ".."
RowLayout {
    id: root
    property int number: 1
    property string text: ""
    property bool complete: false
    spacing: Tokens.sm
    Rectangle {
        implicitWidth: Tokens.xl
        implicitHeight: Tokens.xl
        radius: Tokens.radius
        color: root.complete ? Tokens.accentSoft : Tokens.raised
        AppLabel { anchors.centerIn: parent; text: root.complete ? "✓" : root.number; color: root.complete ? Tokens.success : Tokens.muted }
    }
    AppLabel { text: root.text; color: root.complete ? Tokens.text : Tokens.muted; Layout.fillWidth: true }
}
