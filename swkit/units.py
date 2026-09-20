# -*- coding: utf-8 -*-
"""Единицы измерения.

API SolidWorks работает в МЕТРАХ и РАДИАНАХ. Вся библиотека swkit принимает
на вход МИЛЛИМЕТРЫ и ГРАДУСЫ и переводит на границе вызова. Никогда не
передавайте метры в функции swkit — получите деталь в 1000 раз меньше.
"""
import math

MM = 0.001          # множитель мм -> м
DEG = math.pi / 180

# угол уклона по умолчанию в FeatureExtrusion3/FeatureCut4: 1 градус в радианах.
# Само значение не действует, пока флаг уклона выключен, но SolidWorks
# отвергает нули в этих позициях на части сборок.
DRAFT = 0.01745329


def m(mm_value):
    """мм -> м."""
    return float(mm_value) / 1000.0


def mm(m_value):
    """м -> мм."""
    return float(m_value) * 1000.0


def rad(deg_value):
    """градусы -> радианы."""
    return float(deg_value) * DEG


def deg(rad_value):
    """радианы -> градусы."""
    return float(rad_value) / DEG


def m3_to_mm3(v):
    return v * 1e9


def m3_to_cm3(v):
    return v * 1e6
