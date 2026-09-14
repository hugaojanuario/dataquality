import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Relatório"; subtitle: appModel.state.demo ? "Demo · uma divergência sintética." : ""; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true
        StatusBadge { text: "GLOBAL · " + appModel.state.resultLabel; tone: appModel.state.resultStatus }
        Item { Layout.fillWidth: true }
        SecondaryButton { text: "Exportar HTML"; enabled: appModel.state.hasReport && !appModel.state.busy; onClicked: exportDialog.open() }
        PrimaryButton { text: "Abrir relatório"; enabled: appModel.state.hasReport; onClicked: appModel.openReport() }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.sm
        AppTextField { Layout.fillWidth: true; placeholderText: "Filtrar por tabela…"; text: appModel.state.findingSearch; onEdited: value => appModel.filter("table", value) }
        SelectField { model: ["Todos", "Aprovado", "Divergência", "Inconclusivo", "Erro", "Ignorado"]; currentIndex: model.indexOf(appModel.state.findingStatus); onActivated: appModel.filter("status", currentText) }
        SelectField { model: appModel.state.rules; currentIndex: model.indexOf(appModel.state.findingRule); onActivated: appModel.filter("rule", currentText) }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.lg; Layout.alignment: Qt.AlignTop
        ColumnLayout {
            Layout.fillWidth: true; Layout.preferredWidth: 3; Layout.alignment: Qt.AlignTop; spacing: Tokens.md
            DataTable {
                Layout.fillWidth: true; visible: appModel.state.findingRows.length > 0
                implicitHeight: Tokens.rowHeight * 8
                rows: appModel.state.findingRows
                columns: [{title:"TABELA", key:"table", width:150}, {title:"REGRA", key:"rule", width:170}, {title:"STATUS", key:"status", width:100}]
                onRowClicked: row => appModel.showFinding(row.index)
            }
            EmptyState { Layout.fillWidth: true; visible: appModel.state.findingRows.length === 0; title: appModel.state.hasResult ? "Nenhum finding neste filtro" : "Aguardando uma auditoria"; description: "Sem evidências, não há aprovação."; iconName: "validation" }
            AppLabel { text: appModel.state.findingCount + " verificações. Selecione uma linha para consultar as evidências."; color: Tokens.muted; Layout.fillWidth: true; font.pixelSize: Tokens.caption }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.preferredWidth: 1.15; Layout.alignment: Qt.AlignTop; spacing: Tokens.md
            GlassPanel {
                Layout.fillWidth: true
                implicitHeight: summary.implicitHeight + Tokens.lg * 2
                ColumnLayout {
                    id: summary; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
                    AppLabel { text: "Cobertura do escopo"; color: Tokens.muted; font.pixelSize: Tokens.caption }
                    AppLabel { text: appModel.state.tableCoverage; font.pixelSize: Tokens.display; font.weight: Font.DemiBold; color: Tokens.text }
                    AppLabel { text: "Colunas: " + appModel.state.columnCoverage; color: Tokens.muted; font.pixelSize: Tokens.caption }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.border }
                    AppLabel { text: appModel.state.passed + " checks aprovados"; color: Tokens.success; Layout.fillWidth: true }
                    AppLabel { text: appModel.state.failed + " checks divergentes"; color: Tokens.danger; Layout.fillWidth: true }
                    AppLabel { text: "Qualidade: " + appModel.state.quality; color: Tokens.muted; Layout.fillWidth: true; font.pixelSize: Tokens.caption }
                }
            }
            GlassPanel {
                Layout.fillWidth: true; visible: appModel.state.failed > 0
                implicitHeight: alert.implicitHeight + Tokens.md * 2
                ColumnLayout {
                    id: alert; anchors.fill: parent; anchors.margins: Tokens.md; spacing: Tokens.sm
                    StatusBadge { text: "Requer revisão"; tone: "failed" }
                    AppLabel { text: "Dados divergentes"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    AppLabel { text: "Revise as evidências antes de aprovar."; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
                    SecondaryButton { text: "Ver divergências"; onClicked: appModel.filter("status", "Divergência") }
                }
            }
        }
    }
    FileDialog { id: exportDialog; title: "Exportar relatório HTML"; fileMode: FileDialog.SaveFile; defaultSuffix: "html"; nameFilters: ["Relatório HTML (*.html)"]; onAccepted: appModel.exportReport(selectedFile.toString()) }
}
