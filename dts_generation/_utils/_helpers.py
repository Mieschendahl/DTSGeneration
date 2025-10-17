import json
from pathlib import Path
import shutil
from typing import Any, Optional

def create_dir(dst_path: Path, src_path: Optional[Path] = None, overwrite: bool = False) -> None:
    if overwrite:
        shutil.rmtree(dst_path, ignore_errors=True)
    if src_path is None:
        dst_path.mkdir(parents=True, exist_ok=True)
    else:
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True, symlinks=True)

def create_file(dst_path: Path, src_path: Optional[Path] = None, content: Optional[str] = None) -> None:
    create_dir(dst_path.parent)
    if src_path is None:
        dst_path.write_text("" if content is None else content)
    else:
        dst_path.write_text(src_path.read_text())

def escape_package_name(package_name: str) -> str:
    if package_name.startswith("@"):
        scope, package_name = package_name[1:].split("/", 1)
        return f"{scope}__{package_name}"
    return package_name

def unescape_package_name(name: str) -> str:
    if "__" in name:
        scope, pkg = name.split("__", 1)
        return f"@{scope}/{pkg}"
    return name

def get_children(dir_path: Path) -> list[Path]:
    if not dir_path.is_dir():
        return []
    return sorted(dir_path.iterdir(), key=lambda path: path.name)

def dir_empty(dir_path: Path) -> bool:
    return not (dir_path.is_dir() and any(dir_path.iterdir()))

def file_exists(file_path: Path) -> bool:
    return file_path.is_file()

def make_path_name_unique(path: Path) -> Path:
    if "." in path.name:
        stem, suffix = path.name.split(".", 1)
        suffix = "." + suffix
    else:
        stem, suffix = path.name, ""
    index = 0
    while path.exists():
        path = path.parent / f"{stem}_{index}{suffix}"
        index += 1
    return path

def load_data(file_path: Path, key: str, raise_missing: bool = True, default: Any = None) -> Any:
    data = {}
    if file_path.is_file():
        data = json.loads(file_path.read_text())
    if raise_missing and key not in data:
        raise KeyError(f"Key {key!r} not found at {file_path}")
    return data.get(key, default)

def save_data(file_path: Path, key: str, value: Any, raise_missing: bool = False, raise_overwrite: bool = False) -> None:
    data = {}
    if file_path.is_file():
        data = json.loads(file_path.read_text())
    if raise_missing and key not in data:
        raise KeyError(f"Key {key!r} not found at {file_path}")
    if raise_overwrite:
        raise KeyError(f"Key {key!r} already exists at {file_path}") 
    data[key] = value
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))