pragma Singleton
import QtQuick
QtObject {
    readonly property bool dark: appModel.dark
    readonly property color canvas: dark ? "#102536" : "#e4f2fb"
    readonly property color sidebar: dark ? "#122d43" : "#213d56"
    readonly property color surface: dark ? "#f51b3347" : "#faffffff"
    readonly property color solidSurface: dark ? "#1b3347" : "#ffffff"
    readonly property color raised: dark ? "#284459" : "#eef5fb"
    readonly property color input: dark ? "#142b3e" : "#fbfdff"
    readonly property color border: dark ? "#345064" : "#d9e5f1"
    readonly property color glassBorder: dark ? "#24395064" : "#e6eef5"
    readonly property color text: dark ? "#ebf4fc" : "#18314d"
    readonly property color muted: dark ? "#adc2d3" : "#5e748b"
    readonly property color accent: dark ? "#a6ceff" : "#3d7cec"
    readonly property color accentFill: dark ? "#a6ceff" : "#112d49"
    readonly property color accentText: dark ? "#102a45" : "#ffffff"
    readonly property color accentSoft: dark ? "#244761" : "#e7f0ff"
    readonly property color success: dark ? "#7bd8ba" : "#188567"
    readonly property color warning: dark ? "#f0c781" : "#936a17"
    readonly property color danger: dark ? "#ffaeb7" : "#c24458"
    readonly property color neutral: dark ? "#b7aecb" : "#725993"
    readonly property color shadow: dark ? "#33081521" : "#121d405e"
    readonly property color canvasEnd: dark ? "#132f3e" : "#e0f3ee"
    readonly property color navigationText: "#eff7ff"
    readonly property color navigationMuted: "#b4c8d9"
    readonly property color navigationSelected: "#3a5671"
    readonly property color navigationHover: "#2d4962"
    readonly property color navigationBorder: "#1f3a52"
    readonly property color transparent: "transparent"
    readonly property int xxs: 4
    readonly property int xs: 8
    readonly property int sm: 12
    readonly property int md: 16
    readonly property int lg: 24
    readonly property int xl: 32
    readonly property int xxl: 48
    readonly property int radiusSm: 10
    readonly property int radius: 14
    readonly property int radiusLg: 18
    readonly property int fieldHeight: 42
    readonly property int rowHeight: 52
    readonly property int sidebarWidth: 212
    readonly property int collapsedWidth: 72
    readonly property int headerHeight: 56
    readonly property int minWidth: 1024
    readonly property int minHeight: 700
    readonly property int initialWidth: 1280
    readonly property int initialHeight: 800
    readonly property int caption: 12
    readonly property int body: 14
    readonly property int subtitle: 16
    readonly property int heading: 24
    readonly property int display: 28
    readonly property string font: Qt.platform.os === "windows" ? "Segoe UI" : Qt.application.font.family
    readonly property int fast: appModel.reducedMotion ? 0 : 120
    readonly property int normal: appModel.reducedMotion ? 0 : 180
    readonly property int easing: Easing.OutCubic
    readonly property real disabledOpacity: 0.45
    readonly property real surfaceOpacity: 0.96
    readonly property int shadowOffset: 3
    function semantic(tone) {
        if (tone === "passed") return success
        if (tone === "failed" || tone === "error") return danger
        if (tone === "inconclusive") return warning
        if (tone === "skipped") return neutral
        return accent
    }
}
