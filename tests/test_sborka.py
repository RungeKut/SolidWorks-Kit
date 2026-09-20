# -*- coding: utf-8 -*-
"""Сквозная проверка swkit на реальном SolidWorks.

Что проверяется: детали в координатах сборки, сопряжения, статусы, проверка.

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
ASM_PATH = os.path.join(OUT, "Тест_сборка.SLDASM")

app = sw.app(verbose=True)
sw.close_all(app)

# --- три детали, смоделированные СРАЗУ в координатах сборки ---------------
# основание 2000x1000x200 и две стойки по краям
SPEC = [
    ("Основание", (0, 0, 2000, 1000), 0, 200),
    ("Стойка_левая", (0, 0, 200, 1000), 200, 1000),
    ("Стойка_правая", (1800, 0, 2000, 1000), 200, 1000),
]
paths = []
print("\n=== детали ===")
for name, rect, z0, z1 in SPEC:
    doc = sw.new_part(app)
    with sw.Sketch(doc, sw.TOP) as sk:
        sk.rect(*rect)
    # вытяжка вверх от отметки z0 на высоту (z1 - z0)
    sw.extrude(doc, sk.feature, z1 - z0, start_offset=z0)
    box = [round(v, 1) for v in sw.bbox_size_mm(doc)]
    p = sw.save_as(doc, os.path.join(OUT, name + ".SLDPRT"))
    paths.append(p)
    print("  %-16s габарит %s" % (name, box))
    sw.close(app, doc)

# --- сборка способом 3 ----------------------------------------------------
print("\n=== сборка: вставка с сопряжениями по базовым плоскостям ===")
asm = sw.new_assembly(app)
sw.save_as(asm, ASM_PATH)
sw.preload(app, ASM_PATH, paths)
asm = app.ActiveDoc

total_ok = total_bad = 0
for p in paths:
    comp, ok, bad = sw.by_origin_mates(app, asm, ASM_PATH, p)
    total_ok += ok
    total_bad += bad
    print("  %-30s сопряжений %d, ошибок %d" % (os.path.basename(p), ok, bad))

sw.rebuild(asm)
sw.save_as(asm, ASM_PATH)

print("\n=== проверка сборки ===")
print("статусы компонентов:", sw.status_report(asm))
ok = sw.check_assembly(asm, "Тест_сборка", expect_components=3,
                       require_fully_defined=True, allow_interference=False)

mp = sw.mass_properties(asm)
print("\nобъём сборки, мм3: %.0f" % (mp["volume"] * 1e9))
expect = 2000 * 1000 * 200 + 2 * (200 * 1000 * 800)
print("ожидалось:         %d" % expect)

shot = sw.shot(asm, os.path.join(OUT, "сборка_iso.png"), view="iso")
print("снимок:", os.path.basename(shot), os.path.getsize(shot), "байт")

print("\nИТОГ:", "СБОРКА ПРОЙДЕНА" if ok and total_bad == 0 else "ЕСТЬ ПРОБЛЕМЫ")
sys.exit(0 if ok and total_bad == 0 else 1)
