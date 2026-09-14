import QtQuick
import QtQuick.Controls
AppTextField {
    label: "Senha"
    echoMode: TextInput.Password
    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
    placeholderText: "Senha de acesso"
}
