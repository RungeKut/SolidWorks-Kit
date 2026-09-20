# -*- coding: utf-8 -*-
"""Экспорт в нейтральные форматы: STEP, IGES, STL, PDF, DWG."""
import glob
import os

from .conn import DOC_ASM, DOC_PART, byref, close, open_doc, prop

# swUserPreferenceIntegerValue_e
SW_STEP_AP = 213        # 214 или 203


def set_step_format(sw, ap=214):
    """Формат STEP: AP214 (с цветами) или AP203 (базовый)."""
    try:
        sw.SetUserPreferenceIntegerValue(SW_STEP_AP, ap)
        return True
    except Exception:
        return False


def export(doc, path):
    """Экспорт активного документа. Формат определяется расширением пути.

    Поддерживаются .step/.stp, .iges/.igs, .stl, .pdf, .dwg, .dxf, .x_t, .png.
    Каскад перегрузок SaveAs — тот же, что в part.save_as.
    """
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # options=2 (swSaveAsOptions_Copy) здесь ПРАВИЛЬНО: экспорт не должен
    # переименовывать открытую модель в Деталь.STEP.
    errs = []
    for name, fn in (("SaveAs3", lambda: doc.SaveAs3(path, 0, 2)),
                     ("Extension.SaveAs", lambda: doc.Extension.SaveAs(
                         path, 0, 2, None, byref(), byref())),
                     ("SaveAs2", lambda: doc.SaveAs2(path, 0, True, False)),
                     ("SaveAs", lambda: doc.SaveAs(path))):
        try:
            fn()
            if os.path.exists(path):
                return path
        except Exception as e:
            errs.append("%s: %s" % (name, str(e)[:70]))
    raise RuntimeError("экспорт не удался: %s\n  %s" % (path, "\n  ".join(errs)))


def is_real_document(path):
    """Отсеять служебные файлы блокировки SolidWorks.

    Файлы ~$Имя.SLDPRT — это не документы, а метки открытия. Попытка их
    открыть даёт непонятную ошибку в середине пакетного экспорта.
    """
    return not os.path.basename(path).startswith("~$")


def batch(sw, sources, out_dir, fmt="STEP", ap=214, verbose=True):
    """Пакетный экспорт списка файлов моделей.

    sources — список путей или каталогов. Каталоги раскрываются по маскам
    *.SLDPRT и *.SLDASM.
    Возвращает (успешно, [(имя, причина), ...]).
    """
    if fmt.upper().startswith("STEP"):
        set_step_format(sw, ap)

    files = []
    for s in sources:
        if os.path.isdir(s):
            files += glob.glob(os.path.join(s, "*.SLDPRT"))
            files += glob.glob(os.path.join(s, "*.SLDASM"))
        else:
            files.append(s)
    files = sorted(f for f in files if is_real_document(f))

    ext = {"STEP": ".STEP", "IGES": ".IGS", "STL": ".STL",
           "PDF": ".PDF", "PARASOLID": ".X_T"}.get(fmt.upper(), "." + fmt.lower())

    done, failed = 0, []
    for src in files:
        name = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(out_dir, name + ext)
        doc = None
        try:
            doc = open_doc(sw, src)
            export(doc, dst)
            size = os.path.getsize(dst) / 1024.0
            if verbose:
                print("  OK   %-28s %9.0f КБ" % (name, size))
            done += 1
        except Exception as e:
            if verbose:
                print("  FAIL %-28s %s" % (name, str(e)[:60]))
            failed.append((name, str(e)[:120]))
        finally:
            if doc is not None:
                try:
                    close(sw, doc)
                except Exception:
                    pass
    if verbose:
        print("\nЭкспортировано %d из %d в %s" % (done, len(files), out_dir))
    return done, failed
