import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Configurações"; subtitle: ""; Layout.fillWidth: true }
    GlassPanel {
        Layout.fillWidth: true; implicitHeight: appearance.implicitHeight + Tokens.lg * 2
        ColumnLayout {
            id: appearance; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
            AppLabel { text: "Aparência"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
            RowLayout {
                SecondaryButton { text: appModel.dark ? "Escuro · ativo" : "Escuro"; onClicked: appModel.setDark(true) }
                SecondaryButton { text: !appModel.dark ? "Claro · ativo" : "Claro"; onClicked: appModel.setDark(false) }
                CheckBox { text: "Reduzir animações"; checked: appModel.reducedMotion; onClicked: appModel.setReducedMotion(checked); palette.windowText: Tokens.text }
            }
            AppLabel { text: ""; color: Tokens.muted; Layout.fillWidth: true }
        }
    }
    GlassPanel {
        Layout.fillWidth: true; implicitHeight: project.implicitHeight + Tokens.lg * 2
        ColumnLayout {
            id: project; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
            AppLabel { text: "Projeto de auditoria"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
            RowLayout {
                AppTextField { Layout.fillWidth: true; label: "Nome do projeto"; text: appModel.state.projectName; enabled: !appModel.state.busy; onEdited: value => appModel.configure("name", value) }
                SecondaryButton { text: "Abrir / criar projeto"; enabled: !appModel.state.demo && !appModel.state.busy; Layout.alignment: Qt.AlignBottom; onClicked: directoryPicker.open() }
            }
            AppTextField { Layout.fillWidth: true; label: "Descrição"; text: appModel.state.description; enabled: !appModel.state.busy; onEdited: value => appModel.configure("description", value) }
            AppLabel { text: appModel.state.directory; color: Tokens.muted; Layout.fillWidth: true }
            AppLabel { visible: appModel.state.recentProjects.length > 0; text: "Projetos recentes"; font.weight: Font.DemiBold }
            Flow {
                Layout.fillWidth: true; spacing: Tokens.sm
                Repeater {
                    model: appModel.state.recentProjects
                    SecondaryButton {
                        required property var modelData
                        text: modelData.name + (modelData.current ? " · aberto" : "")
                        enabled: !modelData.current && !appModel.state.busy
                        onClicked: appModel.openRecentProject(modelData.path)
                    }
                }
            }
            AppTextField { Layout.fillWidth: true; label: "Variável da chave HMAC"; text: appModel.state.keyEnv; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => appModel.configure("keyEnv", value) }
            AppLabel { text: "Use a mesma chave nas capturas. Mínimo: 32 bytes."; color: Tokens.muted; Layout.fillWidth: true }
            CheckBox { text: "Incluir schemas de sistema"; checked: appModel.state.includeSystem; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: appModel.configure("system", checked.toString()); palette.windowText: Tokens.text }
        }
    }
    FolderDialog { id: directoryPicker; title: "Selecionar diretório do projeto"; onAccepted: appModel.chooseDirectory(selectedFolder.toString()) }
}
