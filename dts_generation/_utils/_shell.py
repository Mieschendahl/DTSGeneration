
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import threading
from typing import Optional

from dts_generation._utils._printer import printer

class ShellError(Exception):
    pass

class ShellTimeoutError(ShellError):
    pass

@dataclass
class ShellOutput:
    value: str
    code: int
    timeout: bool

def shell(
    command: str,
    verbose: bool = False,
    timeout: Optional[float] = None,
    check: bool = True,
    cwd: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None
) -> ShellOutput:
    with printer.with_verbose(verbose):
        message = f"Shell"
        if timeout is not None:
            message += f" (timeout: {timeout}s)"
        if cwd is not None:
            message += f" (cwd: {cwd})"
        if env is not None:
            message += f" (env: {env})"
        printer(message + ":")
        with printer:
            printer(command)
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1, # line-buffered text mode
                universal_newlines=True,
                cwd=cwd,
                env=env,
                shell=True,
                start_new_session=True,
            )
            captured: list[str] = []
            def _reader():
                assert proc.stdout is not None
                for line in proc.stdout:
                    printer(line, end="")
                    captured.append(line)
            t = threading.Thread(target=_reader, daemon=True)
            t.start()
            timeout_error = False
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timeout_error = True
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
                rc = 124 # like GNU timeout
            # Ensure we've drained stdout and the thread exited
            t.join()
            output = ShellOutput("".join(captured), rc, timeout_error)
            if check and output.timeout:
                raise ShellTimeoutError(f"Timeout after {timeout}s")
            if check and output.code != 0:
                raise ShellError(f"Non-Zero exit: {output.code}")
            return output