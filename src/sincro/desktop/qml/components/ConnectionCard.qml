import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
GlassPanel {
    id: root
    property var connection
    property string side: "source"
    property bool advanced: false
    property string title: "Origem"
    signal fileRequested(string purpose, string side)
    implicitHeight: body.implicitHeight + Tokens.lg * 2
    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: Tokens.lg
        spacing: Tokens.sm
        RowLayout {
            AppIcon { name: "connections"; color: Tokens.accent }
            AppLabel { text: root.title; font.pixelSize: Tokens.heading; font.weight: Font.DemiBold; Layout.fillWidth: true }
            StatusBadge { text: root.connection.fields.status; tone: root.connection.fields.status === "Conectada" ? "passed" : "pending" }
        }
        SelectField {
            Layout.fillWidth: true; label: "Engine"; model: appModel.state.engineNames
            iconSources: ["../../assets/databases/firebird.png", "../../assets/databases/postgresql.png", "../../assets/databases/sqlserver.png", "../../assets/databases/mysql.png"]
            currentIndex: root.connection.fields.engineIndex
            enabled: !appModel.state.busy && !appModel.state.demo
            onActivated: index => root.connection.setField("engine", appModel.state.engineKeys[index])
        }
        RowLayout {
            Layout.fillWidth: true; spacing: Tokens.sm
            AppTextField { Layout.fillWidth: true; Layout.preferredWidth: 3; label: "Host"; text: root.connection.fields.host; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => root.connection.setField("host", value) }
            AppTextField { Layout.fillWidth: true; Layout.preferredWidth: 1; label: "Porta"; text: root.connection.fields.port; inputMethodHints: Qt.ImhDigitsOnly; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => root.connection.setField("port", value) }
        }
        AppTextField { Layout.fillWidth: true; label: "Banco"; text: root.connection.fields.database; placeholderText: "Nome do banco"; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => root.connection.setField("database", value) }
        RowLayout {
            spacing: Tokens.sm
            AppTextField { Layout.fillWidth: true; label: "Usuário"; text: root.connection.fields.user; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => root.connection.setField("user", value) }
            PasswordField { Layout.fillWidth: true; enabled: !appModel.state.busy && !appModel.state.demo; onEdited: value => root.connection.setSecret(value) }
        }
        RowLayout {
            spacing: Tokens.sm
            AppTextField { Layout.fillWidth: true; label: "Driver JDBC (.jar)"; text: root.connection.fields.jar; placeholderText: appModel.state.demo ? "Não necessário na demonstração" : "Selecione o arquivo .jar"; readOnly: true }
            SecondaryButton { text: "Selecionar"; Layout.alignment: Qt.AlignBottom; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: root.fileRequested("jar", root.side) }
        }
        AppLabel { visible: root.advanced; text: root.connection.fields.driver; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
        RowLayout {
            Layout.topMargin: Tokens.xs
            PrimaryButton { text: "Testar conexão"; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: appModel.execute("test_" + root.side) }
            SecondaryButton { text: "Avançado"; onClicked: root.advanced = !root.advanced }

        }
        SecondaryButton { visible: root.advanced; text: "Importar YAML"; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: root.fileRequested("import", root.side) }
    }
}
