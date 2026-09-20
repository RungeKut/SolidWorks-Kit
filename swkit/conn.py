# -*- coding: utf-8 -*-
"""Подключение к SolidWorks по COM.

Три режима связывания и их цена:

* раннее (gencache.EnsureModule + приведение типов) — видны имена методов
  и подсказки, но строгая проверка типов аргументов отвергает часть
  законных вызовов, например SaveAs с аргументом None;
* обычное (win32com.client.Dispatch) — поведение зависит от состояния кэша
  gencache, поэтому непредсказуемо;
* позднее (win32com.client.dynamic) — проходят любые сигнатуры, но члены
  объекта не видны заранее, и pywin32 отдаёт их неоднородно: одни
  значениями, другие методами.

По умолчанию здесь ПОЗДНЕЕ связывание: это единственный режим, который
выдерживает все вызовы SolidWorks без исключений. Неоднородность членов
закрывают хелперы prop() и call().
"""
import os
import sys
import types

import pythoncom
import win32com.client
import win32com.client.dynamic
from win32com.client import VARIANT

from . import dialogs

#: ProgID SolidWorks. Один и тот же для всех версий начиная с 2001.
PROGID = "SldWorks.Application"

#: GUID типовой библиотеки SolidWorks — нужен только для раннего связывания.
TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"


def utf8_console():
    """Заставить stdout принимать кириллицу.

    Без этого print() с русским текстом падает на UnicodeEncodeError, когда
    скрипт запущен из консоли с кодовой страницей 866. Вызывайте первой
    строкой каждого скрипта построения.
    """
    if hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
                                      encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer,
                                      encoding="utf-8", errors="replace")


def prop(obj, name):
    """Прочитать член COM-объекта, который может быть и свойством, и методом.

    При позднем связывании pywin32 отдаёт одни члены значениями, другие —
    связанными методами: doc.GetTitle сразу даёт строку, а doc.FeatureManager
    даёт COM-объект.

    ВАЖНО: проверять callable() здесь НЕЛЬЗЯ. Объекты win32com CDispatch
    определяют __call__, поэтому callable(doc.FirstFeature) истинно, хотя
    FirstFeature УЖЕ вернул объект. Повторный вызов даёт
    «Член группы не найден». Проверяется именно тип: связанный метод или
    функция — вызываем, всё остальное возвращаем как есть.
    """
    a = getattr(obj, name)
    return a() if isinstance(a, (types.MethodType, types.FunctionType,
                                 types.BuiltinFunctionType)) else a


def byref(value=0, vt=pythoncom.VT_I4):
    """VARIANT для ВЫХОДНОГО параметра COM-метода.

    Многие методы SolidWorks возвращают код ошибки через by-ref аргумент:
    OpenDoc6(..., errors, warnings), ActivateDoc3(..., errors),
    SaveAs(..., errors, warnings). При позднем связывании передача обычного
    целого нуля даёт «Несовпадение типов» с номером проблемного аргумента.
    При раннем связывании нули проходят — поэтому код, перенесённый с
    раннего связывания на позднее, ломается именно здесь.
    """
    return VARIANT(pythoncom.VT_BYREF | vt, value)


#: Пустой IDispatch для необязательных объектных аргументов COM.
#: SelectByID2 принимает восьмым аргументом Callout. Передать вместо него
#: None или 0 при позднем связывании нельзя — «Несовпадение типов»
#: с номером аргумента 8. Нужен именно типизированный пустой VARIANT.
#: При раннем связывании проходит None — ещё одно место, где ломается код,
#: перенесённый с раннего связывания.
NULL_DISPATCH = VARIANT(pythoncom.VT_DISPATCH, None)


def select(doc, name, typ, append=False, mark=0):
    """Выбрать объект по имени. Возвращает True/False.

    Правила адресации проверены 20.09.2026 (см. knowledge/30_ГРАБЛИ/30-05):

        компонент сборки       "Основание-1@Сборка"
        плоскость компонента   "Спереди@Основание-1@Сборка"
        плоскость сборки       "Спереди"
        объект в детали        "Бобышка-Вытянуть1"

    Имя компонента БЕЗ суффикса "@Сборка" не находится — Name2 возвращает
    "Основание-1", и этого недостаточно.
    """
    doc.ClearSelection2(True) if not append else None
    return bool(doc.Extension.SelectByID2(
        name, typ, 0, 0, 0, append, mark, NULL_DISPATCH, 0))


def call(obj, name, *args):
    """Вызвать метод COM-объекта при позднем связывании.

    _FlagAsMethod говорит pywin32 трактовать член как метод. Без него
    вызов с аргументами даёт «Property ... can not be set».
    """
    try:
        obj._FlagAsMethod(name)
    except Exception:
        pass
    return getattr(obj, name)(*args)


def app(visible=True, attach_first=True, watch_dialogs=True, verbose=False):
    """Получить приложение SolidWorks.

    attach_first=True — сначала пробуем подключиться к УЖЕ ЗАПУЩЕННОМУ
    экземпляру. Это почти всегда то, что нужно: холодный старт SolidWorks
    занимает больше минуты и упирается в диалоги лицензии, которые некому
    нажать, а при работе с открытой сессией вы видите на экране то же,
    что делает скрипт.

    watch_dialogs=True — поднимает сторож модальных окон (см. dialogs.py).
    Без него первое же предупреждение аддина подвешивает скрипт навсегда.
    """
    pythoncom.CoInitialize()
    sw = None
    if attach_first:
        try:
            raw = win32com.client.GetActiveObject(PROGID)
            sw = win32com.client.dynamic.Dispatch(raw)
            if verbose:
                print("ATTACH: подключились к запущенному SolidWorks")
        except Exception:
            sw = None
    if sw is None:
        sw = win32com.client.dynamic.Dispatch(PROGID)
        if verbose:
            print("DISPATCH: поднят новый экземпляр SolidWorks")
    sw.Visible = bool(visible)
    if watch_dialogs:
        pid = dialogs.solidworks_pid()
        if pid:
            dialogs.start(pid, verbose=verbose)
    return sw


def app_early():
    """Приложение с РАННИМ связыванием — для случаев, когда нужны имена типов.

    Возвращает (sw, S), где S — сгенерированный модуль типовой библиотеки.
    Приводить объекты типом: S.IModelDoc2(obj._oleobj_).

    Применяйте, только если позднее связывание не справилось: ранняя
    привязка ломает SaveAs с None и требует прогретого кэша gencache.
    """
    from win32com.client import gencache
    S = gencache.EnsureModule(TYPELIB, 0, 33, 0)
    raw = win32com.client.Dispatch(PROGID)
    sw = cast(S.ISldWorks, raw)
    sw.Visible = True
    return sw, S


def cast(cls, obj):
    """Привести COM-объект к интерфейсу типовой библиотеки (раннее связывание)."""
    if obj is None:
        return None
    return cls(getattr(obj, "_oleobj_", obj))


# --- документы ------------------------------------------------------------

DOC_PART, DOC_ASM, DOC_DRW = 1, 2, 3


def close_all(sw):
    """Закрыть все документы.

    Открытый документ держит файл и ломает перезапись при повторном
    построении. Вызывайте перед пересборкой.
    """
    try:
        call(sw, "CloseAllDocuments", True)
        return True
    except Exception:
        # запасной путь: закрывать по одному, пока есть активный
        for _ in range(64):
            doc = sw.ActiveDoc
            if doc is None:
                break
            call(sw, "CloseDoc", prop(doc, "GetTitle"))
        return sw.ActiveDoc is None


def open_doc(sw, path, doc_type=None, read_only=False, silent=True):
    """Открыть документ. doc_type определяется по расширению, если не задан."""
    if doc_type is None:
        ext = os.path.splitext(path)[1].lower()
        doc_type = {".sldprt": DOC_PART, ".sldasm": DOC_ASM,
                    ".slddrw": DOC_DRW}.get(ext, DOC_PART)
    if not os.path.isfile(path):
        raise RuntimeError("файла нет на диске: " + path)
    opts = (1 if silent else 0) | (2 if read_only else 0)

    # OpenDoc6 объявляет последние два аргумента как выходные (by-ref).
    # При позднем связывании передача целых нулей даёт «Несовпадение типов»:
    # нужны VARIANT с флагом VT_BYREF. При раннем связывании проходят и нули.
    doc = None
    try:
        res = sw.OpenDoc6(path, doc_type, opts, "", byref(), byref())
        doc = res[0] if isinstance(res, tuple) else res
    except Exception:
        doc = None
    if doc is None:
        try:
            doc = sw.OpenDoc(path, doc_type)     # старая перегрузка без by-ref
        except Exception:
            doc = None
    if doc is None:
        # OpenDoc* иногда открывает документ, но возвращает None
        doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("не открылся документ: " + path)
    return doc


def close(sw, doc):
    """Закрыть конкретный документ."""
    call(sw, "CloseDoc", prop(doc, "GetTitle"))


def activate(sw, path_or_name):
    """Сделать документ активным. Нужно после OpenDoc при работе со сборкой:
    AddComponent5 добавляет компонент в АКТИВНЫЙ документ."""
    name = os.path.basename(path_or_name)
    try:
        return sw.ActivateDoc3(name, False, 0, byref())
    except Exception:
        return sw.ActivateDoc2(name, False, byref())
