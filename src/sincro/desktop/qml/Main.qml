import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "."
import "components"
AppWindow {
    id: window
    objectName: "sincroWindow"
    property bool allowClose: false
    property bool detailsOpen: false
    onClosing: event => { if (!allowClose && appModel.state.busy) { event.accepted = false; closeDialog.open() } }
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Sidebar { id: sidebar; Layout.fillHeight: true; Layout.preferredWidth: implicitWidth }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Tokens.headerHeight
                color: Tokens.transparent

                RowLayout {
                    id: headerRow
                    anchors.fill: parent
                    anchors.margins: Tokens.lg
                    spacing: Tokens.sm
                    AbstractButton {
                        id: projectSwitcher
                        objectName: "projectSwitcher"
                        Layout.fillWidth: true
                        Layout.maximumWidth: 460
                        implicitHeight: 36
                        leftPadding: Tokens.sm
                        rightPadding: Tokens.sm
                        hoverEnabled: true
                        enabled: !appModel.state.demo && !appModel.state.busy
                        Accessible.name: "Trocar projeto atual"
                        onClicked: projectMenu.open()
                        contentItem: RowLayout {
                            spacing: Tokens.xs
                            AppLabel { text: "Projeto  /"; color: Tokens.muted; font.pixelSize: Tokens.caption }
                            AppLabel { text: appModel.state.projectName; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            AppLabel { text: "⌄"; color: Tokens.muted; font.pixelSize: Tokens.subtitle }
                        }
                        background: Rectangle {
                            radius: Tokens.radiusSm
                            color: projectSwitcher.down ? Tokens.accentSoft : projectSwitcher.hovered ? Tokens.surface : Tokens.transparent
                            border.color: projectSwitcher.visualFocus ? Tokens.accent : Tokens.transparent
                            border.width: projectSwitcher.visualFocus ? 2 : 1
                            Behavior on color { ColorAnimation { duration: Tokens.fast } }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    StatusBadge { text: appModel.state.busy ? "Em execução" : appModel.state.error ? "Erro na operação" : appModel.state.hasResult ? appModel.state.resultLabel : "Pronto"; tone: appModel.state.busy ? "running" : appModel.state.error ? "error" : appModel.state.resultStatus }
                    IconButton { text: "Alternar tema"; iconName: "settings"; onClicked: appModel.setDark(!appModel.dark) }
                    IconButton { text: "Detalhes da operação"; iconName: "info"; onClicked: window.detailsOpen = !window.detailsOpen }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Tokens.lg
                Layout.margins: Tokens.lg
                Loader {
                    id: pageLoader
                    objectName: "pageLoader"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: ["pages/Overview.qml", "pages/ConnectionsPage.qml", "pages/Discovery.qml", "pages/Mapping.qml", "pages/Validation.qml", "pages/History.qml", "pages/Settings.qml", "pages/Results.qml"][appModel.state.page]
                    onLoaded: item.forceActiveFocus()
                }
                GlassPanel {
                    visible: window.detailsOpen && window.width >= 1400
                    Layout.preferredWidth: 280
                    Layout.fillHeight: true
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
                        AppLabel { text: "Contexto e evidências"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
                        ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth; AppLabel { width: parent.width; text: appModel.state.details || "Selecione um resultado para ver os detalhes."; color: Tokens.muted } }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: Tokens.xl; color: Tokens.transparent
                AppLabel { anchors.fill: parent; anchors.leftMargin: Tokens.lg; anchors.rightMargin: Tokens.lg; verticalAlignment: Text.AlignVCenter; text: appModel.state.demo ? "Demo · dados sintéticos" : appModel.state.status; color: Tokens.muted; font.pixelSize: Tokens.caption; elide: Text.ElideRight; wrapMode: Text.NoWrap }
            }
        }
    }
    Popup {
        id: projectMenu
        objectName: "projectMenu"
        parent: Overlay.overlay
        x: sidebar.width + Tokens.lg
        y: Tokens.headerHeight - Tokens.xs
        width: 340
        padding: Tokens.md
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: GlassPanel { solid: true }
        contentItem: ColumnLayout {
            spacing: Tokens.xs
            AppLabel { text: "Trocar projeto"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold; Layout.bottomMargin: Tokens.xs }
            Repeater {
                model: appModel.state.recentProjects
                ItemDelegate {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: Tokens.fieldHeight
                    enabled: !modelData.current && !appModel.state.busy
                    onClicked: { appModel.openRecentProject(modelData.path); projectMenu.close() }
                    contentItem: RowLayout {
                        AppLabel { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideMiddle; wrapMode: Text.NoWrap }
                        AppLabel { visible: modelData.current; text: "Atual"; color: Tokens.accent; font.pixelSize: Tokens.caption }
                    }
                    background: Rectangle {
                        radius: Tokens.radiusSm
                        color: parent.down ? Tokens.accentSoft : parent.hovered ? Tokens.raised : Tokens.transparent
                    }
                }
            }
            SecondaryButton {
                Layout.fillWidth: true
                text: "Abrir ou criar outro projeto…"
                enabled: !appModel.state.busy
                onClicked: { projectMenu.close(); projectPicker.open() }
            }
        }
    }
    FolderDialog {
        id: projectPicker
        title: "Selecionar diretório do projeto"
        onAccepted: appModel.chooseDirectory(selectedFolder.toString())
    }
    Drawer {
        id: detailsDrawer
        objectName: "detailsDrawer"
        edge: Qt.RightEdge
        width: Math.min(420, window.width - Tokens.xxl)
        height: window.height
        visible: window.detailsOpen && window.width < 1400
        onClosed: window.detailsOpen = false
        background: GlassPanel { solid: true }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.lg
            RowLayout { AppLabel { text: "Contexto e evidências"; font.pixelSize: Tokens.subtitle; Layout.fillWidth: true } IconButton { text: "Fechar detalhes"; iconName: "close"; onClicked: window.detailsOpen = false } }
            ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth; AppLabel { width: parent.width; text: appModel.state.details || "Selecione um resultado para ver os detalhes."; color: Tokens.muted } }
        }
    }
    Toast { id: toast; parent: Overlay.overlay; x: (parent.width - width) / 2; y: parent.height - height - Tokens.xl }
    ConfirmDialog { id: closeDialog; parent: Overlay.overlay; title: "Cancelar e fechar?"; message: "Aguarde a liberação dos recursos. O driver pode precisar atingir o timeout antes de encerrar."; acceptText: "Cancelar e fechar"; onAccepted: { if (appModel.requestClose()) { window.allowClose = true; window.close() } } }
    LoadingOverlay { anchors.fill: parent; visible: appModel.state.demo && appModel.state.busy && appModel.state.discovered === 0 }
    Connections {
        target: appModel
        function onToast(message, tone) { toast.message = message; toast.tone = tone; toast.open() }
        function onReadyToClose() { window.allowClose = true; window.close() }
        function onDetailsRequested() { window.detailsOpen = true }
    }
    Shortcut { sequence: "Ctrl+1"; onActivated: appModel.navigate(0) }
    Shortcut { sequence: "Ctrl+2"; onActivated: appModel.navigate(1) }
    Shortcut { sequence: "Ctrl+3"; onActivated: appModel.navigate(2) }
    Shortcut { sequence: "Ctrl+4"; onActivated: appModel.navigate(3) }
    Shortcut { sequence: "Ctrl+5"; onActivated: appModel.navigate(4) }
    Shortcut { sequence: "Ctrl+6"; onActivated: appModel.navigate(5) }
    Shortcut { sequence: "Ctrl+7"; onActivated: appModel.navigate(6) }
}
