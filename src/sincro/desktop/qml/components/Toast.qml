import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
Popup {
    id: root
    property string message: ""
    property string tone: "pending"
    width: Math.min(parent.width - Tokens.xxl, 560)
    height: toastBody.implicitHeight + Tokens.lg
    padding: Tokens.sm
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: Tokens.raised; radius: Tokens.radius; border.color: Tokens.semantic(root.tone) }
    contentItem: RowLayout {
        id: toastBody
        AppLabel { text: root.message; Layout.fillWidth: true; Accessible.role: Accessible.AlertMessage }
        IconButton { text: "Fechar notificação"; iconName: "close"; onClicked: root.close() }
    }
    Timer { id: timer; interval: 6500; onTriggered: root.close() }
    onOpened: timer.restart()
}
