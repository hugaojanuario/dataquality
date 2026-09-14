import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
Rectangle {
    id: root
    property bool collapsed: false
    color: Tokens.transparent
    clip: true
    implicitWidth: collapsed ? Tokens.collapsedWidth : Tokens.sidebarWidth
    Behavior on implicitWidth { NumberAnimation { duration: Tokens.normal; easing.type: Tokens.easing } }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0; color: Tokens.dark ? "#ed214761" : "#ed1e4d69" }
            GradientStop { position: 0.48; color: Tokens.dark ? "#e815344b" : "#ea173f5a" }
            GradientStop { position: 1; color: Tokens.dark ? "#f00d2639" : "#ef0d3148" }
        }
    }
    Rectangle {
        width: 260; height: 260; radius: 130
        x: -145; y: -95
        color: Tokens.dark ? "#173fa7cc" : "#2459c9ed"
        border.color: "#25ffffff"
        border.width: 1
    }
    Rectangle {
        width: 230; height: 230; radius: 115
        x: root.width - 115; y: root.height - 175
        color: Tokens.dark ? "#123ac6a0" : "#164be0b5"
        border.color: "#18ffffff"
        border.width: 1
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        height: 1
        color: "#35ffffff"
    }
    Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: "#45ffffff" }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.md
        spacing: Tokens.xxs
        RowLayout {
            Layout.topMargin: Tokens.xs
            Layout.bottomMargin: Tokens.xl
            Image {
                source: "../../assets/app-icon.svg"
                sourceSize.width: Tokens.xxl
                sourceSize.height: Tokens.xxl
                Layout.preferredWidth: Tokens.fieldHeight
                Layout.preferredHeight: Tokens.fieldHeight
                fillMode: Image.PreserveAspectFit
                Accessible.name: "Sincro · veleiro"
            }
            ColumnLayout {
                visible: !root.collapsed
                Layout.fillWidth: true
                spacing: Tokens.xxs
                AppLabel { text: "Sincro"; font.pixelSize: Tokens.subtitle; font.weight: Font.DemiBold; color: Tokens.navigationText }
                AppLabel { text: "Auditoria de dados"; font.pixelSize: Tokens.caption; color: Tokens.navigationMuted }
            }
        }
        AppLabel { text: "NAVEGAÇÃO"; font.pixelSize: Tokens.caption; color: Tokens.navigationMuted; visible: !root.collapsed; Layout.bottomMargin: Tokens.sm }
        Repeater {
            model: [{label:"Visão geral", icon:"overview"}, {label:"Conexões", icon:"connections"}, {label:"Descoberta", icon:"discover"}, {label:"Mapeamento", icon:"mapping"}, {label:"Validação", icon:"validation"}, {label:"Histórico", icon:"history"}]
            SidebarItem {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                text: modelData.label
                iconName: modelData.icon
                collapsed: root.collapsed
                selected: appModel.state.page === index || (index === 4 && appModel.state.page === 7)
                onClicked: appModel.navigate(index)
            }
        }
        Item { Layout.fillHeight: true }
        Rectangle {
            visible: !root.collapsed
            Layout.fillWidth: true
            implicitHeight: Tokens.xxl + Tokens.lg
            radius: Tokens.radiusSm
            color: Tokens.navigationHover
            ColumnLayout {
                anchors.fill: parent; anchors.margins: Tokens.sm; spacing: Tokens.xxs
                AppLabel { text: appModel.state.demo ? "Demonstração" : "Workspace local"; color: Tokens.navigationText; font.pixelSize: Tokens.caption }
                AppLabel { text: appModel.state.demo ? "Dados sintéticos" : "Seus dados ficam aqui"; color: Tokens.navigationMuted; font.pixelSize: Tokens.caption; Layout.fillWidth: true }
            }
            Layout.bottomMargin: Tokens.md
        }
        SidebarItem { Layout.fillWidth: true; text: "Configurações"; iconName: "settings"; collapsed: root.collapsed; selected: appModel.state.page === 6; onClicked: appModel.navigate(6) }
        SidebarItem { Layout.fillWidth: true; text: root.collapsed ? "Expandir menu" : "Recolher menu"; iconName: "menu"; collapsed: root.collapsed; onClicked: root.collapsed = !root.collapsed }
    }
}
