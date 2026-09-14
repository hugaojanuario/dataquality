import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"
Page {
    id: root
    PageTitle { title: "Mapeamento"; subtitle: "Revise origem, destino e chaves."; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.sm
        SelectField { model: ["Todos", "Mapeados", "Não mapeados", "Ambíguos", "Ignorados"]; currentIndex: model.indexOf(appModel.state.mappingFilter); onActivated: appModel.filter("mapping", currentText) }
        Item { Layout.fillWidth: true }
        StatusBadge { text: appModel.state.blocked + " pendências de revisão"; tone: appModel.state.blocked ? "inconclusive" : "passed" }
        SecondaryButton { text: "Gerar sugestões"; enabled: !appModel.state.busy && appModel.state.mappingCount === 0; onClicked: appModel.execute("suggest") }
        PrimaryButton { text: "Salvar manifesto"; enabled: !appModel.state.busy && appModel.state.mappingCount > 0; onClicked: appModel.execute("save_mapping") }
    }
    DataTable {
        Layout.fillWidth: true; visible: appModel.state.mappingRows.length > 0
        rows: appModel.state.mappingRows
        columns: [{title:"ORIGEM", key:"source", width:220}, {title:"DESTINO", key:"target", width:220}, {title:"CONFIANÇA", key:"confidence", width:100}, {title:"REVISÃO", key:"status", width:100}]
        onRowClicked: row => { appModel.editMapping(row.index); editor.open() }
    }
    EmptyState { Layout.fillWidth: true; visible: appModel.state.mappingRows.length === 0; title: "Nenhum mapeamento neste filtro"; description: "Descubra os dois bancos e gere sugestões. Sugestões reais nunca são confirmadas automaticamente."; iconName: "mapping" }
    AppLabel { text: "Alterações são salvas automaticamente. Use Salvar manifesto para validar tudo agora."; color: Tokens.muted; Layout.fillWidth: true }
    Dialog {
        id: editor
        objectName: "mappingDialog"
        parent: Overlay.overlay
        modal: true
        width: Math.min(820, Overlay.overlay.width - Tokens.xxl)
        height: Math.min(720, Overlay.overlay.height - Tokens.xxl)
        anchors.centerIn: parent
        padding: Tokens.lg
        background: GlassPanel { solid: true }
        header: AppLabel { text: "Revisar mapeamento"; font.pixelSize: Tokens.heading; padding: Tokens.lg }
        contentItem: ScrollView {
            id: editorScroll
            clip: true; contentWidth: availableWidth
            ColumnLayout {
                width: editorScroll.availableWidth; spacing: Tokens.md
                AppLabel { text: appModel.state.mappingEditor.source || ""; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
                AppLabel { text: appModel.state.mappingEditor.reason || ""; color: Tokens.muted; Layout.fillWidth: true }
                SelectField {
                    Layout.fillWidth: true; label: "Tabela de destino"; model: appModel.state.targetOptions; textRole: "label"; valueRole: "value"
                    currentIndex: Math.max(0, appModel.state.targetOptions.findIndex(t => t.value === appModel.state.mappingEditor.target))
                    onActivated: appModel.updateMapping("target", currentValue)
                }
                RowLayout {
                    AppTextField { Layout.fillWidth: true; label: "Chave da origem · vírgulas"; text: appModel.state.mappingEditor.sourceKey || ""; onEdited: value => appModel.updateMapping("source_key", value) }
                    AppTextField { Layout.fillWidth: true; label: "Chave do destino · mesma ordem"; text: appModel.state.mappingEditor.targetKey || ""; onEdited: value => appModel.updateMapping("target_key", value) }
                }
                CheckBox { text: "Excluir esta tabela do escopo"; checked: appModel.state.mappingEditor.ignored || false; onClicked: appModel.updateMapping("ignored", checked.toString()); palette.windowText: Tokens.text }
                AppTextField { Layout.fillWidth: true; visible: appModel.state.mappingEditor.ignored || false; label: "Justificativa da exclusão"; text: appModel.state.mappingEditor.justification || ""; onEdited: value => appModel.updateMapping("justification", value) }
                AppLabel { text: "COLUNA DE ORIGEM  →  COLUNA DE DESTINO"; color: Tokens.muted; font.pixelSize: Tokens.caption }
                Repeater {
                    model: (appModel.state.mappingEditor.columns || []).length
                    ColumnLayout {
                        id: col
                        required property int index
                        property var modelData: appModel.state.mappingEditor.columns[index]
                        Layout.fillWidth: true
                        RowLayout {
                            AppLabel { text: col.modelData.source; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                            AppTextField { Layout.fillWidth: true; Layout.preferredWidth: 1; text: col.modelData.target; label: "Destino de " + col.modelData.source; onEdited: value => appModel.updateColumn(col.index, "target", value) }
                            CheckBox { text: "Ignorar"; checked: col.modelData.ignored; palette.windowText: Tokens.text; onClicked: appModel.updateColumn(col.index, "ignored", checked.toString()) }
                        }
                        AppTextField { Layout.fillWidth: true; visible: col.modelData.ignored; label: "Justificativa · " + col.modelData.source; text: col.modelData.justification; onEdited: value => appModel.updateColumn(col.index, "justification", value) }
                    }
                }
            }
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            SecondaryButton { text: "Fechar"; onClicked: editor.close(); Layout.bottomMargin: Tokens.lg }
            PrimaryButton { text: appModel.state.mappingEditor.confirmed ? "Revisão confirmada" : "Confirmar revisão"; enabled: !appModel.state.busy; onClicked: appModel.confirmMapping(); Layout.rightMargin: Tokens.lg; Layout.bottomMargin: Tokens.lg }
        }
    }
}
