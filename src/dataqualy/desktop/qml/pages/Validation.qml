import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Validação"; subtitle: "Capture antes e compare depois da conversão."; Layout.fillWidth: true }
    GlassPanel {
        Layout.fillWidth: true
        implicitHeight: options.implicitHeight + Tokens.lg * 2
        ColumnLayout {
            id: options; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
            RowLayout {
                Layout.fillWidth: true; spacing: Tokens.lg
                SelectField { label: "Profundidade da captura"; model: ["Rápido", "Balanceado", "Exaustivo"]; currentIndex: ["fast", "balanced", "exhaustive"].indexOf(appModel.state.profile); enabled: !appModel.state.busy && !appModel.state.demo; onActivated: index => appModel.configure("profile", ["fast", "balanced", "exhaustive"][index]) }
                AppLabel { text: appModel.state.profile === "exhaustive" ? "Compara registros por chave, com evidências HMAC." : appModel.state.profile === "fast" ? "Contagens e nulos. Não compara valores." : "Contagens e agregados. Não compara valores."; color: Tokens.muted; Layout.fillWidth: true }
            }
            CheckBox { text: "Confirmo que suspendi as escritas durante as capturas"; checked: appModel.state.quiescent; enabled: !appModel.state.busy && !appModel.state.demo; onClicked: appModel.configure("quiescent", checked.toString()); palette.windowText: Tokens.text }
            AppLabel { text: appModel.state.mappingCount + " tabelas no manifesto  ·  " + appModel.state.confirmed + " revisadas  ·  " + appModel.state.blocked + " pendências"; color: Tokens.muted }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.md
        GlassPanel {
            Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: before.implicitHeight + Tokens.lg * 2
            ColumnLayout {
                id: before; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
                AppLabel { text: "01  Antes da conversão"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
                AppLabel { text: "Capture a origem e o destino vazio para preservar a baseline."; color: Tokens.muted; Layout.fillWidth: true }
                SecondaryButton { text: appModel.state.sourceReady ? "Origem capturada" : "Capturar origem"; enabled: !appModel.state.busy && !appModel.state.demo && !appModel.state.baselineReady; onClicked: appModel.execute("source") }
                SecondaryButton { text: appModel.state.baselineReady ? "Baseline capturada" : "Capturar baseline"; enabled: !appModel.state.busy && !appModel.state.demo && appModel.state.sourceReady && !appModel.state.targetReady; onClicked: appModel.execute("baseline") }
            }
        }
        GlassPanel {
            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.fillHeight: true
            ColumnLayout {
                anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.md
                AppLabel { text: "02  Após a conversão"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
                AppLabel { text: "Revise o manifesto e capture o destino para gerar o relatório."; color: Tokens.muted; Layout.fillWidth: true }
                PrimaryButton { text: "Capturar e validar destino"; enabled: !appModel.state.busy && !appModel.state.demo && appModel.state.baselineReady && appModel.state.mappingCount > 0 && appModel.state.blocked === 0; onClicked: appModel.execute("target") }
                SecondaryButton { text: "Comparar snapshots salvos"; enabled: !appModel.state.busy && appModel.state.targetReady; onClicked: appModel.execute("report") }
            }
        }
    }
    ProgressPanel { Layout.fillWidth: true; visible: appModel.state.busy }
    Repeater { model: appModel.state.timeline; AppLabel { required property string modelData; text: modelData; color: Tokens.muted; Layout.fillWidth: true } }
    SecondaryButton { text: "Abrir resultado e findings  →"; visible: appModel.state.hasResult || appModel.state.findingCount > 0; onClicked: appModel.navigate(7) }
    AppLabel { text: "Execute seu conversor externamente entre as capturas."; color: Tokens.muted; Layout.fillWidth: true }
}
