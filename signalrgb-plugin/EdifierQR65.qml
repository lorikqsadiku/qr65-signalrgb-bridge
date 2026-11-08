import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    anchors.fill: parent

    Flickable {
        anchors.fill: parent
        contentHeight: column.height
        clip: true

        ColumnLayout {
            id: column
            width: parent.width
            spacing: 16

            Text {
                text: "Edifier QR65 BLE Bridge"
                font.family: "Poppins"
                font.pointSize: 16
                font.bold: true
                color: theme.primary1
            }

            Text {
                text: "This plugin sends colors to your Edifier QR65 speaker via a local BLE bridge server."
                font.family: "Poppins"
                font.pointSize: 10
                color: theme.primary2
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.primary2
                opacity: 0.3
            }

            Text {
                text: "Setup"
                font.family: "Poppins"
                font.pointSize: 13
                font.bold: true
                color: theme.primary1
            }

            Text {
                text: "1. Run install.cmd from the bridge folder (once).\n\n2. The bridge starts with Windows, finds your QR65 over Bluetooth and keeps it connected - in USB and Bluetooth mode.\n\n3. Apply any SignalRGB effect - the speaker will sync!\n\nColor calibration: http://127.0.0.1:5297/calibrate"
                font.family: "Poppins"
                font.pointSize: 10
                color: theme.primary2
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.primary2
                opacity: 0.3
            }

            Text {
                text: "Connection Test"
                font.family: "Poppins"
                font.pointSize: 13
                font.bold: true
                color: theme.primary1
            }

            RowLayout {
                spacing: 12

                Button {
                    text: "Test Connection"
                    font.family: "Poppins"

                    background: Rectangle {
                        color: "#2196F3"
                        radius: 4
                    }

                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        statusText.text = "Checking...";
                        statusText.color = theme.primary2;
                        var xhr = new XMLHttpRequest();
                        var port = service.loadSetting("bridgePort", "5297");
                        xhr.open("GET", "http://127.0.0.1:" + port + "/status", true);
                        xhr.onreadystatechange = function() {
                            if (xhr.readyState === 4) {
                                if (xhr.status === 200) {
                                    var data = JSON.parse(xhr.responseText);
                                    if (data.connected) {
                                        statusText.text = "Connected to " + data.address;
                                        statusText.color = "#4CAF50";
                                    } else {
                                        statusText.text = "Bridge running, BLE disconnected";
                                        statusText.color = "#FF9800";
                                    }
                                } else {
                                    statusText.text = "Bridge not running";
                                    statusText.color = "#F44336";
                                }
                            }
                        };
                        xhr.send();
                    }
                }

                Text {
                    id: statusText
                    text: "Not tested"
                    font.family: "Poppins"
                    font.pointSize: 10
                    color: theme.primary2
                }
            }
        }
    }
}
