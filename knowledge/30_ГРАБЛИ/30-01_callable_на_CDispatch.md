---
id: 30-01
title: callable() на объекте CDispatch всегда истинно — проверять надо тип, а не вызываемость
tags: [com, позднее-связывание, pywin32, prop]
applies_to: pywin32, позднее связывание (win32com.client.dynamic), любая версия SolidWorks
status: проверено
verified: 2026-09-20 — воспроизведено на SolidWorks 2025 SP04, исправлено в swkit/conn.py
source: эксперимент; исправлено в swkit/conn.py
---

# callable() не отличает значение от метода

## Что происходит

При позднем связывании pywin32 отдаёт члены COM-объекта неоднородно:

```
doc.GetTitle        -> 'Деталь34'                  уже значение (строка)
doc.FirstFeature    -> <COMObject <unknown>>       уже значение (объект)
doc.FeatureManager  -> <COMObject <unknown>>       уже значение (объект)
```

Напрашивается универсальный хелпер:

```python
def prop(obj, name):
    a = getattr(obj, name)
    return a() if callable(a) else a      # НЕВЕРНО
```

Для `GetTitle` он работает: строка не вызываема, возвращается как есть.
Для `FirstFeature` он ломается:

```
pywintypes.com_error: (-2147352573, 'Член группы не найден.', None, None)
```

## Почему

Класс `win32com.client.dynamic.CDispatch` **определяет `__call__`**. Поэтому
`callable(doc.FirstFeature)` истинно, хотя `FirstFeature` уже вернул готовый
объект. Хелпер вызывает его повторно — как метод по умолчанию, — и такого
члена нет.

Ошибка коварна тем, что проявляется не на всех членах: код, написанный и
отлаженный на строковых свойствах, разваливается при первом обращении к
дереву построения.

## Как правильно

Проверять именно тип, а не вызываемость:

```python
import types

def prop(obj, name):
    a = getattr(obj, name)
    return a() if isinstance(a, (types.MethodType, types.FunctionType,
                                 types.BuiltinFunctionType)) else a
```

`CDispatch` не является ни методом, ни функцией, поэтому возвращается как есть.

## Как неправильно

```python
a() if callable(a) else a          # ломается на FirstFeature, FeatureManager,
                                   # Extension, ConfigurationManager
```

Коварство в том, что такой хелпер работает на строковых свойствах
(`GetTitle`, `GetPathName`) и разваливается при первом обращении к дереву
построения или к менеджерам (`FeatureManager`, `Extension`,
`ConfigurationManager`). Код успевает выглядеть отлаженным.

## Чем подтверждено

```
doc.FirstFeature (атрибут)   -> CDispatch  <COMObject <unknown>>  callable: True
doc.FirstFeature()           -> ОШИБКА (-2147352573, 'Член группы не найден.')
```

После исправления `swkit/conn.py` обход дерева даёт
`['Спереди', 'Сверху', 'Справа']`, сквозной тест проходит целиком.

## Связанное

* [30-04](30-04_члены_интерфейсов_вне_dispatch.md) — обратный случай: член,
  которого в dispatch нет вовсе, и нужен `_FlagAsMethod`.
