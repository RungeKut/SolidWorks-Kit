@echo off
rem Установка SolidWorks-Kit двойным щелчком.
rem
rem Обёртка над tools\setup.ps1: политика выполнения снимается только для
rem этого запуска, путь к скрипту берётся рядом с собой, а окно не закрывается,
rem пока сообщения не прочитаны. Прав администратора не требует.
rem
rem Все сообщения печатает сам setup.ps1: PowerShell выводит юникод в консоль
rem независимо от кодовой страницы. Здесь echo только латиницей — cmd читает
rem этот файл в текущей кодовой странице, и русский текст рассыпался бы то на
rem одной машине, то на другой.

setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup.ps1"
set RC=%ERRORLEVEL%

if not %RC% equ 0 (
    echo.
    echo SETUP FAILED, exit code %RC% -- see the message above.
)
echo.
pause
endlocal & exit /b %RC%