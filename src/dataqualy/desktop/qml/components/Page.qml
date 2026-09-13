import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
ScrollView {
    id: root
    default property alias contents: body.data
    clip: true
    contentWidth: availableWidth
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ColumnLayout {
        id: body
        width: root.availableWidth
        spacing: Tokens.lg
    }
}
