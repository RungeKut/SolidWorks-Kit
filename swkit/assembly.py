# -*- coding: utf-8 -*-
"""Сборки: вставка компонентов, расстановка, сопряжения.

Есть ТРИ способа поставить компонент на место. Здесь собраны все три,
потому что каждый нужен в своём случае:

1. by_coordinates()  — вставить по координатам, компонент остаётся
   зафиксированным. Быстро и детерминированно, но связей нет: при правке
   детали ничего не пересчитается. Годится для моделей внешнего вида.

2. by_transform()    — вставить и применить матрицу поворота и переноса.
   Нужен, когда деталь смоделирована в своей ориентации, а в сборке стоит
   повёрнутой.

3. by_origin_mates() — вставить в начало координат и связать тремя
   совпадениями базовых плоскостей с плоскостями сборки. Компонент получает
   статус «полностью определён», сборка перестраивается без предупреждений.
   Требует, чтобы деталь была смоделирована СРАЗУ в координатах сборки.

Правило выбора: если детали моделируются скриптом — всегда 3 (моделируйте
в координатах сборки). Если деталь пришла со стороны или повёрнута — 2.
1 — только для быстрых визуальных макетов.
"""
import math
import os

import pythoncom
from win32com.client import VARIANT

from .conn import (DOC_ASM, DOC_PART, NULL_DISPATCH, activate, byref, call,
                   open_doc, prop, select)
from .part import base_planes, bbox_centre_mm, find_template, save_as
from .units import m

# swAddComponentConfigOptions_e
CONFIG_CURRENT = 0

# swMateType_e
COINCIDENT = 0
CONCENTRIC = 1
PERPENDICULAR = 2
PARALLEL = 3
TANGENT = 4
DISTANCE = 5
ANGLE = 6

# swMateAlign_e
ALIGNED = 0
ANTI_ALIGNED = 1
CLOSEST = 2

# swComponentConstrainedStatus_e — что возвращает GetConstrainedStatus().
#
# ВНИМАНИЕ: коды 2 и 3 часто путают, и в разных справочниках они указаны
# по-разному. Проверено опытом 20.09.2026 на этой установке (2025 SP04):
#   компонент вставлен и зафиксирован          -> 3
#   фиксация снята, сопряжений нет (свободен)  -> 2
#   фиксация снята, 3 совпадения плоскостей    -> 3
# То есть 3 = ПОЛНОСТЬЮ ОПРЕДЕЛЁН, 2 = НЕДООПРЕДЕЛЁН.
# Коды 0, 1, 4 на этой установке воспроизвести не удалось — приведены по
# документации и НЕ проверены.
STATUS = {
    0: "неизвестно (не проверено)",
    1: "переопределён (не проверено)",
    2: "недоопределён",
    3: "полностью определён",
    4: "нет решения (не проверено)",
}
FULLY_DEFINED = 3
UNDER_DEFINED = 2


def new_assembly(sw, template=None):
    """Новый документ сборки."""
    tpl = template or find_template(sw, "assembly")
    doc = sw.NewDocument(tpl, 0, 0, 0)
    if doc is None:
        doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("NewDocument вернул None для шаблона " + tpl)
    return doc


def assembly_name(path):
    """Имя сборки без расширения — нужно для адресации SelectByID2."""
    return os.path.splitext(os.path.basename(path))[0]


def plane_names(doc):
    """Имена базовых плоскостей документа в порядке дерева."""
    return [prop(p, "Name") for p in base_planes(doc)]


# ==========================================================================
# вставка компонентов
# ==========================================================================

def _add(asm, path, x=0.0, y=0.0, z=0.0):
    # AddComponent5 — член IAssemblyDoc, а не IModelDoc2. При позднем
    # связывании его нет в дефолтном dispatch: обычное обращение даёт
    # AttributeError. call() помечает имя как метод через _FlagAsMethod.
    comp = call(asm, "AddComponent5", path, CONFIG_CURRENT, "", False, "",
                m(x), m(y), m(z))
    if comp is None:
        raise RuntimeError("AddComponent5 не вставил компонент: " + path)
    return comp


def preload(sw, asm_path, part_paths):
    """Открыть детали перед вставкой и вернуть активной сборку.

    AddComponent5 берёт только тот документ, который SolidWorks УЖЕ загрузил.
    Без предварительного OpenDoc он молча возвращает None.
    """
    for p in part_paths:
        open_doc(sw, p, DOC_PART)
    activate(sw, asm_path)


def by_coordinates(sw, asm, path, x=0.0, y=0.0, z=0.0, compensate_bbox=True):
    """Способ 1: вставить так, чтобы НАЧАЛО КООРДИНАТ детали легло в (x, y, z).

    compensate_bbox=True — обязательно, если деталь смоделирована не вокруг
    своего начала координат: AddComponent5 ставит компонент ЦЕНТРОМ
    ГАБАРИТНОГО ЯЩИКА, а не началом координат. Разница и есть смещение,
    которое здесь добавляется обратно.
    """
    dx = dy = dz = 0.0
    if compensate_bbox:
        doc = open_doc(sw, path, DOC_PART)
        dx, dy, dz = bbox_centre_mm(doc)
        activate(sw, prop(asm, "GetPathName") or "")
    return _add(asm, path, x + dx, y + dy, z + dz)


def by_transform(sw, asm, path, rotation=None, translation=(0.0, 0.0, 0.0)):
    """Способ 2: вставить и задать положение матрицей 3x3 + переносом (мм).

    rotation — список из трёх строк по три числа, или None (без поворота).
    Матрица SolidWorks хранится 16 числами: 9 — поворот ПО СТОЛБЦАМ,
    3 — перенос в метрах, затем масштаб 1.0 и три нуля.
    """
    comp = _add(asm, path, 0, 0, 0)
    R = rotation or [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    t = translation
    data = [R[0][0], R[1][0], R[2][0],
            R[0][1], R[1][1], R[2][1],
            R[0][2], R[1][2], R[2][2],
            m(t[0]), m(t[1]), m(t[2]),
            1.0, 0.0, 0.0, 0.0]
    mu = prop(sw, "GetMathUtility")
    try:
        mu._FlagAsMethod("CreateTransform")
    except Exception:
        pass
    arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in data])
    comp.Transform2 = mu.CreateTransform(arr)
    return comp


def by_origin_mates(sw, asm, asm_doc_path, path, unfix=True):
    """Способ 3: вставить в начало координат и связать тремя совпадениями.

    Деталь должна быть смоделирована СРАЗУ в координатах сборки — тогда
    совпадение одноимённых базовых плоскостей ставит её точно на место
    и делает полностью определённой.

    Возвращает (компонент, число_сопряжений, число_ошибок).
    """
    comp = _add(asm, path, 0, 0, 0)
    name = prop(comp, "Name2")
    aname = assembly_name(asm_doc_path)
    if unfix:
        asm.ClearSelection2(True)
        # компонент адресуется как "Имя-1@Сборка"; без суффикса не находится
        if not select(asm, "%s@%s" % (name, aname), "COMPONENT"):
            print("  !! не выбран компонент %s@%s для снятия фиксации"
                  % (name, aname))
        call(asm, "UnfixComponent")
        asm.ClearSelection2(True)
    ok, bad = mate_origin_planes(asm, asm_doc_path, name)
    return comp, ok, bad


# ==========================================================================
# сопряжения
# ==========================================================================

def mate_origin_planes(asm, asm_doc_path, comp_name):
    """Три совпадения базовых плоскостей компонента с плоскостями сборки.

    Имена плоскостей у детали и сборки совпадают, потому что берутся из
    одного шаблона. Адресация в сборке: "Плоскость@Компонент-1@Сборка".
    """
    aname = assembly_name(asm_doc_path)
    planes = plane_names(asm)
    ok = bad = 0
    for pln in planes:
        asm.ClearSelection2(True)
        s1 = select(asm, "%s@%s@%s" % (pln, comp_name, aname),
                    "PLANE", append=True, mark=1)
        s2 = select(asm, pln, "PLANE", append=True, mark=1)
        if not (s1 and s2):
            print("  !! не выбрано %s@%s (%s, %s)" % (pln, comp_name, s1, s2))
            bad += 1
            continue
        res = call(asm, "AddMate5", COINCIDENT, ALIGNED, False, 0, 0, 0,
                   0, 0, 0, 0, 0, False, False, 0, byref())
        mate = res[0] if isinstance(res, tuple) else res
        if mate is None:
            print("  !! сопряжение %s@%s не создано" % (pln, comp_name))
            bad += 1
        else:
            ok += 1
        asm.ClearSelection2(True)
    return ok, bad


# ==========================================================================
# матрицы поворота
# ==========================================================================

def rx(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mul(a, b):
    """Произведение матриц 3x3."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


# ==========================================================================
# состояние сборки
# ==========================================================================

def components(asm, top_level_only=True):
    """Список компонентов сборки."""
    c = call(asm, "GetComponents", top_level_only)
    return list(c) if c else []


def status_report(asm):
    """Сводка по статусам компонентов: {'полностью определён': 30, ...}.

    Главная проверка сборки. Недоопределённые компоненты уедут при первом
    же перестроении — модель, которая выглядит правильно сегодня, завтра
    развалится.
    """
    from collections import Counter
    cnt = Counter(prop(c, "GetConstrainedStatus") for c in components(asm))
    return {STATUS.get(k, "код %s" % k): v for k, v in cnt.items()}


def check_interference(asm):
    """Список пересечений компонентов: [(имя1, имя2, объём_мм3), ...].

    Возвращает:
        []      — пересечений нет;
        [...]   — найденные пересечения;
        None    — ПРОВЕРКА НЕДОСТУПНА на этой установке.

    Состояние на 20.09.2026, SolidWorks 2025 SP04, проверено опытом:
    штатный путь IModelDocExtension::CreateInterferenceDetectionManager
    здесь не работает ни при позднем связывании («Неизвестное имя»), ни при
    раннем — метода нет и в сгенерированной типовой библиотеке. Интерфейс
    IInterferenceDetectionMgr в библиотеке присутствует, но фабрики к нему
    нет. Запасной путь IAssemblyDoc::ToolsCheckInterference2(0, None, False)
    возвращает (None, None) и на заведомо пересекающейся сборке — то есть
    тоже не даёт результата.

    Поэтому функция честно сообщает о недоступности, а не возвращает пустой
    список: пустой список означал бы «пересечений нет», и сборка с грубой
    ошибкой прошла бы проверку молча.

    Обходной путь на сегодня: сверять объём сборки с суммой объёмов
    компонентов. Если детали пересекаются, объём сборки окажется МЕНЬШЕ
    суммы — см. check_volume_additive().
    """
    ext = asm.Extension
    try:
        mgr = call(ext, "CreateInterferenceDetectionManager")
    except Exception:
        return None
    if mgr is None:
        return None
    try:
        mgr.TreatCoincidenceAsInterference = False
        mgr.IncludeMultibodyPartInterferences = True
        res = call(mgr, "GetInterferences")
    except Exception:
        return None
    out = []
    for i in (res or []):
        comps = prop(i, "Components")
        names = [prop(c, "Name2") for c in (comps or [])]
        out.append((names[0] if names else "?",
                    names[1] if len(names) > 1 else "?",
                    prop(i, "Volume") * 1e9))
    return out


def check_volume_additive(sw, asm, part_paths, tol_rel=1e-6):
    """Косвенная проверка на пересечения: объём сборки против суммы деталей.

    Пересекающиеся тела считаются в сборке один раз, поэтому объём сборки
    оказывается МЕНЬШЕ суммы объёмов компонентов. Работает как замена
    недоступному детектору пересечений (см. check_interference).

    Возвращает (объём_сборки_мм3, сумма_объёмов_мм3, совпало_ли).
    Внимание: сравнивать надо с учётом КРАТНОСТИ компонентов — если одна
    деталь вставлена четырежды (колёса), передайте её путь четыре раза.
    """
    from .part import mass_properties
    from .conn import open_doc, close, activate
    asm_path = prop(asm, "GetPathName")
    v_asm = mass_properties(asm)["volume"] * 1e9
    total = 0.0
    for p in part_paths:
        d = open_doc(sw, p, DOC_PART)
        total += mass_properties(d)["volume"] * 1e9
        close(sw, d)
    if asm_path:
        activate(sw, asm_path)
    ok = abs(v_asm - total) <= max(total * tol_rel, 1.0)
    return v_asm, total, ok


def rebuild(asm, force=False):
    """Перестроить сборку."""
    if force:
        return call(asm, "ForceRebuild3", False)
    return call(asm, "EditRebuild3")


def show(asm, comp_name, visible=True):
    """Показать или скрыть компонент по имени — для съёмки видов в разрезе."""
    asm.ClearSelection2(True)
    select(asm, comp_name, "COMPONENT")
    call(asm, "ShowComponent") if visible else call(asm, "HideComponent")
    asm.ClearSelection2(True)
