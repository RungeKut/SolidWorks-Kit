# -*- coding: utf-8 -*-
"""Проверка целостности базы знаний SolidWorks-Kit.

Выполняет раздел 9 файла knowledge/00_ПРАВИЛА.md:

  * у каждого файла базы есть шапка YAML с обязательными полями;
  * каждый файл присутствует в INDEX.md и наоборот;
  * нет двух файлов с одинаковым id;
  * id в шапке совпадает с именем файла;
  * записи со status: проверено имеют поле verified;
  * внутренние ссылки ведут на существующие файлы;
  * НИ ОДИН файл набора не упоминает постороннее изделие или проект.

Последняя проверка обязательна перед каждым коммитом: репозиторий публичный,
и название изделия, попавшее в набор, утекает наружу. Стоп-слова лежат в
tools/stoplist.txt; при работе над изделием укажите ещё и папку проекта —
тогда его имя и имена его моделей станут стоп-словами автоматически.

Запуск:
    python tools/check_docs.py
    python tools/check_docs.py --project "C:\путь\к\папке\проекта"
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


STOPLIST = os.path.join(ROOT, "tools", "stoplist.txt")
SKIP = ("tools/stoplist.txt",)   # сам код обязан быть чистым и проверяется
TEXT_EXT = (".md", ".py", ".ps1", ".txt", ".cfg", ".toml", ".json", ".yml")
# слишком общие, чтобы быть приметой изделия
GENERIC = set("model проект part assembly деталь сборка test main build "
              "params kit work temp data".split())


def repo_files():
    """Все текстовые файлы набора, кроме служебных и самого стоп-листа."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".venv")]
        for fn in sorted(filenames):
            if not fn.endswith(TEXT_EXT):
                continue
            full = os.path.join(dirpath, fn)
            r = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if r in SKIP:
                continue
            out.append(full)
    return sorted(out)


def stop_words():
    """Стоп-слова из tools/stoplist.txt."""
    if not os.path.exists(STOPLIST):
        return set()
    out = set()
    for line in read(STOPLIST).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def project_words(project_dir):
    """Приметы изделия, выведенные из папки проекта: её имя и имена моделей.

    Помнить про стоп-лист перед каждым коммитом невозможно, а путь к папке
    проекта в работе всегда под рукой — отсюда этот режим.
    """
    if not project_dir or not os.path.isdir(project_dir):
        return set()
    names = [os.path.basename(os.path.abspath(project_dir))]
    for fn in os.listdir(project_dir):
        stem, ext = os.path.splitext(fn)
        if ext.upper() in (".SLDPRT", ".SLDASM", ".SLDDRW", ".STEP"):
            names.append(stem)
    out = set()
    for name in names:
        for token in re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", name):
            if len(token) >= 4 and token.lower() not in GENERIC:
                out.add(token)
    return out


def main(project_dir=None):
    problems = []
    notes = []
    files = knowledge_files()
    ids = {}

    print("База знаний: %s" % KNOWLEDGE)
    print("Файлов найдено: %d" % len(files))
    print("Проверка на стоп-слова: %d файлов набора\n"
          % len(repo_files()))

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
    # Набор должен читаться как знание об инструменте, а не как история его
    # сборки: упоминаний конкретных изделий и проектов в нём быть не должно.
    # Проверяется ВЕСЬ набор, а не только knowledge/: название изделия однажды
    # утекло через CHANGELOG.md, который в прежнюю проверку не попадал.
    # Сравнение регистронезависимое: прежняя проверка сверяла регистр, и
    # название с большой буквы прошло мимо строчного стоп-слова.
    project = project_words(project_dir)
    if project:
        print("Приметы изделия из папки проекта: %s\n"
              % ", ".join(sorted(project)))
    words = stop_words() | project
    for path in repo_files():
        text = read(path).lower()
        r = os.path.relpath(path, ROOT).replace(os.sep, "/")
        for word in sorted(words):
            if word.lower() in text:
                problems.append("%s: упоминание постороннего изделия или "
                                "проекта %r (правило 1)" % (r, word))

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
    argv = sys.argv[1:]
    proj = None
    if "--project" in argv:
        i = argv.index("--project")
        if i + 1 >= len(argv):
            print("--project требует путь к папке проекта")
            sys.exit(2)
        proj = argv[i + 1]
    sys.exit(main(proj))
