from pathlib import Path

def unescape_package_name(name: str) -> str:
    if "__" in name:
        scope, pkg = name.split("__", 1)
        return f"@{scope}/{pkg}"
    return name

dt_path = Path(__file__).parent.parent.parent / "output" / "DefinitelyTyped" / "types"
escaped = 0
total = 0
for path in sorted(list(dt_path.iterdir()), key=lambda x: x.name):
    if path.is_dir():
        total += 1
        escaped_name = unescape_package_name(path.name)
        if escaped_name != path.name:
            escaped += 1
            print(escaped_name, path.name)
print(f"Got {escaped} escaped package names (i.e. dts-generate can't handel them) from a total of {total} package names")