# -*- coding: utf-8 -*-
"""Виды и снимки экрана — визуальный контроль модели.

Зачем это нужно отдельным модулем: числовая проверка габаритов НЕ отвечает
на вопрос «похоже ли это на то, что задумано». Модель кузова автомобиля
может пройти все числовые проверки, будучи сплошным клиновидным бруском:
габарит совпадёт с прототипом точно, а узнаваемости не будет никакой —
её дают арки, сужение в плане, завал бортов и остекление, и ни одно из
этих свойств габаритом не измеряется.

Правило: после каждого этапа построения снимайте виды и СМОТРИТЕ на них.
"""
import os

import pythoncom
from win32com.client import VARIANT

from .conn import byref, call, prop

# swStandardViews_e
STD = {
    "front": 1,     # спереди
    "back": 2,      # сзади
    "left": 3,      # слева
    "right": 4,     # справа
    "top": 5,       # сверху
    "bottom": 6,    # снизу
    "iso": 7,       # изометрия
    "trimetric": 8,
    "dimetric": 9,
}

#: Именованные виды для ShowNamedView2. Русские имена работают на русской
#: установке, звёздочка означает стандартный вид.
NAMED_RU = {
    "front": "*Спереди", "back": "*Сзади", "left": "*Слева",
    "right": "*Справа", "top": "*Сверху", "bottom": "*Снизу",
    "iso": "*Изометрия",
}


def named_view(doc, view):
    """Поставить стандартный вид. view — ключ из STD или число.

    ShowNamedView2("", N) с числовым кодом не зависит от языка интерфейса
    и предпочтительнее передачи русского имени.
    """
    code = STD.get(view, view) if isinstance(view, str) else view
    doc.ShowNamedView2("", code)
    call(doc, "ViewZoomtofit2")
    call(doc, "GraphicsRedraw2")


def _norm(v):
    import math
    L = math.sqrt(sum(c * c for c in v))
    return [c / L for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def set_view(sw, doc, up, normal):
    """Задать ориентацию вида ЯВНО через вектор «вверх» и вектор на зрителя.

    Нужно, когда «вверх» в модели — не Y. Стандартная изометрия SolidWorks
    предполагает вверх = Y; в автомобильной системе координат вверх = Z, и
    штатная изометрия показывает машину лежащей на боку.

    IModelView::Orientation3 хранит матрицу ПО СТОЛБЦАМ; её строки — оси
    вида (вправо, вверх, на зрителя), выраженные в системе модели.
    """
    n = _norm(normal)
    d = sum(u * c for u, c in zip(up, n))
    u = _norm([up[i] - d * n[i] for i in range(3)])
    r = _cross(u, n)
    data = [r[0], u[0], n[0],
            r[1], u[1], n[1],
            r[2], u[2], n[2],
            0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    mu = prop(sw, "GetMathUtility")
    try:
        mu._FlagAsMethod("CreateTransform")
    except Exception:
        pass
    arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x) for x in data])
    doc.ActiveView.Orientation3 = mu.CreateTransform(arr)
    call(doc, "ViewZoomtofit2")
    call(doc, "GraphicsRedraw2")


#: Готовый набор видов для модели, у которой вверх = Z.
#: Пример: автомобиль, X назад, Y влево, Z вверх.
VIEWS_Z_UP = {
    "sboku":   dict(up=(0, 0, 1), normal=(0, -1, 0)),
    "speredi": dict(up=(0, 0, 1), normal=(-1, 0, 0)),
    "szadi":   dict(up=(0, 0, 1), normal=(1, 0, 0)),
    "sverhu":  dict(up=(-1, 0, 0), normal=(0, 0, 1)),
    "3_4_perednyaya": dict(up=(0, 0, 1), normal=(-0.55, -0.70, 0.45)),
    "3_4_zadnyaya":   dict(up=(0, 0, 1), normal=(0.60, -0.68, 0.42)),
}


def shaded(doc, with_edges=False):
    """Затенённый режим отображения — для снимков."""
    if with_edges:
        call(doc, "ViewDisplayShaderewithedges")
    else:
        call(doc, "ViewDisplayShaded")


def shot(doc, path, view=None, sw=None, up=None, normal=None):
    """Сохранить снимок экрана в PNG.

    Ориентация задаётся либо стандартным видом (view), либо явно (up+normal,
    тогда нужен и sw). Размер снимка определяется размером окна SolidWorks —
    разверните окно перед съёмкой, если нужна детализация.

    Снимок делается через SaveAs с расширением .png: это захват графической
    области, поэтому SolidWorks обязан быть видимым и не под заблокированным
    сеансом RDP.
    """
    if up is not None and normal is not None:
        if sw is None:
            raise ValueError("для явной ориентации нужен аргумент sw")
        set_view(sw, doc, up, normal)
    elif view is not None:
        named_view(doc, view)

    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # флаг 2 = копия: снимок не должен переименовывать модель
    for fn in (lambda: doc.SaveAs3(path, 0, 2),
               lambda: doc.Extension.SaveAs(path, 0, 2, None, byref(), byref()),
               lambda: doc.SaveAs2(path, 0, True, False)):
        try:
            fn()
            if os.path.exists(path):
                return path
        except Exception:
            pass
    raise RuntimeError("не удалось снять вид: " + path)


def shot_set(doc, out_dir, prefix, views=("iso", "front", "right", "top")):
    """Снять набор стандартных видов. Возвращает список путей."""
    out = []
    for v in views:
        out.append(shot(doc, os.path.join(out_dir, "%s_%s.png" % (prefix, v)), view=v))
    return out


def shot_set_z_up(sw, doc, out_dir, prefix, views=None):
    """Снять набор видов для модели с вертикалью Z."""
    names = views or list(VIEWS_Z_UP)
    out = []
    for name in names:
        cfg = VIEWS_Z_UP[name]
        out.append(shot(doc, os.path.join(out_dir, "%s_%s.png" % (prefix, name)),
                        sw=sw, up=cfg["up"], normal=cfg["normal"]))
    return out
