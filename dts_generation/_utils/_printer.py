from io import TextIOWrapper
from typing import Any, Self

class WithVerbose:
    def __init__(self, printer: "Printer", verbose: bool):
        self._printer = printer
        self._verbose = verbose
    
    def __enter__(self) -> Self:
        self._old_verbose = self._printer.get_verbose()
        self._printer.set_verbose(self._verbose)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._printer.set_verbose(self._old_verbose)

class WithFile:
    def __init__(self, printer: "Printer", file: TextIOWrapper):
        self._printer = printer
        self._file = file
    
    def __enter__(self) -> Self:
        self._printer.add_file(self._file)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._printer.remove_file(self._file)

class Printer:
    def __init__(self):
        self._level = 0
        self._new_line = True
        self.set_padding()
        self.set_verbose()
        self.set_files([])
    
    def set_verbose(self, verbose: bool = True) -> None:
        self._verbose = verbose

    def get_verbose(self) -> bool:
        return self._verbose

    def set_padding(self, padding: str = "  ") -> Self:
        self._padding = padding
        return self
    
    def get_padding(self) -> str:
        return self._padding

    def set_files(self, file: list[TextIOWrapper]) -> None:
        self._files = file

    def get_file(self) -> list[TextIOWrapper]:
        return self._files

    def add_file(self, file: TextIOWrapper) -> None:
        if file not in self._files:
            self._files.append(file)
    
    def remove_file(self, file: TextIOWrapper) -> None:
        self._files.remove(file)

    def __enter__(self) -> Self:
        self._level += 1
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._level -= 1

    def with_verbose(self, verbose: bool) -> "WithVerbose":
        return WithVerbose(self, verbose)
    
    def with_file(self, file: TextIOWrapper) -> "WithFile":
        return WithFile(self, file)

    def __call__(self, text: str = "", end: str = "\n", flush: bool = True) -> Self:
        if not self._verbose:
            return self
        text += end
        if self._new_line:
            self._new_line = False
            text = self._padding * self._level + text
        if text.endswith("\n"):
            self._new_line = True
            text = text[:-1].replace("\n", "\n" + self._padding * self._level) + "\n"
        else:
            text = text.replace("\n", "\n" + self._padding * self._level)
        print(text, end="", flush=flush)
        for file in self._files:
            print(text, end="", flush=flush, file=file)
        return self

printer = Printer()