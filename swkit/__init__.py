# -*- coding: utf-8 -*-
"""swkit — библиотека построения моделей SolidWorks скриптами.

Проверенное поведение API, разобранные сигнатуры и типовые ошибки —
в knowledge/ (начинать с knowledge/INDEX.md).

Быстрый старт:

    import swkit as sw

    sw.utf8_console()
    app = sw.app()                       # подключиться к запущенному SolidWorks
    doc = sw.new_part(app)

    with sw.Sketch(doc, sw.TOP) as sk:   # эскиз на плоскости «Сверху»
        sk.rect(0, 0, 2000, 1000)        # мм
    sw.extrude(doc, sk.feature, 200)     # мм

    sw.check_part(doc, "Плита", expect_volume_mm3=2000 * 1000 * 200,
                  expect_box_mm=[2000, 200, 1000])
    sw.save_as(doc, r"C:\\проект\\Плита.SLDPRT")

Единицы: на вход всегда МИЛЛИМЕТРЫ и ГРАДУСЫ. Перевод в метры и радианы,
которых требует API, делается внутри.
"""

__version__ = "1.0.0"

from .conn import (DOC_ASM, DOC_DRW, DOC_PART, NULL_DISPATCH, activate, app,
                   app_early, byref, call, cast, close, close_all, open_doc,
                   prop, select, utf8_console)
from .units import DEG, MM, deg, m, m3_to_cm3, m3_to_mm3, mm, rad
from .part import (BLIND, FRONT, MIDPLANE, RIGHT, START_OFFSET, THROUGH_ALL,
                   THROUGH_ALL_BOTH, TOP, Sketch, base_planes, bbox_centre_mm,
                   bbox_mm, bbox_size_mm, bbox_union_mm, bodies, cut, extrude,
                   feature_names, features, find_template, last_feature,
                   mass_properties, new_part, revolve, save_as, select_plane,
                   set_color, set_material, sketch_on)
from .assembly import (ALIGNED, COINCIDENT, CONCENTRIC, FULLY_DEFINED,
                       STATUS, UNDER_DEFINED,
                       assembly_name, by_coordinates, by_origin_mates,
                       by_transform, check_interference, components,
                       check_volume_additive, mate_origin_planes,
                       new_assembly, plane_names, preload,
                       rebuild, rx, ry, rz, show, status_report)
from .views import (STD, VIEWS_Z_UP, named_view, set_view, shaded, shot,
                    shot_set, shot_set_z_up)
from .export import batch as export_batch
from .export import export, set_step_format
from .verify import (Report, box_area, check_assembly, check_part, poly_area)
from . import dialogs, materials

__all__ = [
    # подключение
    "app", "app_early", "utf8_console", "prop", "call", "cast", "byref",
    "select", "NULL_DISPATCH",
    "open_doc", "close", "close_all", "activate",
    "DOC_PART", "DOC_ASM", "DOC_DRW",
    # единицы
    "m", "mm", "rad", "deg", "MM", "DEG", "m3_to_mm3", "m3_to_cm3",
    # деталь
    "new_part", "find_template", "Sketch", "sketch_on", "extrude", "cut",
    "revolve", "save_as", "set_material", "set_color",
    "base_planes", "select_plane", "features", "feature_names",
    "last_feature", "FRONT", "TOP", "RIGHT",
    "BLIND", "THROUGH_ALL", "THROUGH_ALL_BOTH", "MIDPLANE", "START_OFFSET",
    "bodies", "bbox_mm", "bbox_size_mm", "bbox_union_mm", "bbox_centre_mm",
    "mass_properties",
    # сборка
    "new_assembly", "assembly_name", "preload", "by_coordinates",
    "by_transform", "by_origin_mates", "mate_origin_planes", "components",
    "status_report", "check_interference", "check_volume_additive",
    "rebuild", "show", "plane_names",
    "rx", "ry", "rz", "COINCIDENT", "CONCENTRIC", "ALIGNED", "FULLY_DEFINED",
    "UNDER_DEFINED", "STATUS",
    # виды
    "named_view", "set_view", "shot", "shot_set", "shot_set_z_up", "shaded",
    "STD", "VIEWS_Z_UP",
    # экспорт
    "export", "export_batch", "set_step_format",
    # проверка
    "Report", "check_part", "check_assembly", "box_area", "poly_area",
    # модули
    "dialogs", "materials",
]
