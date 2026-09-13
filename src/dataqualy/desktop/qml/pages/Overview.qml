import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Visão geral"; subtitle: ""; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.md
        MetricCard { Layout.fillWidth: true; iconName: "overview"; label: "TABELAS"; value: appModel.state.tableCount; note: "Na captura de origem" }
        MetricCard { Layout.fillWidth: true; iconName: "connections"; label: "REGISTROS"; value: appModel.state.sourceRows; note: "Contagem na origem" }
        MetricCard { Layout.fillWidth: true; iconName: "info"; label: "DIVERGÊNCIAS"; value: appModel.state.hasResult ? String(appModel.state.failed) : "—"; note: "Checks com divergência"; valueColor: Tokens.danger }
        MetricCard { Layout.fillWidth: true; iconName: "validation"; label: "COBERTURA"; value: appModel.state.tableCoverage; note: "Tabelas comparadas"; valueColor: Tokens.accent }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: Tokens.lg; Layout.alignment: Qt.AlignTop
        GlassPanel {
            Layout.fillWidth: true; Layout.preferredWidth: 3; Layout.alignment: Qt.AlignTop
            implicitHeight: project.implicitHeight + Tokens.lg * 2
            ColumnLayout {
                id: project; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.lg
                RowLayout {
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: Tokens.xs
                        AppLabel { text: appModel.state.projectName; font.pixelSize: Tokens.heading; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        AppLabel { text: appModel.state.description; color: Tokens.muted; Layout.fillWidth: true }
                    }
                    StatusBadge { text: appModel.state.demo ? "Sintético" : "Auditoria local"; tone: "pending" }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: Tokens.sm
                    RowLayout {
                        AppLabel { text: "Etapas concluídas"; Layout.fillWidth: true; color: Tokens.muted }
                        AppLabel { text: appModel.state.completed + " de 4"; color: Tokens.accent; font.weight: Font.DemiBold }
                    }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: Tokens.xs; radius: Tokens.xxs; color: Tokens.accentSoft
                        Rectangle { width: parent.width * appModel.state.completed / 4; height: parent.height; radius: parent.radius; color: Tokens.accent }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: Tokens.sm
                    Repeater {
                        model: [{title:"ORIGEM", vm:appModel.sourceConnection}, {title:"DESTINO", vm:appModel.targetConnection}]
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; Layout.preferredWidth: 1
                            implicitHeight: route.implicitHeight + Tokens.md * 2
                            color: Tokens.input; radius: Tokens.radius; border.color: Tokens.border
                            ColumnLayout {
                                id: route; anchors.fill: parent; anchors.margins: Tokens.md; spacing: Tokens.xs
                                AppLabel { text: modelData.title; font.pixelSize: Tokens.caption; color: Tokens.muted }
                                AppLabel { text: modelData.vm.fields.database || "Não configurado"; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideMiddle; maximumLineCount: 1 }
                                AppLabel { text: appModel.state.engineNames[modelData.vm.fields.engineIndex]; font.pixelSize: Tokens.caption; color: Tokens.muted; Layout.fillWidth: true }
                            }
                        }
                    }
                }
                PrimaryButton { text: appModel.state.hasResult ? "Ver relatório" : appModel.state.discovered ? "Continuar auditoria" : "Configurar conexões"; onClicked: appModel.navigate(appModel.state.hasResult ? 7 : appModel.state.discovered ? 4 : 1) }
                AppLabel { text: "Cobertura não significa aprovação."; color: Tokens.muted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
            }
        }
        GlassPanel {
            Layout.fillWidth: true; Layout.preferredWidth: 1.35; Layout.fillHeight: true
            implicitHeight: activity.implicitHeight + Tokens.lg * 2
            ColumnLayout {
                id: activity; anchors.fill: parent; anchors.margins: Tokens.lg; spacing: Tokens.lg
                AppLabel { text: "Atividade recente"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold }
                Repeater {
                    model: appModel.state.stages.slice(-4)
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true; spacing: Tokens.xs
                        RowLayout {
                            Rectangle { implicitWidth: Tokens.xs; implicitHeight: Tokens.xs; radius: Tokens.xxs; color: Tokens.semantic(modelData.tone) }
                            AppLabel { text: modelData.name; Layout.fillWidth: true; font.pixelSize: Tokens.caption; font.weight: Font.Medium }
                        }
                        AppLabel { text: modelData.status; color: Tokens.semantic(modelData.tone); font.pixelSize: Tokens.caption; Layout.leftMargin: Tokens.md }
                    }
                }
                AppLabel { visible: appModel.state.stages.length === 0; text: "Nenhuma etapa executada. As capturas aparecerão aqui."; color: Tokens.muted; Layout.fillWidth: true }
                Item { Layout.fillHeight: true }
                SecondaryButton { text: "Abrir histórico"; onClicked: appModel.navigate(5) }
            }
        }
    }
}
