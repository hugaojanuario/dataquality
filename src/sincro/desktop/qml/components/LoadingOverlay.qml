import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
Rectangle {
    property string message: "Preparando demonstração sintética…"
    color: Qt.alpha(Tokens.canvas, Tokens.surfaceOpacity)
    z: 10
    visible: false
    MouseArea { anchors.fill: parent }
    ColumnLayout {
        anchors.centerIn: parent
        spacing: Tokens.lg
        BusyIndicator { running: parent.parent.visible && !appModel.reducedMotion; Layout.alignment: Qt.AlignHCenter; palette.dark: Tokens.accent }
        AppLabel { text: message }
    }
}
