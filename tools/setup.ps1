# Установка SolidWorks-Kit на машине.
#
# Запускать из любого места после клонирования репозитория:
#     powershell -ExecutionPolicy Bypass -File tools\setup.ps1
#
# Что делает:
#   1. находит корень набора (папку, где лежит этот скрипт, на уровень выше);
#   2. создаёт junction ~\.claude\skills\solidworks -> <корень>\skill,
#      чтобы скилл подхватывался Claude Code из любого каталога;
#   3. прописывает переменную SWKIT_HOME в профиль пользователя;
#   4. проверяет Python, его разрядность и pywin32.
#
# Прав администратора не требует: junction (mklink /J) создаётся без них,
# в отличие от символической ссылки.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Write-Host "Корень набора: $root"

if (-not (Test-Path (Join-Path $root "swkit"))) {
    throw "В $root нет папки swkit — скрипт запущен не из репозитория."
}

# --- 1. junction для скилла ------------------------------------------------
$skills = Join-Path $env:USERPROFILE ".claude\skills"
if (-not (Test-Path $skills)) {
    New-Item -ItemType Directory -Path $skills -Force | Out-Null
}
$link = Join-Path $skills "solidworks"
$target = Join-Path $root "skill"

if (Test-Path $link) {
    $item = Get-Item $link -Force
    $current = $null
    if ($item.LinkType) { $current = $item.Target | Select-Object -First 1 }
    if ($current -eq $target) {
        Write-Host "OK   junction уже указывает куда нужно"
    } else {
        Write-Host "     junction ведёт в другое место ($current) — пересоздаю"
        if ($item.LinkType) {
            cmd /c rmdir "$link" | Out-Null
        } else {
            throw "$link — обычная папка, а не ссылка. Уберите её вручную и повторите."
        }
        cmd /c mklink /J "$link" "$target" | Out-Null
        Write-Host "OK   junction создан"
    }
} else {
    cmd /c mklink /J "$link" "$target" | Out-Null
    Write-Host "OK   junction создан: $link -> $target"
}

# --- 2. SWKIT_HOME ---------------------------------------------------------
# Нужна скриптам проектов, чтобы находить библиотеку независимо от того,
# куда склонирован репозиторий.
[Environment]::SetEnvironmentVariable("SWKIT_HOME", $root, "User")
$env:SWKIT_HOME = $root
Write-Host "OK   SWKIT_HOME = $root (в новых консолях подхватится сам)"

# --- 3. Python -------------------------------------------------------------
$py = $null
foreach ($c in @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
    if (Test-Path $c) { $py = $c; break }
}
if (-not $py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
}

if (-not $py) {
    Write-Host "НЕТ  Python не найден."
    Write-Host "     winget install --id Python.Python.3.13 --scope user --silent"
    exit 1
}

Write-Host "OK   Python: $py"
$arch = & $py -c "import platform; print(platform.architecture()[0])"
if ($arch -ne "64bit") {
    Write-Host "НЕТ  Python $arch — нужен 64bit, иначе COM-объект SolidWorks недоступен."
    exit 1
}
Write-Host "OK   разрядность: 64bit"

& $py -c "import win32com.client" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "     pywin32 не установлен — ставлю"
    & $py -m pip install --quiet pywin32
}
Write-Host "OK   pywin32 на месте"

# --- 4. проверка библиотеки ------------------------------------------------
& $py -c "import sys; sys.path.insert(0, r'$root'); import swkit; print('OK   swkit', swkit.__version__)"

Write-Host ""
Write-Host "Готово. Перезапустите Claude Code, чтобы он увидел скилл /solidworks."
Write-Host "Запуск скриптов: & '$py' скрипт.py"
