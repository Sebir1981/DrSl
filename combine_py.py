#!/usr/bin/env python3
# combine_py.py
import argparse
from pathlib import Path
import sys

# === НАСТРОЙКИ ИСКЛЮЧЕНИЙ ===
EXCLUDE_DIRS = {
    ".venv", "venv", "env", ".env", 'migrations',
    "__pycache__", ".git", "node_modules",
    "dist", "build", "htmlcov", ".pytest_cache",
    ".mypy_cache", ".tox", ".idea", ".vscode",
    "tmp", "temp", "eggs", "wheels", "log",
    "media"  # ← "static" удалён, чтобы файлы попали в сборку
}


# ============================

def combine_files(folder: str, output: str, recursive: bool = False, add_separators: bool = True,
                  include_html: bool = False, include_static: bool = False):
    folder_path = Path(folder).resolve()
    script_name = Path(__file__).resolve().name
    output_name = Path(output).resolve().name

    if not folder_path.is_dir():
        print(f"❌ Ошибка: Папка '{folder}' не найдена или не является директорией.")
        sys.exit(1)

    # Формируем список расширений
    extensions = ["*.py"]
    if include_html:
        extensions.append("*.html")
    if include_static:
        extensions.extend(["*.css", "*.js"])

    # Собираем файлы
    all_files = []
    for ext in extensions:
        pattern = f"**/{ext}" if recursive else ext
        all_files.extend(folder_path.glob(pattern))
    all_files = sorted(all_files)

    # Исключаем сам скрипт и выходной файл
    exclude_names = {script_name}
    if output_name.lower().endswith(('.py', '.html', '.txt', '.css', '.js')):
        exclude_names.add(output_name)

    final_files = []
    skipped = 0
    for f in all_files:
        if f.name in exclude_names:
            skipped += 1
            continue
        # Пропускаем файлы, лежащие в запрещённых папках
        if any(part.lower() in EXCLUDE_DIRS for part in f.parts):
            skipped += 1
            continue
        final_files.append(f)

    if not final_files:
        print(f"⚠️ Предупреждение: В папке '{folder}' не найдено файлов для объединения.")
        sys.exit(0)

    output_path = Path(output).resolve()
    exts_info = ".py"
    if include_html: exts_info += ", .html"
    if include_static: exts_info += ", .css, .js"

    try:
        with open(output_path, "w", encoding="utf-8") as out_f:
            out_f.write(f"# 📦 Скомпилировано из: {folder_path}\n")
            out_f.write(f"# 📄 Расширения: {exts_info}\n")
            out_f.write(f"# 📄 Всего файлов: {len(final_files)}\n")
            out_f.write(f"# 🚫 Пропущено служебных файлов: {skipped}\n")
            out_f.write("# " + "=" * 60 + "\n\n")

            for file in final_files:
                if add_separators:
                    rel = file.relative_to(folder_path)
                    out_f.write(f"\n{'#' + '=' * 59}\n")
                    out_f.write(f"# >>> Файл: {file.name} | Путь: {rel}\n")
                    out_f.write(f"{'#' + '=' * 59}\n\n")

                try:
                    content = file.read_text(encoding="utf-8")
                    out_f.write(content)
                except Exception as e:
                    out_f.write(f"# ❌ ОШИБКА ЧТЕНИЯ ФАЙЛА: {e}\n")

                out_f.write("\n\n")

        print(f"✅ Успешно! Результат сохранён в: {output_path}")
        print(f"   📁 Включено: {len(final_files)} файлов | 🚫 Пропущено: {skipped}")
    except Exception as e:
        print(f"❌ Ошибка записи: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Объединение .py, .html, .css и .js файлов проекта в один документ")
    parser.add_argument("folder", help="Путь к корневой папке проекта")
    parser.add_argument("-o", "--output", default="full_project.txt", help="Имя выходного файла")
    parser.add_argument("-r", "--recursive", action="store_true", help="Искать во вложенных папках")
    parser.add_argument("--html", action="store_true", help="Добавить .html файлы (обычно из templates/)")
    parser.add_argument("--static", action="store_true", help="Добавить .css и .js файлы (обычно из static/)")
    parser.add_argument("--no-sep", action="store_true", help="Без разделителей между файлами")
    args = parser.parse_args()

    combine_files(args.folder, args.output, args.recursive, not args.no_sep, args.html, args.static)