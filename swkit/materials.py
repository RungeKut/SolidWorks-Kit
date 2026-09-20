# -*- coding: utf-8 -*-
"""Пользовательская база материалов SolidWorks (.sldmat).

Позволяет добавить свои материалы с реальной плотностью и прочностью —
без этого масса модели не имеет смысла, а штатная база не содержит ни
железобетона B25, ни каменной ваты, ни ЛДСП.

Файл .sldmat — это XML в кодировке UTF-16. Он должен быть зарегистрирован
в SolidWorks: Настройки -> Расположение файлов -> Базы данных материалов.

Работа идёт «классификациями»: функция перезаписывает только свои
классификации, не трогая остальные материалы в файле. Перед первой записью
создаётся резервная копия .bak, и все последующие записи идут от неё —
поэтому повторный запуск не накапливает мусор.
"""
import os
import re
import shutil

#: Типовое расположение пользовательской базы на русской установке 2025.
DEFAULT_DB = (r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025"
              r"\Настроенный пользователем материал"
              r"\Настроенный пользователем материал.sldmat")

#: Штриховки разрезов по ГОСТ/ANSI — что чем принято обозначать.
HATCH = {
    "сталь": "ANSI32 (Steel)",
    "бетон": "ANSI31 (Iron BrickStone)",
    "кирпич": "ANSI35 (Firebrick)",
    "пластик": "ANSI34 (Plastic Rubber)",
    "изоляция": "ANSI37 (Lead Zinc Mg)",
    "дерево": "ANSI33 (Bronze Brass)",
}


class Material:
    """Один материал.

    density  — плотность, кг/м3
    E        — модуль упругости, Па
    nu       — коэффициент Пуассона
    strength — предел текучести и прочности, Па
    k        — теплопроводность, Вт/(м·К)
    c        — удельная теплоёмкость, Дж/(кг·К)
    rgb      — цвет образца, строка вида "969699"
    hatch    — имя штриховки (ключ из HATCH или полное имя)
    """

    def __init__(self, name, density, E, nu, strength, k, c, rgb,
                 hatch="сталь", description=""):
        self.name = name
        self.density = density
        self.E = E
        self.nu = nu
        self.strength = strength
        self.k = k
        self.c = c
        self.rgb = rgb
        self.hatch = HATCH.get(hatch, hatch)
        self.description = description

    @property
    def G(self):
        """Модуль сдвига из E и nu."""
        return self.E / (2 * (1 + self.nu))

    def to_xml(self):
        return "\n".join([
            '\t\t<material name="%s" description="%s">' % (self.name, self.description),
            '\t\t\t<shaders/>',
            '\t\t\t<swatchcolor RGB="%s">' % self.rgb,
            '\t\t\t\t<sldcolorswatch:Optical Ambient="1.00000" '
            'Transparency="0.00000" Diffuse="1.00000" Specularity="0.30000" '
            'Shininess="0.200000" Emission="0.000000"/>',
            '\t\t\t</swatchcolor>',
            '\t\t\t<xhatch name="%s" angle="0.0" scale="1.0"/>' % self.hatch,
            '\t\t\t<physicalproperties>',
            '\t\t\t\t<EX displayname="Модуль упругости" value="%.6g"/>' % self.E,
            '\t\t\t\t<NUXY displayname="Коэффициент Пуассона" value="%s"/>' % self.nu,
            '\t\t\t\t<GXY displayname="Модуль сдвига" value="%.6g"/>' % self.G,
            '\t\t\t\t<ALPX displayname="Коэффициент теплового расширения" value="1e-005"/>',
            '\t\t\t\t<DENS displayname="Плотность" value="%s"/>' % self.density,
            '\t\t\t\t<KX displayname="Теплопроводность" value="%s"/>' % self.k,
            '\t\t\t\t<C displayname="Удельная теплоемкость" value="%s"/>' % self.c,
            '\t\t\t\t<SIGXT displayname="Предел прочности при растяжении" value="%.6g"/>' % self.strength,
            '\t\t\t\t<SIGYLD displayname="Предел текучести" value="%.6g"/>' % self.strength,
            '\t\t\t</physicalproperties>',
            '\t\t\t<custom/>',
            '\t\t</material>',
        ])


def classification_xml(title, materials):
    """XML одной классификации (группы материалов)."""
    body = "\n".join(mt.to_xml() for mt in materials)
    return '\t<classification name="%s">\n%s\n\t</classification>' % (title, body)


def write(classifications, database=DEFAULT_DB):
    """Записать классификации в базу материалов.

    classifications — словарь {название_группы: [Material, ...]}.

    Переписывает ТОЛЬКО перечисленные группы. Остальные материалы в файле
    не затрагиваются. Резервная копия .bak создаётся один раз и служит
    исходником при каждом запуске, поэтому повторный запуск идемпотентен.
    """
    if not os.path.exists(database):
        raise RuntimeError(
            "база материалов не найдена: %s\n"
            "Создайте её в SolidWorks (Правка материала -> Пользовательские "
            "материалы) и зарегистрируйте в Настройки -> Расположение файлов "
            "-> Базы данных материалов" % database)

    bak = database + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(database, bak)

    with open(bak, encoding="utf-16") as f:
        text = f.read()

    for title in classifications:
        text = re.sub(r'\n\t<classification name="%s">.*?\n\t</classification>'
                      % re.escape(title), "", text, flags=re.S)

    add = "\n".join(classification_xml(t, mats)
                    for t, mats in classifications.items())
    text = text.replace("</mstns:materials>", add + "\n</mstns:materials>")

    with open(database, "w", encoding="utf-16") as f:
        f.write(text)

    total = sum(len(v) for v in classifications.values())
    return database, total


# ==========================================================================
# готовые наборы материалов, проверенные на реальных моделях
# ==========================================================================

STROITELNYE = [
    Material("Железобетон монолитный B25", 2500, 3.00e10, 0.20, 1.45e7,
             1.70, 840, "969699", "бетон", "Строительные конструкции"),
    Material("Блок силикатный", 1800, 1.60e10, 0.20, 1.00e7,
             0.87, 880, "f2f2f2", "кирпич", "Строительные конструкции"),
    Material("Блок керамический поризованный", 800, 6.00e9, 0.20, 5.00e6,
             0.20, 880, "e8e0b4", "кирпич", "Строительные конструкции"),
    Material("Панель стеновая керамическая", 1000, 7.00e9, 0.20, 5.00e6,
             0.25, 880, "efe9d6", "кирпич", "Строительные конструкции"),
    Material("Утеплитель - вата каменная", 110, 5.00e6, 0.15, 1.00e4,
             0.042, 840, "fff8dc", "изоляция", "Строительные конструкции"),
]

MEBEL = [
    Material("Мебель корпусная (ЛДСП)", 700, 2.50e9, 0.30, 1.50e7,
             0.15, 1700, "c8a06a", "дерево", "Мебель и оборудование"),
    Material("Мягкая мебель", 150, 5.00e6, 0.35, 1.00e5,
             0.05, 1400, "5f7186", "пластик", "Мебель и оборудование"),
    Material("Бытовая техника", 500, 7.00e10, 0.30, 2.50e8,
             20.0, 500, "aeb4b9", "сталь", "Мебель и оборудование"),
    Material("Сантехника (фаянс)", 2000, 6.00e10, 0.22, 3.00e7,
             1.30, 900, "f4f7f9", "изоляция", "Мебель и оборудование"),
]

#: Плотности для проверки назначения материала (см. verify.check_part).
DENSITY = {mt.name: mt.density for mt in STROITELNYE + MEBEL}
