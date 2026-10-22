#!/usr/bin/env python3
"""
File Organizer
--------------
Sorts files in a folder into category subfolders (Images, Documents, etc.)
based on their extension.

Usage examples:
    python file_organizer.py ~/Downloads --dry-run     # preview only
    python file_organizer.py ~/Downloads                # organize for real
    python file_organizer.py ~/Downloads --by-date      # Images/2026-10/...
    python file_organizer.py ~/Downloads --recursive    # include subfolders
    python file_organizer.py ~/Downloads --undo         # revert last run
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff", ".ico"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods", ".tsv"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".go",
             ".rs", ".json", ".xml", ".yml", ".yaml", ".sh", ".sql", ".ipynb"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk"},
    "Fonts": {".ttf", ".otf", ".woff", ".woff2"},
}

OTHER = "Other"
LOG_NAME = ".organizer_log.json"


def get_category(path: Path) -> str:
    ext = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return OTHER


def unique_destination(dest: Path) -> Path:
    """If dest exists, append (1), (2), ... before the extension."""
    if not dest.exists():
        return dest
    counter = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({counter}){dest.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def collect_files(folder: Path, recursive: bool):
    category_dirs = set(CATEGORIES) | {OTHER}
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    for item in iterator:
        if not item.is_file():
            continue
        if item.name.startswith(".") or item.name == LOG_NAME:
            continue  # skip hidden files and our own log
        # Skip files already inside a category folder
        rel_parts = item.relative_to(folder).parts
        if len(rel_parts) > 1 and rel_parts[0] in category_dirs:
            continue
        yield item


def organize(folder: Path, dry_run: bool, by_date: bool, recursive: bool) -> None:
    moves = []  # list of (source, destination) strings for undo
    counts = {}

    for file in collect_files(folder, recursive):
        category = get_category(file)
        target_dir = folder / category
        if by_date:
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            target_dir = target_dir / mtime.strftime("%Y-%m")

        dest = unique_destination(target_dir / file.name)

        if dry_run:
            print(f"[DRY RUN] {file.relative_to(folder)}  ->  {dest.relative_to(folder)}")
        else:
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(dest))
                moves.append((str(file), str(dest)))
                print(f"Moved: {file.name}  ->  {dest.relative_to(folder)}")
            except (PermissionError, OSError) as e:
                print(f"Skipped {file.name}: {e}", file=sys.stderr)
                continue

        counts[category] = counts.get(category, 0) + 1

    if not counts:
        print("Nothing to organize.")
        return

    print("\nSummary:")
    for category, n in sorted(counts.items()):
        print(f"  {category:<14} {n} file(s)")

    if not dry_run and moves:
        log_path = folder / LOG_NAME
        log_path.write_text(json.dumps(moves, indent=2))
        print(f"\nDone. Run again with --undo to revert ({LOG_NAME} saved).")


def undo(folder: Path) -> None:
    log_path = folder / LOG_NAME
    if not log_path.exists():
        print("No undo log found in this folder.")
        return

    moves = json.loads(log_path.read_text())
    restored = 0
    for src, dest in reversed(moves):
        src_path, dest_path = Path(src), Path(dest)
        if not dest_path.exists():
            print(f"Missing, can't restore: {dest_path.name}")
            continue
        src_path.parent.mkdir(parents=True, exist_ok=True)
        final_src = unique_destination(src_path)
        shutil.move(str(dest_path), str(final_src))
        restored += 1

    # Remove now-empty category folders
    for sub in sorted(folder.rglob("*"), reverse=True):
        if sub.is_dir():
            try:
                sub.rmdir()  # only succeeds if empty
            except OSError:
                pass

    log_path.unlink()
    print(f"Restored {restored} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize files into folders by type.")
    parser.add_argument("folder", type=Path, help="Folder to organize")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving files")
    parser.add_argument("--by-date", action="store_true", help="Add YYYY-MM subfolders")
    parser.add_argument("--recursive", action="store_true", help="Include files in subfolders")
    parser.add_argument("--undo", action="store_true", help="Revert the last organize run")
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"Error: '{folder}' is not a valid folder.")

    if args.undo:
        undo(folder)
    else:
        organize(folder, args.dry_run, args.by_date, args.recursive)


if __name__ == "__main__":
    main()
