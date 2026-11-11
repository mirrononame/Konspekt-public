@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Konspekt.lnk');" ^
  "$s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0start-hidden.vbs\"'; $s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%~dp0konspekt.ico,0'; $s.Description='Konspekt'; $s.Save()"
echo  Ярлик "Konspekt" створено на робочому столі.
set /p A=Запускати "Конспект" автоматично під час входу в Windows? (y/n): 
if /i "%A%"=="y" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Konspekt.lnk');" ^
    "$s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0start-hidden.vbs\" --no-browser'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0konspekt.ico,0'; $s.Save()"
  echo  Автозапуск увімкнено. Вимкнути: видаліть Konspekt з папки shell:startup
)
pause
