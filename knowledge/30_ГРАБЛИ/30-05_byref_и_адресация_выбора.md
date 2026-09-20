---
id: 30-05
title: Выходные аргументы требуют VARIANT byref, а SelectByID2 — пустой VT_DISPATCH и полное имя с «@Сборка»
tags: [com, byref, SelectByID2, выбор, VARIANT]
applies_to: pywin32, позднее связывание, SolidWorks 2025 SP04
status: проверено
verified: 2026-09-20 — перебор четырёх форм аргумента и трёх форм имени
source: swkit/conn.py
---

# «Несовпадение типов» с номером аргумента

## Что происходит

Два разных вызова падают одинаково выглядящей ошибкой, и номер аргумента —
единственная подсказка:

```
sw.OpenDoc6(path, 1, 0, "", 0, 0)
  -> com_error (-2147352571, 'Несовпадение типов.', None, 5)

sw.ActivateDoc3(name, False, 0, 0)
  -> com_error (-2147352571, 'Несовпадение типов.', None, 4)

ext.SelectByID2(name, "COMPONENT", 0, 0, 0, True, 0, None, 0)
  -> com_error (-2147352571, 'Несовпадение типов.', None, 8)
```

Последнее число — **номер проблемного аргумента, считая с единицы**.

## Случай 1: выходные аргументы (by-ref)

Многие методы SolidWorks возвращают код ошибки через выходной параметр:
`OpenDoc6(..., Errors, Warnings)`, `ActivateDoc3(..., Errors)`,
`Extension.SaveAs(..., Errors, Warnings)`, `AddMate5(..., ErrorStatus)`.

При **раннем** связывании туда проходит обычный `0`, поэтому такой код
годами работает без нареканий. При **позднем** нужен типизированный VARIANT
с флагом `VT_BYREF`:

```python
import pythoncom
from win32com.client import VARIANT

def byref(value=0, vt=pythoncom.VT_I4):
    return VARIANT(pythoncom.VT_BYREF | vt, value)

doc = sw.OpenDoc6(path, 1, 0, "", byref(), byref())
sw.ActivateDoc3(name, False, 0, byref())
```

В библиотеке — `swkit.conn.byref()`, применяется внутри `open_doc`,
`activate`, `save_as`, `mate_origin_planes`.

## Случай 2: необязательный объектный аргумент

`SelectByID2` восьмым аргументом принимает `Callout` — объект. Ни `None`,
ни `0` не подходят:

```
callout=None                 -> ОШИБКА 'Несовпадение типов', arg 8
callout=0                    -> ОШИБКА 'Несовпадение типов', arg 8
callout=VT_EMPTY             -> ОШИБКА 'Несовпадение типов', arg 8
callout=VARIANT(VT_DISPATCH, None)  -> проходит
```

Нужен именно типизированный пустой диспетч:

```python
NULL_DISPATCH = VARIANT(pythoncom.VT_DISPATCH, None)
```

## Случай 3: имя объекта для выбора

Аргумент прошёл — а выбор всё равно `False`. Здесь дело в имени. Правила
адресации, проверенные перебором:

| Что выбираем | Имя | Результат |
|---|---|---|
| компонент сборки | `Основание-1` | **False** |
| компонент сборки | `Основание-1@Проба3` | True |
| плоскость компонента | `Спереди@Основание-1@Проба3` | True |
| плоскость компонента | `Спереди@Основание-1` | **False** |
| плоскость сборки | `Спереди` | True |

То есть `Name2` компонента возвращает `Основание-1`, и **этого имени
недостаточно** — нужен суффикс `@ИмяСборки` (имя файла сборки без
расширения).

## Как правильно

```python
from swkit.conn import select

select(asm, "Основание-1@Проба3", "COMPONENT")
select(asm, "Спереди@Основание-1@Проба3", "PLANE", append=True, mark=1)
select(asm, "Спереди", "PLANE", append=True, mark=1)
```

`swkit.conn.select()` подставляет `NULL_DISPATCH` и возвращает `bool`.
Имя компонента с суффиксом собирает `swkit.assembly.by_origin_mates`.

## Как неправильно

```python
ext.SelectByID2(name, "COMPONENT", 0, 0, 0, True, 0, None, 0)   # arg 8
select(asm, prop(comp, "Name2"), "COMPONENT")                    # вернёт False
```

Второй вариант опаснее: он не падает, а тихо возвращает `False`. Дальше
`AddMate5` создаёт сопряжение не с тем набором объектов или не создаёт
вовсе — а сообщение об ошибке появится далеко от причины.

**Всегда проверяйте результат `SelectByID2`.** В `swkit` каждая неудача
выбора печатается.

## Чем подтверждено

Таблицы выше получены прямым перебором на реальной сборке. После исправления:
три компонента, по три сопряжения, ноль ошибок выбора.
