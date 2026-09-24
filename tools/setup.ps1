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
#   4. включает хук commit-msg, который не пропускает в сообщение коммита
#      название проектируемого изделия, и заводит локальный стоп-лист
#      tools\stoplist.txt (он в .gitignore и в репозиторий не попадает);
#   5. проверяет Python, его разрядность и pywin32.
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

# --- 3. хук на текст коммита -----------------------------------------------
# Хук лежит в репозитории и включается через core.hooksPath, а не копируется
# в .git\hooks: так он приезжает на все машины вместе с набором.
if (Get-Command git -ErrorAction SilentlyContinue) {
    Push-Location $root
    git config core.hooksPath tools/hooks
    Pop-Location
    Write-Host "OK   core.hooksPath = tools/hooks (проверка текста коммита)"
    Write-Host "     папку текущего проекта можно добавить к стоп-словам:"
    Write-Host "     git config swkit.project '<путь к папке проекта>'"
} else {
    Write-Host "НЕТ  git не найден — хук commit-msg не включён"
}

# Стоп-лист локальный: лежавший в репозитории сам публиковал названия,
# которые должен был скрывать. Без BOM — Python читает его как UTF-8.
$stop = Join-Path $root "tools\stoplist.txt"
if (-not (Test-Path $stop)) {
    $text = "# Стоп-слова: названия и приметы изделий этой машины.`r`n" +
            "# Файл ЛОКАЛЬНЫЙ: он в .gitignore и в репозиторий не попадает.`r`n" +
            "# Строка = подстрока, регистр не важен; # — комментарий.`r`n"
    [IO.File]::WriteAllText($stop, $text, (New-Object Text.UTF8Encoding $false))
    Write-Host "OK   заведён tools\stoplist.txt — впишите туда изделие до первого коммита"
} else {
    Write-Host "OK   tools\stoplist.txt на месте (локальный, в .gitignore)"
}

# --- 4. Python -------------------------------------------------------------
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

# Вывод python перенаправляется, поэтому на время проверки снимаем Stop:
# в Windows PowerShell 5.1 stderr нативной программы при $ErrorActionPreference
# = Stop превращается в терминирующую ошибку, и скрипт падает вместо установки.
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $py -c "import win32com.client" 2>&1 | Out-Null
$hasPywin32 = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev

if (-not $hasPywin32) {
    Write-Host "     pywin32 не установлен — ставлю"
    & $py -m pip install --quiet pywin32
}
Write-Host "OK   pywin32 на месте"

# --- 5. проверка библиотеки ------------------------------------------------
& $py -c "import sys; sys.path.insert(0, r'$root'); import swkit; print('OK   swkit', swkit.__version__)"

Write-Host ""
Write-Host "Готово. Перезапустите Claude Code, чтобы он увидел скилл /solidworks."
Write-Host "Запуск скриптов: & '$py' скрипт.py"
