<#
  Show a Windows toast notification. Used by the QR65 bridge when the speaker's Bluetooth is asleep.
  Text is inserted with CreateTextNode, so it is never interpreted as XML.
#>
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Message
)
$ErrorActionPreference = 'Stop'
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $template.GetElementsByTagName('text')
$null = $text.Item(0).AppendChild($template.CreateTextNode($Title))
$null = $text.Item(1).AppendChild($template.CreateTextNode($Message))
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
# Windows PowerShell's registered AppUserModelID, so the toast is allowed without an installed app.
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
