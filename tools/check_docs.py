# -*- coding: utf-8 -*-
"""Проверка целостности базы знаний SolidWorks-Kit.

Выполняет раздел 9 файла knowledge/00_ПРАВИЛА.md:

  * у каждого файла базы есть шапка YAML с обязательными полями;
  * каждый файл присутствует в INDEX.md и наоборот;
  * нет двух файлов с одинаковым id;
  * id в шапке совпадает с именем файла;
  * записи со status: проверено имеют поле verified;
  * внутренние ссылки ведут на существующие файлы.

Запуск:
    python tools/check_docs.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE = os.path.join(ROOT, "knowledge")
INDEX = os.path.join(KNOWLEDGE, "INDEX.md")

REQUIRED = ("id", "title", "status")
VALID_STATUS = ("проверено", "не проверено", "устарело", "действует")


def read(path):
    return io.open(path, encoding="utf-8").read()


def front_matter(text):
    """Разобрать шапку YAML. Возвращает словарь (плоский, без вложенности)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def knowledge_files():
    out = []
    for dirpath, _dirnames, filenames in os.walk(KNOWLEDGE):
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            if fn in ("INDEX.md",):
                continue
            out.append(os.path.join(dirpath, fn))
    return sorted(out)


def rel(path):
    return os.path.relpath(path, KNOWLEDGE).replace("\\", "/")


def main():
    problems = []
    notes = []
    files = knowledge_files()
    ids = {}

    print("База знаний: %s" % KNOWLEDGE)
    print("Файлов найдено: %d\n" % len(files))

    # --- шапки -----------------------------------------------------------
    for path in files:
        r = rel(path)
        fm = front_matter(read(path))
        if fm is None:
            problems.append("%s: нет шапки YAML" % r)
            continue
        for field in REQUIRED:
            if field not in fm:
                problems.append("%s: в шапке нет поля %s" % (r, field))
        status = fm.get("status", "")
        if status and status not in VALID_STATUS:
            problems.append("%s: неизвестный status %r (допустимы: %s)"
                            % (r, status, ", ".join(VALID_STATUS)))
        if status == "проверено" and not fm.get("verified"):
            problems.append("%s: status «проверено», но нет поля verified — "
                            "запись не имеет силы (правило 3)" % r)

        fid = fm.get("id", "")
        if fid:
            if fid in ids:
                problems.append("%s: id %s уже занят файлом %s"
                                % (r, fid, ids[fid]))
            else:
                ids[fid] = r
            base = os.path.basename(path)
            if not base.startswith(fid.replace('"', '')):
                # 00_ПРАВИЛА.md имеет id "00" — допускаем префикс без разделителя
                if not base.startswith(fid + "_") and base != "00_ПРАВИЛА.md":
                    problems.append("%s: id %s не совпадает с именем файла"
                                    % (r, fid))

    # --- индекс ----------------------------------------------------------
    if not os.path.exists(INDEX):
        problems.append("нет INDEX.md")
    else:
        index_text = read(INDEX)
        linked = set(re.findall(r"\]\(([^)]+\.md)\)", index_text))
        linked = {l.replace("\\", "/") for l in linked}
        for path in files:
            r = rel(path)
            if r not in linked:
                problems.append("%s: файла нет в INDEX.md (правило 5)" % r)
        existing = {rel(p) for p in files} | {"00_ПРАВИЛА.md"}
        for l in sorted(linked):
            if l not in existing and not l.startswith(".."):
                problems.append("INDEX.md ссылается на несуществующий %s" % l)

    # --- внутренние ссылки ------------------------------------------------
    for path in files:
        base = os.path.dirname(path)
        for link in re.findall(r"\]\(([^)]+\.md)\)", read(path)):
            if link.startswith("http"):
                continue
            target = os.path.normpath(os.path.join(base, link))
            if not os.path.exists(target):
                problems.append("%s: битая ссылка -> %s" % (rel(path), link))

    # --- посторонние привязки ----------------------------------------------
    # База должна читаться как знание об инструменте, а не как история его
    # сборки: упоминаний сторонних проектов в ней быть не должно.
    FOREIGN = ("CyberWood", "cybertruck", "Квартира_3А",
               "SolidWorks-MCP-Установка")
    for path in files:
        text = read(path)
        for word in FOREIGN:
            if word in text:
                problems.append("%s: упоминание стороннего проекта %r "
                                "(правило 1)" % (rel(path), word))

    # --- вывод -------------------------------------------------------------
    if problems:
        print("РАСХОЖДЕНИЯ (%d):" % len(problems))
        for p in problems:
            print("  - " + p)
    else:
        print("Расхождений нет.")

    if notes:
        print("\nЗамечания (%d):" % len(notes))
        for n in notes:
            print("  - " + n)

    print("\nЗанятые id: %s" % ", ".join(sorted(ids)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.exit(main())
