---
id: 30-04
title: Члены IAssemblyDoc и IPartDoc не видны через дефолтный dispatch — нужен _FlagAsMethod
tags: [com, позднее-связывание, сборка, AddComponent5]
applies_to: pywin32, позднее связывание, SolidWorks 2025 SP04
status: проверено
verified: 2026-09-20 — AddComponent5, UnfixComponent, AddMate5, GetComponents
source: swkit/assembly.py
---

# Один документ — несколько интерфейсов, и не все они в dispatch

## Что происходит

`sw.ActiveDoc` возвращает один COM-объект, но у документа несколько
интерфейсов: `IModelDoc2` (общее для всех типов), `IPartDoc`, `IAssemblyDoc`,
`IDrawingDoc`, `IModelDocExtension`.

Через позднее связывание доступны члены `IModelDoc2`. Специфичные члены —
нет:

```python
asm.AddComponent5(path, 0, "", False, "", 0, 0, 0)
```
```
AttributeError: <unknown>.AddComponent5
```

## Почему

pywin32 при позднем связывании строит список членов по типовой информации
объекта по умолчанию. Члены, доступные только через QueryInterface к другому
интерфейсу, туда не попадают, и `__getattr__` честно сообщает, что атрибута нет.

## Как правильно

`_FlagAsMethod` заставляет pywin32 обращаться к члену по имени, не сверяясь
со списком:

```python
from swkit.conn import call

comp = call(asm, "AddComponent5", path, 0, "", False, "", 0.0, 0.0, 0.0)
call(asm, "UnfixComponent")
res = call(asm, "AddMate5", 0, 0, False, 0, 0, 0, 0, 0, 0, 0, 0,
           False, False, 0, byref())
comps = call(asm, "GetComponents", True)
```

`swkit.conn.call()` делает это внутри:

```python
def call(obj, name, *args):
    try:
        obj._FlagAsMethod(name)
    except Exception:
        pass
    return getattr(obj, name)(*args)
```

Проверено, что так работают: `AddComponent5`, `UnfixComponent`, `AddMate5`,
`GetComponents`, `ShowComponent`, `HideComponent`, `ForceRebuild3`,
`EditRebuild3`, `CloseAllDocuments`, `ViewZoomtofit2`, `GraphicsRedraw2`.

## Как неправильно

Прямое обращение `asm.AddComponent5(...)` — `AttributeError`.

И **не надо на этом основании переходить на раннее связывание целиком**:
оно приносит свои проблемы (строгая проверка типов, `SaveAs` с `None`).
Точечный `call()` дешевле.

## Важное ограничение: _FlagAsMethod помогает не всегда

Если член отсутствует **в самой типовой библиотеке**, `_FlagAsMethod` не
спасёт — вызов даст «Неизвестное имя»:

```
ext.CreateInterferenceDetectionManager
  без _FlagAsMethod -> AttributeError: <unknown>.CreateInterferenceDetectionManager
  с _FlagAsMethod   -> com_error (-2147352570, 'Неизвестное имя.')
```

Это признак того, что члена нет вовсе, а не что он спрятан за другим
интерфейсом. Случай разобран в [30-06](30-06_детектор_пересечений_недоступен.md).

## Как отличить одно от другого

```
AttributeError: <unknown>.ИмяЧлена     -> член спрятан, поможет call()
com_error 'Неизвестное имя'            -> члена нет, call() не поможет
com_error 'Несовпадение типов', arg N  -> член есть, неверен аргумент N (см. 30-05)
```

## Чем подтверждено

Сквозной тест сборки: три компонента вставлены, по три сопряжения каждому,
0 ошибок, все компоненты полностью определены, объём сборки совпал с
расчётным (720 000 000 мм³).
