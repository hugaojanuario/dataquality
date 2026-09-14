import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import ".."
import "../components"
Page {
    id: root
    PageTitle { title: "Conexões"; subtitle: "Origem e destino da migração."; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.lg
        ConnectionCard { Layout.fillWidth: true; Layout.preferredWidth: 1; connection: appModel.sourceConnection; title: "Origem"; side: "source"; onFileRequested: (purpose, side) => root.pick(purpose, side) }
        ConnectionCard { Layout.fillWidth: true; Layout.preferredWidth: 1; connection: appModel.targetConnection; title: "Destino"; side: "target"; onFileRequested: (purpose, side) => root.pick(purpose, side) }
    }
    AppLabel { text: appModel.state.demo ? "Demo · nenhuma conexão real." : "SQL Server e MySQL: experimentais."; color: Tokens.muted; Layout.fillWidth: true }
    ProgressPanel { Layout.fillWidth: true; visible: appModel.state.busy }
    FileDialog {
        id: picker
        property string purpose: "jar"
        property string side: "source"
        title: purpose === "jar" ? "Selecionar driver JDBC" : "Importar perfil de conexão"
        nameFilters: purpose === "jar" ? ["Driver JDBC (*.jar)"] : ["Perfil YAML (*.yml *.yaml)"]
        onAccepted: appModel.chooseFile(purpose, side, selectedFile.toString())
    }
    function pick(purpose, side) { picker.purpose = purpose; picker.side = side; picker.open() }
}
