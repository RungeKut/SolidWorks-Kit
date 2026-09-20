# -*- coding: utf-8 -*-
"""Сквозная проверка swkit на реальном SolidWorks.

Что проверяется: деталь, эскиз, вытяжка, вырез, проверка, сохранение, снимок, STEP.

Запускать после обновления SolidWorks или правки библиотеки.
SolidWorks должен быть запущен. Код возврата 0 — всё прошло.
Построенные файлы остаются в tests/vyvod/ — посмотрите на них глазами:
числа не скажут, похоже ли это на задуманное.
"""
import os
import sys

sys.path.insert(0, r"C:\Users\Work\Desktop\SolidWorks-Kit")

import swkit as sw

sw.utf8_console()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vyvod")
os.makedirs(OUT, exist_ok=True)

print("=== 1. подключение ===")
app = sw.app(verbose=True)
print("шаблон детали:", sw.find_template(app, "part"))

print("\n=== 2. новая деталь, эскиз, вытяжка ===")
doc = sw.new_part(app)
print("плоскости (порядок дерева):", sw.feature_names(doc, "RefPlane")[:3])

# плита 2000 x 1000 x 200 на плоскости «Сверху»
with sw.Sketch(doc, sw.TOP) as sk:
    sk.rect(0, 0, 2000, 1000)
sw.extrude(doc, sk.feature, 200)
print("габарит после вытяжки, мм:", [round(v, 1) for v in sw.bbox_size_mm(doc)])

print("\n=== 3. вырез ===")
with sw.Sketch(doc, sw.TOP) as sk2:
    sk2.rect(500, 300, 900, 700)
sw.cut(doc, sk2.feature, end=sw.THROUGH_ALL)
mp = sw.mass_properties(doc)
print("объём после выреза, мм3: %.0f" % (mp["volume"] * 1e9))

print("\n=== 4. проверка числом ===")
expect_vol = 2000 * 1000 * 200 - 400 * 400 * 200
ok = sw.check_part(doc, "Тестовая плита",
                   expect_volume_mm3=expect_vol,
                   expect_box_mm=[2000, 200, 1000])

print("\n=== 5. сохранение и снимок ===")
path = sw.save_as(doc, os.path.join(OUT, "Тест_плита.SLDPRT"))
print("сохранено:", path, os.path.getsize(path), "байт")
shot = sw.shot(doc, os.path.join(OUT, "тест_iso.png"), view="iso")
print("снимок:", shot, os.path.getsize(shot), "байт")

print("\n=== 6. экспорт STEP ===")
step = sw.export(doc, os.path.join(OUT, "Тест_плита.STEP"))
print("STEP:", step, os.path.getsize(step), "байт")

sw.close(app, doc)
print("\nИТОГ:", "ВСЁ ПРОЙДЕНО" if ok else "ЕСТЬ РАСХОЖДЕНИЯ")
sys.exit(0 if ok else 1)
