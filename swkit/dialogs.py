# -*- coding: utf-8 -*-
"""Сторож модальных окон SolidWorks.

Аддины (в первую очередь SOLIDWORKS CAM) при перестроении модели показывают
предупреждения. Модальное окно останавливает COM-вызов, и скрипт зависает
НАВСЕГДА — снаружи это выглядит как бесконечное построение, и отличить его
от тяжёлой геометрии невозможно.

Это самая дорогая из известных ошибок: она не даёт ни исключения, ни
диагностики, а ждать бесполезно.

Сторож крутится в фоновом потоке и закрывает такие окна по заголовку.
Главное окно SolidWorks не трогает.
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import threading
import time

user32 = ctypes.windll.user32
WM_CLOSE = 0x0010

#: Заголовки окон, которые нужно закрывать. Сравнение по вхождению подстроки,
#: без учёта регистра. Пополняйте список, встретив новое мешающее окно, —
#: и добавляйте запись в knowledge/30_ГРАБЛИ.
NUISANCE = (
    "cam", "предупреждение", "warning", "what's new", "welcome",
    "добро пожаловать", "sustainability", "советы", "tip of the day",
    "обновление", "update available",
)

_EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _pid(hwnd):
    p = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def sweep(sw_pid, main_hwnd=None):
    """Закрыть мешающие окна один раз. Возвращает список закрытых заголовков."""
    closed = []

    def cb(hwnd, _):
        if _pid(hwnd) != sw_pid or not user32.IsWindowVisible(hwnd):
            return True
        if main_hwnd and hwnd == main_hwnd:
            return True
        t = _title(hwnd)
        if not t or t.startswith("SOLIDWORKS Premium") or t.startswith("SOLIDWORKS 20"):
            return True
        low = t.lower()
        if any(k in low for k in NUISANCE):
            user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
            closed.append(t)
        return True

    user32.EnumWindows(_EnumProc(cb), 0)
    return closed


def start(sw_pid, period=1.0, verbose=False):
    """Запустить сторож фоновым демон-потоком. Возвращает поток."""
    def loop():
        while True:
            try:
                for t in sweep(sw_pid):
                    if verbose:
                        print("    [сторож] закрыто окно: " + t)
            except Exception:
                pass
            time.sleep(period)

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th


def solidworks_pid():
    """PID процесса SLDWORKS.exe, или None."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].lower().startswith("sldworks"):
                return int(parts[1])
    except Exception:
        pass
    return None
