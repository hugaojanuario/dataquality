import QtQuick
import ".."
Text {
    color: Tokens.text
    font.family: Tokens.font
    font.pixelSize: Tokens.body
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
