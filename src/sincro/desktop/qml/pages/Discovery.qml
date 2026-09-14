import QtQuick
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Descoberta"; subtitle: "Selecione as tabelas para revisão."; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.sm
        AppTextField { Layout.fillWidth: true; placeholderText: "Pesquisar schema ou tabela…"; text: appModel.state.discoverySearch; onEdited: value => appModel.filter("discovery", value) }
        PrimaryButton { text: "Descobrir bancos"; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: appModel.execute("discover") }
        SecondaryButton { text: "Gerar sugestões"; enabled: !appModel.state.busy && appModel.state.discovered > 0 && appModel.state.mappingCount === 0; onClicked: appModel.execute("suggest") }
    }
    RowLayout {
        Layout.fillWidth: true
        AppLabel { text: appModel.state.discovered + " objetos encontrados  ·  " + appModel.state.selectedCount + " selecionados"; color: Tokens.muted; Layout.fillWidth: true }
        SecondaryButton { text: "Selecionar origem"; onClicked: appModel.selectAll(true) }
        SecondaryButton { text: "Limpar"; onClicked: appModel.selectAll(false) }
        SecondaryButton { text: "Justificar exclusão"; enabled: appModel.state.selectedCount > 0 && appModel.state.mappingCount > 0 && !appModel.state.busy; onClicked: exclusion.open() }
    }
    DataTable {
        Layout.fillWidth: true
        visible: appModel.state.discoveryRows.length > 0
        rows: appModel.state.discoveryRows
        selectable: true
        columns: [{title:"TABELA / SCHEMA", key:"name", width:240}, {title:"CONEXÃO", key:"origin", width:85}, {title:"COLUNAS", key:"columns", width:70}, {title:"PK", key:"pk", width:85}, {title:"FK", key:"fk", width:45}, {title:"ESCOPO", key:"status", width:105}]
        onSelectionChanged: (row, selected) => appModel.selectTable(row.tableId, selected)
    }
    EmptyState { Layout.fillWidth: true; visible: appModel.state.discoveryRows.length === 0; title: appModel.state.discovered ? "Nenhuma tabela neste filtro" : "O inventário começa aqui"; description: "Configure origem e destino e descubra os metadados. Nenhum registro será alterado." }
    ProgressPanel { Layout.fillWidth: true; visible: appModel.state.busy }
    AppLabel { text: "Exclusões exigem justificativa e reduzem a cobertura."; color: Tokens.muted; Layout.fillWidth: true }
    ConfirmDialog { id: exclusion; title: "Excluir do escopo comparado"; message: "As tabelas permanecem no inventário. Exclusões reduzem a cobertura e impedem aprovação global."; needsReason: true; acceptText: "Aplicar exclusões"; onAccepted: appModel.excludeSelected(reason) }
}
