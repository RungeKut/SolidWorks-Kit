# -*- coding: utf-8 -*-
"""Построение деталей: шаблоны, плоскости, эскизы, вытяжки, вырезы, сохранение.

Все размеры на входе — в МИЛЛИМЕТРАХ, углы — в ГРАДУСАХ.
"""
import glob
import os

import pythoncom
from win32com.client import VARIANT

from .conn import byref, call, prop
from .units import DRAFT, m, rad

# --- swEndConditions_e ----------------------------------------------------
BLIND = 0            # на заданное расстояние
THROUGH_ALL = 1      # насквозь
UPTO_NEXT = 2        # до следующего
UPTO_VERTEX = 3      # до вершины
UPTO_SURFACE = 4     # до поверхности
OFFSET_FROM_SURFACE = 5
MIDPLANE = 6         # от средней поверхности
THROUGH_ALL_BOTH = 8  # насквозь в обе стороны

# --- swStartConditions_e --------------------------------------------------
START_SKETCH_PLANE = 0
START_SURFACE = 1
START_VERTEX = 2
START_OFFSET = 3     # смещение от плоскости эскиза

# --- swUserPreferenceStringValue_e ----------------------------------------
SW_TEMPLATE_PART = 8
SW_TEMPLATE_ASSEMBLY = 9
SW_TEMPLATE_DRAWING = 10


# ==========================================================================
# шаблоны
# ==========================================================================

def find_template(sw, kind="part"):
    """Путь к шаблону документа.

    Сначала спрашиваем настройку SolidWorks, потом ищем на диске.
    Настройка шаблона по умолчанию бывает ПУСТОЙ на свежей установке —
    NewDocument с пустым путём возвращает None без внятной ошибки.

    Предпочитается ГОСТ-шаблон, MBD-шаблоны идут последними: они настроены
    под мелкие детали и дают неудобные виды на крупной модели.
    """
    pref = {"part": SW_TEMPLATE_PART,
            "assembly": SW_TEMPLATE_ASSEMBLY,
            "drawing": SW_TEMPLATE_DRAWING}[kind]
    ext = {"part": "prtdot", "assembly": "asmdot", "drawing": "drwdot"}[kind]
    try:
        tpl = sw.GetUserPreferenceStringValue(pref)
        if tpl and os.path.isfile(tpl):
            return tpl
    except Exception:
        pass
    cands = []
    for pat in (r"C:\ProgramData\SolidWorks\**\*." + ext,
                r"C:\Program Files\SOLIDWORKS*\**\*." + ext):
        cands += glob.glob(pat, recursive=True)
    if not cands:
        raise RuntimeError("шаблон *.%s не найден ни в настройках, ни на диске" % ext)

    def rank(p):
        base = os.path.basename(p).lower()
        return (0 if "gost" in base else 1,
                1 if (os.sep + "MBD" + os.sep) in p else 0,
                len(p))

    return sorted(set(cands), key=rank)[0]


def new_part(sw, template=None):
    """Новый документ детали."""
    tpl = template or find_template(sw, "part")
    doc = sw.NewDocument(tpl, 0, 0, 0)
    if doc is None:
        doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("NewDocument вернул None для шаблона " + tpl)
    return doc


# ==========================================================================
# плоскости и дерево построения
# ==========================================================================

def features(doc, type_name=None):
    """Список объектов дерева построения, при желании — только заданного типа.

    Типы: 'RefPlane', 'ProfileFeature' (эскиз), 'Extrusion', 'Cut', 'RefAxis'.
    """
    out = []
    f = prop(doc, "FirstFeature")
    while f is not None:
        if type_name is None or prop(f, "GetTypeName2") == type_name:
            out.append(f)
        f = prop(f, "GetNextFeature")
    return out


def feature_names(doc, type_name=None):
    """Имена объектов дерева — для диагностики и отладки."""
    return [prop(f, "Name") for f in features(doc, type_name)]


def base_planes(doc):
    """Три базовые плоскости В ПОРЯДКЕ ДЕРЕВА: [Спереди, Сверху, Справа].

    Обращаться по индексу, а НЕ по имени: имена зависят от языка интерфейса
    (Спереди / Front / Vorne) и от шаблона. Скрипт, который ищет плоскость
    "Спереди", молча ломается на англоязычной установке.
    """
    return features(doc, "RefPlane")[:3]


FRONT, TOP, RIGHT = 0, 1, 2     # индексы в base_planes()


def select_plane(doc, index):
    """Выбрать базовую плоскость по индексу: 0 Спереди, 1 Сверху, 2 Справа."""
    doc.ClearSelection2(True)
    planes = base_planes(doc)
    if index >= len(planes):
        raise RuntimeError("базовая плоскость #%d не найдена" % index)
    call(planes[index], "Select2", False, 0)
    return planes[index]


def last_feature(doc):
    """Последний созданный объект дерева (эскиз сразу после закрытия и т.п.)."""
    return doc.FeatureByPositionReverse(0)


# ==========================================================================
# эскизы
# ==========================================================================

class Sketch:
    """Контекст эскиза. Координаты — в мм, в системе плоскости эскиза.

        with Sketch(doc, part.TOP) as sk:
            sk.rect(0, 0, 1000, 500)
        extrude(doc, sk.feature, 200)
    """

    def __init__(self, doc, plane_index=FRONT, plane=None):
        self.doc = doc
        self.plane_index = plane_index
        self.plane = plane
        self.feature = None

    def __enter__(self):
        if self.plane is not None:
            self.doc.ClearSelection2(True)
            call(self.plane, "Select2", False, 0)
        else:
            select_plane(self.doc, self.plane_index)
        self.doc.SketchManager.InsertSketch(True)
        return self

    def __exit__(self, *exc):
        self.doc.SketchManager.InsertSketch(True)
        self.doc.ClearSelection2(True)
        self.feature = last_feature(self.doc)
        return False

    @property
    def sm(self):
        return self.doc.SketchManager

    def line(self, x1, y1, x2, y2):
        return self.sm.CreateLine(m(x1), m(y1), 0.0, m(x2), m(y2), 0.0)

    def rect(self, x1, y1, x2, y2):
        """Прямоугольник по двум противоположным углам."""
        return self.sm.CreateCornerRectangle(m(x1), m(y1), 0.0, m(x2), m(y2), 0.0)

    def circle(self, x, y, d):
        """Окружность по ДИАМЕТРУ (API принимает радиус — перевод внутри)."""
        return self.sm.CreateCircleByRadius(m(x), m(y), 0.0, m(d / 2.0))

    def poly(self, pts, close=True):
        """Контур по списку точек [(x, y), ...].

        Контур ОБЯЗАН быть замкнут, иначе вытяжка вернёт None без объяснения.
        """
        n = len(pts)
        last = n if close else n - 1
        for i in range(last):
            a, b = pts[i], pts[(i + 1) % n]
            self.line(a[0], a[1], b[0], b[1])

    def polys(self, polygons):
        """Несколько контуров сразу: внешний + внутренние (отверстия)."""
        for p in polygons:
            self.poly(p)

    def arc(self, cx, cy, x1, y1, x2, y2, direction=1):
        return self.sm.CreateArc(m(cx), m(cy), 0.0, m(x1), m(y1), 0.0,
                                 m(x2), m(y2), 0.0, direction)

    def centerline(self, x1, y1, x2, y2):
        return self.sm.CreateCenterLine(m(x1), m(y1), 0.0, m(x2), m(y2), 0.0)


def sketch_on(doc, plane_index, draw):
    """Функциональная форма: sketch_on(doc, part.TOP, lambda sk: sk.rect(...))."""
    with Sketch(doc, plane_index) as sk:
        draw(sk)
    return sk.feature


# ==========================================================================
# вытяжки и вырезы
# ==========================================================================

def extrude(doc, sketch=None, depth=0.0, end=BLIND, reverse=False,
            merge=True, start_offset=0.0, flip_start=False, depth2=0.0,
            both=False, draft=0.0, draft_outward=True):
    """Вытяжка выбранного (или переданного) эскиза.

    depth        — глубина, мм
    end          — условие окончания: BLIND, MIDPLANE, THROUGH_ALL
    reverse      — в обратную сторону от плоскости эскиза
    start_offset — начать не от плоскости эскиза, а со смещением, мм
    both         — две глухие стороны по depth и depth2. Надёжная замена
                   MIDPLANE при позднем связывании (см. 30_ГРАБЛИ/30-03)
    draft        — угол уклона, градусы. Уклон заметает грань, наклонную к
                   плоскости эскиза (см. 20_ПРИЁМЫ/20-04)

    FeatureExtrusion3 принимает 23 позиционных аргумента в этом порядке.
    Проверено на SolidWorks 2025 SP04; менять местами нельзя.
    """
    doc.ClearSelection2(True)
    sk = sketch if sketch is not None else last_feature(doc)
    call(sk, "Select2", False, 0)

    t0 = START_OFFSET if start_offset else START_SKETCH_PLANE
    if both:
        sd, t1, t2 = False, BLIND, BLIND
        d1, d2 = m(depth), m(depth2 or depth)
    else:
        sd, t1, t2 = True, end, 0
        d1, d2 = m(depth), 0.0

    feat = doc.FeatureManager.FeatureExtrusion3(
        sd,                   # 1  sd: только одно направление
        False,                # 2  flip: обратить сторону материала
        reverse,              # 3  dir: обратное направление
        t1,                   # 4  t1: условие окончания, направление 1
        t2,                   # 5  t2: условие окончания, направление 2
        d1,                   # 6  d1: глубина 1, м
        d2,                   # 7  d2: глубина 2, м
        bool(draft), False,   # 8-9   dchk1/dchk2: уклон включён
        bool(draft_outward), False,   # 10-11 ddir1/ddir2: уклон наружу
        rad(draft) or DRAFT,  # 12 dang1: угол уклона 1, рад
        DRAFT,                # 13 dang2
        False, False,         # 14-15 offsetReverse1/2
        False, False,         # 16-17 translateSurface1/2
        merge,                # 18 merge: объединить с телом
        True,                 # 19 useFeatScope
        True,                 # 20 useAutoSelect
        t0,                   # 21 t0: начальное условие
        m(start_offset),      # 22 startOffset, м
        flip_start,           # 23 flipStartOffset
    )
    doc.ClearSelection2(True)
    if feat is None:
        raise RuntimeError(
            "FeatureExtrusion3 вернул None. Причины по частоте: "
            "контур эскиза не замкнут; эскиз самопересекается; "
            "глубина 0; выбран не эскиз, а другой объект дерева")
    return feat


def _cut_once(doc, sk, depth, end, reverse, start_offset, flip_start,
              both_directions, draft=0.0, draft_outward=True):
    doc.ClearSelection2(True)
    call(sk, "Select2", False, 0)

    t0 = START_OFFSET if start_offset else START_SKETCH_PLANE
    if both_directions:
        sd, t1, t2 = False, end, end
    else:
        sd, t1, t2 = True, end, 0

    feat = doc.FeatureManager.FeatureCut4(
        sd,                 # 1  sd: только одно направление
        False,              # 2  flip
        reverse,            # 3  dir
        t1,                 # 4  t1
        t2,                 # 5  t2
        m(depth),           # 6  d1
        m(depth),           # 7  d2
        bool(draft), False,           # 8-9   уклон включён
        bool(draft_outward), False,   # 10-11 уклон наружу
        rad(draft) or DRAFT, DRAFT,   # 12-13 углы уклона
        False, False,       # 14-15 offsetReverse
        False, False,       # 16-17 translateSurface
        False,              # 18 normalCut
        True,               # 19 useFeatScope
        True,               # 20 useAutoSelect
        True,               # 21 assemblyFeatureScope
        False,              # 22 autoSelectComponents
        False,              # 23 propagateFeatureToParts
        t0,                 # 24 t0
        m(start_offset),    # 25 startOffset
        flip_start,         # 26 flipStartOffset
        False,              # 27 optimizeGeometry
    )
    doc.ClearSelection2(True)
    return feat


def cut(doc, sketch=None, depth=0.0, end=THROUGH_ALL, reverse=True,
        start_offset=0.0, flip_start=False, both_directions=False,
        auto_direction=True, verbose=False, draft=0.0, draft_outward=True):
    """Вырез по эскизу.

    ВАЖНО: направление у выреза ПРОТИВОПОЛОЖНО вытяжке. Проверено опытом
    (см. knowledge/30_ГРАБЛИ/30-02): на плите, вытянутой из плоскости
    «Сверху» вверх, сквозной вырез из той же плоскости проходит только при
    reverse=True. Поэтому reverse=True здесь — ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ,
    в отличие от extrude().

    auto_direction=True — если вырез не прошёл, автоматически повторить с
    обратным направлением. Экономит итерации: угадать знак заранее нельзя,
    он зависит от того, с какой стороны плоскости эскиза лежит материал.
    Сработавшее направление печатается при verbose=True.

    both_directions=True — сквозной рез в обе стороны. Нужен, когда эскиз
    лежит в плоскости симметрии: односторонний рез прорежет только одну стенку.

    draft — угол уклона, градусы. Вырез с уклоном режет плоскостью, наклонной
    к плоскости эскиза: так делаются скосы, не перпендикулярные базовым
    плоскостям, без справочных плоскостей и лофтов (см. 20_ПРИЁМЫ/20-04).
    Сторону задаёт draft_outward; угадать её заранее нельзя, проверяйте
    объёмом до и после.

    FeatureCut4 в SolidWorks 2025 принимает 27 аргументов. Сигнатура из
    старой документации (26 аргументов) НЕ проходит.
    """
    sk = sketch if sketch is not None else last_feature(doc)

    feat = _cut_once(doc, sk, depth, end, reverse, start_offset, flip_start,
                     both_directions, draft, draft_outward)
    if feat is None and auto_direction:
        feat = _cut_once(doc, sk, depth, end, not reverse, start_offset,
                         flip_start, both_directions, draft, draft_outward)
        if feat is not None and verbose:
            print("    [cut] сработало обратное направление reverse=%s"
                  % (not reverse))

    if feat is None:
        raise RuntimeError(
            "FeatureCut4 вернул None в обоих направлениях. Причины: "
            "контур не замкнут; контур не пересекает тело; "
            "вырез съел бы деталь целиком; эскиз лежит в плоскости "
            "симметрии — тогда нужен both_directions=True")
    return feat


def revolve(doc, sketch=None, axis=None, angle=360.0):
    """Вращение эскиза вокруг оси (осевой линии в эскизе или базовой оси)."""
    doc.ClearSelection2(True)
    sk = sketch if sketch is not None else last_feature(doc)
    call(sk, "Select2", False, 0)
    if axis is not None:
        call(axis, "Select2", True, 4)
    feat = doc.FeatureManager.FeatureRevolve2(
        True, True, False, False, False, False, 0, 0,
        rad(angle), 0.0, False, False, 0.0, 0.0, 0.0, 0.0, 0.0,
        True, True, True)
    doc.ClearSelection2(True)
    if feat is None:
        raise RuntimeError("FeatureRevolve2 вернул None: нет оси или контур незамкнут")
    return feat


# ==========================================================================
# материалы и цвет
# ==========================================================================

def set_material(doc, database, name, config=None, expect_density=None):
    """Назначить материал из базы. database — полный путь к .sldmat.

    Два условия, нарушаемые легко:

    1. Материал назначается ПО ГОТОВОМУ ТЕЛУ. До первой вытяжки вызов молча
       не действует.
    2. SetMaterialPropertyName2 НЕ возвращает ошибку при несуществующем
       имени материала — он просто ничего не делает.

    Поэтому результат проверяется здесь же. Проверка идёт ПО ПЛОТНОСТИ, а не
    по имени: обратное чтение GetMaterialPropertyName2 при позднем
    связывании возвращает пустую строку (проверено 20.09.2026), а плотность
    — прямое подтверждение того, что материал реально применён.

    expect_density — ожидаемая плотность, кг/м3. Если не задана, берётся из
    swkit.materials.DENSITY по имени материала. Если и там нет, проверка
    пропускается с предупреждением: молча считать материал назначенным
    нельзя.
    """
    if config is None:
        cm = prop(doc, "ConfigurationManager")
        config = prop(prop(cm, "ActiveConfiguration"), "Name")

    # SetMaterialPropertyName2 — член IPartDoc; EditRebuild3 при позднем
    # связывании отдаётся значением, а не методом: оба идут через call().
    call(doc, "SetMaterialPropertyName2", config, database, name)
    call(doc, "EditRebuild3")

    if expect_density is None:
        from .materials import DENSITY
        expect_density = DENSITY.get(name)

    if expect_density is None:
        print("    материал %r назначен, но НЕ ПРОВЕРЕН: неизвестна "
              "ожидаемая плотность. Передайте expect_density." % name)
        return name

    got = mass_properties(doc)["density"]
    if abs(got - expect_density) > 1.0:
        raise RuntimeError(
            "материал %r не назначен: плотность %.1f вместо %.1f кг/м3. "
            "Проверьте, что имя точно совпадает с именем в базе %s и что "
            "тело уже построено" % (name, got, expect_density, database))
    return name


def set_color(doc, rgb, transparency=0.0, component=None):
    """Цвет детали или компонента сборки. rgb — тройка 0..1.

    Косметика: никогда не должна ронять построение.
    Порядок 9 чисел: R, G, B, ambient, diffuse, specular, shininess,
    transparency, emission.
    """
    target = component if component is not None else doc
    try:
        vals = [float(rgb[0]), float(rgb[1]), float(rgb[2]),
                1.0, 1.0, 0.35, 0.3, float(transparency), 0.0]
        target.MaterialPropertyValues = VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)
        return True
    except Exception as exc:
        print("цвет не задан (не критично):", exc)
        return False


# ==========================================================================
# сохранение
# ==========================================================================

#: swSaveAsOptions_e
SAVE_SILENT = 1      # без диалогов; документ ПЕРЕИМЕНОВЫВАЕТСЯ
SAVE_COPY = 2        # записать копию; документ остаётся под старым именем


def save_as(doc, path, overwrite=True, as_copy=False):
    """Сохранить документ под новым именем. Возвращает путь.

    as_copy=False (по умолчанию) — настоящее «Сохранить как»: открытый
    документ получает новое имя и путь. Именно это нужно для моделей.

    as_copy=True — записать копию, не трогая открытый документ. Нужно для
    экспорта (см. export.py).

    ГРАБЛИ: флаг options=2 — это swSaveAsOptions_Copy. Вызов
    SaveAs3(path, 0, 2) создаёт файл, но НЕ переименовывает документ:
    GetTitle остаётся «Сборка18», GetPathName — пустым. Дальше
    ActivateDoc3 по имени файла не находит документ, и сборка не собирается.
    Проверено 20.09.2026: флаги 0 и 1 переименовывают документ, флаг 2 —
    нет. Ошибка особенно коварна для деталей: там документ обычно сразу
    закрывается, имя роли не играет, и флаг 2 годами не выдаёт себя — пока
    тот же код не применят к сборке.

    Возвращаемое значение SaveAs3 НЕ является признаком успеха: оно равно 0
    и при успешной записи. Проверять надо существование файла.
    """
    opt = SAVE_COPY if as_copy else SAVE_SILENT
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if overwrite and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass   # файл держит открытый документ — SaveAs всё равно перезапишет

    errs = []
    attempts = (
        ("SaveAs3", lambda: doc.SaveAs3(path, 0, opt)),
        ("Extension.SaveAs", lambda: doc.Extension.SaveAs(
            path, 0, opt, None, byref(), byref())),
        ("SaveAs2", lambda: doc.SaveAs2(path, 0, True, False)),
        ("SaveAs", lambda: doc.SaveAs(path)),
    )
    for name, fn in attempts:
        try:
            fn()
            if os.path.exists(path):
                return path
        except Exception as e:
            errs.append("%s: %s" % (name, str(e)[:70]))
    raise RuntimeError("не удалось сохранить %s\n  %s" % (path, "\n  ".join(errs)))


# ==========================================================================
# измерения
# ==========================================================================

def bodies(doc):
    """Твёрдые тела документа детали."""
    b = doc.GetBodies2(0, True)
    return list(b) if b else []


def bbox_mm(doc):
    """Габаритный ящик ПЕРВОГО тела: [x1, y1, z1, x2, y2, z2] в мм."""
    bs = bodies(doc)
    if not bs:
        raise RuntimeError("в детали нет тел")
    return [round(c * 1000, 3) for c in prop(bs[0], "GetBodyBox")]


def bbox_union_mm(doc):
    """Габарит по ВСЕМ телам: (lo, hi), каждый — [x, y, z] в мм."""
    lo, hi = [1e12] * 3, [-1e12] * 3
    for b in bodies(doc):
        box = [c * 1000 for c in prop(b, "GetBodyBox")]
        for i in range(3):
            lo[i] = min(lo[i], box[i])
            hi[i] = max(hi[i], box[i + 3])
    if lo[0] > 1e11:
        raise RuntimeError("в документе нет тел")
    return lo, hi


def bbox_size_mm(doc):
    """Габаритные размеры (dx, dy, dz) в мм по всем телам."""
    lo, hi = bbox_union_mm(doc)
    return [hi[i] - lo[i] for i in range(3)]


def bbox_centre_mm(doc):
    """Центр габаритного ящика в мм. Нужен для AddComponent5 (см. assembly.py)."""
    lo, hi = bbox_union_mm(doc)
    return [(lo[i] + hi[i]) / 2.0 for i in range(3)]


def mass_properties(doc):
    """Словарь: mass (кг), volume (м3), density (кг/м3), area (м2), com (мм)."""
    # CreateMassProperty при позднем связывании отдаётся сразу объектом,
    # а не методом — вызывать его скобками нельзя (см. conn.prop).
    mp = prop(doc.Extension, "CreateMassProperty")
    com = list(prop(mp, "CenterOfMass") or [0, 0, 0])
    return {
        "mass": prop(mp, "Mass"),
        "volume": prop(mp, "Volume"),
        "density": prop(mp, "Density"),
        "area": prop(mp, "SurfaceArea"),
        "com": [c * 1000 for c in com],
    }
