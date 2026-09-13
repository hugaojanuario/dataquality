import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
GlassPanel {
    id: root
    property string status: appModel.state.status
    property real progress: appModel.state.progress
    implicitHeight: body.implicitHeight + Tokens.lg * 2
    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: Tokens.lg
        spacing: Tokens.sm
        RowLayout {
            AppLabel { text: root.status; Layout.fillWidth: true }
            SecondaryButton { text: "Cancelar"; visible: appModel.state.busy; onClicked: appModel.cancel() }
        }
        ProgressBar {
            id: bar
            Layout.fillWidth: true
            value: root.progress < 0 ? 0 : root.progress
            indeterminate: root.progress < 0 && appModel.state.busy
            implicitHeight: Tokens.xs
            background: Rectangle { color: Tokens.raised; radius: Tokens.xxs }
            contentItem: Item {
                clip: true
                Rectangle {
                    width: bar.indeterminate ? parent.width * 0.25 : parent.width * bar.visualPosition
                    height: parent.height; radius: Tokens.xxs; color: Tokens.accent
                    SequentialAnimation on x {
                        running: bar.indeterminate && !appModel.reducedMotion
                        loops: Animation.Infinite
                        NumberAnimation { from: 0; to: bar.width * 0.75; duration: Tokens.normal * 5; easing.type: Tokens.easing }
                        NumberAnimation { to: 0; duration: 0 }
                    }
                }
            }
        }
        AppLabel { text: "Cancelamento cooperativo. Conexão e metadados podem aguardar o timeout do driver."; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
    }
}
