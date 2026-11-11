' Запуск "Конспекту" без чорного вікна. Вимкнути: Налаштування -> Вимкнути сервер.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
args = ""
For Each a In WScript.Arguments
  args = args & " " & a
Next
sh.CurrentDirectory = dir
If Not fso.FileExists(dir & "\.venv\Scripts\pythonw.exe") Then
  ' перший запуск — потрібне вікно, щоб показати встановлення
  sh.Run """" & dir & "\start.bat""" & args, 1, False
Else
  sh.Environment("PROCESS")("PYTHONUTF8") = "1"
  sh.Run """" & dir & "\.venv\Scripts\pythonw.exe"" -m app.server" & args, 0, False
End If
