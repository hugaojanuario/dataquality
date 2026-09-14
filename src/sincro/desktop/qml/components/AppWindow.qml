import QtQuick
import QtQuick.Controls
import ".."
ApplicationWindow {
    width: Tokens.initialWidth
    height: Tokens.initialHeight
    minimumWidth: Tokens.minWidth
    minimumHeight: Tokens.minHeight
    visible: true
    color: appModel.nativeBackdrop ? Tokens.transparent : Tokens.canvas
    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0; color: Tokens.canvas }
            GradientStop { position: 1; color: Tokens.canvasEnd }
        }
    }
    title: "Sincro" + (appModel.state.demo ? " · Demonstração sintética" : "")
    font.family: Tokens.font
    font.pixelSize: Tokens.body
    palette.window: Tokens.canvas
    palette.windowText: Tokens.text
    palette.text: Tokens.text
    palette.buttonText: Tokens.text
    palette.base: Tokens.input
    palette.button: Tokens.surface
    palette.highlight: Tokens.accentSoft
    palette.highlightedText: Tokens.text
}
