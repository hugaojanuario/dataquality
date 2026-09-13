import QtQuick
import QtQuick.Layouts
import ".."
import "../components"
Page {
    PageTitle { title: "Histórico"; subtitle: "Etapas deste projeto · horários em UTC."; Layout.fillWidth: true }
    DataTable { Layout.fillWidth: true; visible: appModel.state.stages.length > 0; rows: appModel.state.stages; columns: [{title:"ETAPA", key:"name", width:220}, {title:"STATUS", key:"status", width:140}, {title:"CONCLUSÃO · UTC", key:"time", width:200}] }
    EmptyState { Layout.fillWidth: true; visible: appModel.state.stages.length === 0; title: "Sua primeira execução começa aqui"; description: "As capturas e comparações serão registradas no diretório do projeto. Use as configurações para abrir um projeto existente."; iconName: "history" }
    SecondaryButton { text: "Ver resultado atual"; visible: appModel.state.hasResult; onClicked: appModel.navigate(7) }
    AppLabel { text: "Histórico do projeto aberto."; color: Tokens.muted; Layout.fillWidth: true }
}
