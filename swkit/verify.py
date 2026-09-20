# -*- coding: utf-8 -*-
"""Проверка построенной модели.

Главный принцип:

    ДЕТАЛЬ, КОТОРАЯ ОТКРЫЛАСЬ, — ЕЩЁ НЕ ПРАВИЛЬНАЯ ДЕТАЛЬ.

Незамкнутый контур, молча слившиеся контуры, вырез не в ту сторону, глубина
вытяжки в метрах вместо миллиметров — всё это даёт файл, который открывается
и выглядит как модель. Ловится только сверкой с независимо посчитанным
ожиданием.

Два уровня проверки, нужны оба:
  числовой  — объём, масса, плотность, габарит (этот модуль);
  глазами   — виды в PNG (модуль views). Числа не скажут, что кузов
              не похож на кузов.
"""


class Report:
    """Накопитель результатов проверки.

        r = Report("01_Лонжерон")
        r.close_to("объём, мм3", got, expected, tol=1e-3, rel=True)
        r.equal("проёмов", len(cuts), 3)
        r.done()          # печатает и возвращает True/False
    """

    def __init__(self, name):
        self.name = name
        self.rows = []

    def _add(self, ok, what, got, expected, note=""):
        self.rows.append((bool(ok), what, got, expected, note))
        return bool(ok)

    def equal(self, what, got, expected):
        return self._add(got == expected, what, got, expected)

    def close_to(self, what, got, expected, tol=1e-6, rel=False):
        """Сравнение с допуском. rel=True — допуск относительный."""
        if got is None or expected is None:
            return self._add(False, what, got, expected, "нет значения")
        d = abs(got - expected)
        limit = abs(expected) * tol if rel else tol
        note = "откл. %.4g" % d
        if rel and expected:
            note = "откл. %.3f %%" % (100.0 * d / abs(expected))
        return self._add(d <= limit, what, got, expected, note)

    def box(self, what, got, expected, tol=0.1):
        """Сравнение габаритов: списки одинаковой длины, мм."""
        if len(got) != len(expected):
            return self._add(False, what, got, expected, "разная длина")
        d = max(abs(a - b) for a, b in zip(got, expected))
        return self._add(d <= tol, what,
                         [round(v, 1) for v in got],
                         [round(v, 1) for v in expected],
                         "макс. откл. %.2f мм" % d)

    def truth(self, what, ok, note=""):
        return self._add(ok, what, "да" if ok else "нет", "да", note)

    def skip(self, what, note=""):
        """Отметить проверку как НЕ ВЫПОЛНЕННУЮ.

        Пропуск не влияет на итог, но печатается отдельной пометкой: модель
        не должна считаться проверенной по признаку, который не проверяли.
        """
        self.rows.append((None, what, "не проверено", "-", note))
        return None

    @property
    def ok(self):
        return all(r[0] for r in self.rows if r[0] is not None)

    @property
    def skipped(self):
        return [r[1] for r in self.rows if r[0] is None]

    def done(self, verbose=True):
        if verbose:
            print("\n%s" % self.name)
            for ok, what, got, expected, note in self.rows:
                mark = "  ПРОПУСК" if ok is None else ("  OK  " if ok
                                                      else "  ОШИБКА")
                print("%s %-28s получено %-22s ожидалось %-22s %s"
                      % (mark, what, _fmt(got), _fmt(expected), note))
            tail = ""
            if self.skipped:
                tail = " (пропущено: %d)" % len(self.skipped)
            print("  итог: %s%s" % ("все проверки пройдены" if self.ok
                                    else "ЕСТЬ РАСХОЖДЕНИЯ", tail))
        return self.ok


def _fmt(v):
    if isinstance(v, float):
        return "%.4g" % v
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join("%.4g" % x if isinstance(x, float) else str(x)
                               for x in v) + "]"
    return str(v)


# ==========================================================================
# готовые проверки
# ==========================================================================

def check_part(doc, name, expect_volume_mm3=None, expect_box_mm=None,
               expect_density=None, expect_bodies=1, tol_rel=1e-3,
               tol_box=0.1, verbose=True):
    """Стандартная сверка детали с ожиданием.

    expect_volume_mm3 — объём, посчитанный независимо (по формуле, не из
                        SolidWorks). Именно независимость даёт смысл проверке.
    expect_box_mm     — [dx, dy, dz] габарит.
    expect_density    — плотность назначенного материала, кг/м3.
    """
    from .part import bbox_size_mm, bodies, mass_properties
    r = Report(name)
    bs = bodies(doc)
    r.equal("тел в детали", len(bs), expect_bodies)
    if not bs:
        return r.done(verbose)

    mp = mass_properties(doc)
    if expect_volume_mm3 is not None:
        r.close_to("объём, мм3", mp["volume"] * 1e9, expect_volume_mm3,
                   tol=tol_rel, rel=True)
    if expect_density is not None:
        r.close_to("плотность, кг/м3", mp["density"], expect_density, tol=1.0)
    if expect_box_mm is not None:
        r.box("габарит, мм", bbox_size_mm(doc), expect_box_mm, tol=tol_box)
    return r.done(verbose)


def check_assembly(asm, name="сборка", expect_components=None,
                   require_fully_defined=True, allow_interference=False,
                   verbose=True):
    """Стандартная сверка сборки.

    require_fully_defined — главная проверка. Недоопределённые компоненты
    уедут при следующем перестроении: модель, правильная сегодня, завтра
    развалится, и причину будет не найти.
    """
    from .assembly import (FULLY_DEFINED, STATUS, check_interference,
                           components, status_report)
    from .conn import prop
    r = Report(name)
    comps = components(asm)
    if expect_components is not None:
        r.equal("компонентов", len(comps), expect_components)
    else:
        r.truth("компоненты есть", len(comps) > 0, "%d шт." % len(comps))

    if require_fully_defined:
        bad = [prop(c, "Name2") for c in comps
               if prop(c, "GetConstrainedStatus") != FULLY_DEFINED]
        r.truth("все полностью определены", not bad,
                "не определены: " + ", ".join(bad[:5]) if bad else
                str(status_report(asm)))

    if not allow_interference:
        inter = check_interference(asm)
        if inter is None:
            # проверка недоступна на этой установке — это не провал сборки,
            # но и не подтверждение. Отмечаем явно, чтобы не создавать
            # ложного ощущения проверенности.
            r.skip("пересечения компонентов",
                   "детектор недоступен, см. assembly.check_interference; "
                   "используйте check_volume_additive")
        else:
            r.truth("нет пересечений", not inter,
                    "пересечений: %d" % len(inter) if inter else "")
    return r.done(verbose)


def box_area(h, flange_w, flange_t, web_t):
    """Площадь коробчатого сечения: две полки + две стенки. Всё в мм."""
    return (flange_w + 2 * web_t) * h - flange_w * (h - 2 * flange_t)


def poly_area(pts):
    """Площадь многоугольника по формуле шнурования. pts — [(x, y), ...]."""
    p = list(pts)
    if p[0] != p[-1]:
        p.append(p[0])
    a = 0.0
    for i in range(len(p) - 1):
        a += p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1]
    return abs(a) / 2.0
