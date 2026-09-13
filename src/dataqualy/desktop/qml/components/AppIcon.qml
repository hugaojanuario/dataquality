import QtQuick
import ".."
Canvas {
    id: root
    property string name: "overview"
    property color color: Tokens.muted
    implicitWidth: Tokens.lg
    implicitHeight: Tokens.lg
    onColorChanged: requestPaint()
    onNameChanged: requestPaint()
    onPaint: {
        const c = getContext("2d"); c.reset(); c.scale(width / 24, height / 24)
        c.strokeStyle = color; c.lineWidth = 1.6; c.lineCap = "round"; c.lineJoin = "round"
        function line(x,y,a,b) { c.moveTo(x,y); c.lineTo(a,b) }
        c.beginPath()
        if (name === "overview") { c.rect(4,4,6,6); c.rect(14,4,6,6); c.rect(4,14,6,6); c.rect(14,14,6,6) }
        else if (name === "connections") { c.ellipse(4,3,16,6); line(4,6,4,18); line(20,6,20,18); c.moveTo(4,12); c.bezierCurveTo(4,17,20,17,20,12); c.moveTo(4,18); c.bezierCurveTo(4,23,20,23,20,18) }
        else if (name === "discover") { c.arc(10,10,6,0,2*Math.PI); line(15,15,21,21) }
        else if (name === "mapping") { c.rect(3,4,6,5); c.rect(15,15,6,5); line(6,9,6,17); line(6,17,15,17); line(12,14,15,17); line(12,20,15,17) }
        else if (name === "validation") { c.moveTo(12,3); c.lineTo(20,6); c.lineTo(19,15); c.quadraticCurveTo(17,19,12,22); c.quadraticCurveTo(7,19,5,15); c.lineTo(4,6); c.closePath(); line(8,12,11,15); line(11,15,16,9) }
        else if (name === "history") { c.arc(12,12,9,0,Math.PI*1.8); line(12,6,12,12); line(12,12,16,14) }
        else if (name === "settings") { line(4,7,20,7); line(4,17,20,17); c.rect(8,4,4,6); c.rect(14,14,4,6) }
        else if (name === "arrow") { line(4,12,20,12); line(15,7,20,12); line(15,17,20,12) }
        else if (name === "close") { line(6,6,18,18); line(18,6,6,18) }
        else if (name === "check") { line(5,12,10,17); line(10,17,19,7) }
        else if (name === "menu") { line(5,6,19,6); line(5,12,19,12); line(5,18,19,18) }
        else { c.arc(12,12,8,0,2*Math.PI); line(12,8,12,13); line(12,16,12,16.2) }
        c.stroke()
    }
}
