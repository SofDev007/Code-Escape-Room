# ============================================================
#  welcome_banner/setup.py
#
#  Prints a "Code Escape Room" ASCII banner during
#  `pip install -r requirements.txt`.
#
#  Self-contained: the art is hard-coded below (rendered once with
#  `figlet -w 200 -f slant "Code Escape Room"`), so NO figlet / pyfiglet
#  is needed on the end user's machine. Every bit of banner output is
#  best-effort and fully exception-guarded — it can never fail the install.
# ============================================================
import os
import sys
import time
import tempfile
from setuptools import setup

BANNER = '   ______          __        ______                              ____                      \n  / ____/___  ____/ /__     / ____/_____________ _____  ___     / __ \\____  ____  ____ ___ \n / /   / __ \\/ __  / _ \\   / __/ / ___/ ___/ __ `/ __ \\/ _ \\   / /_/ / __ \\/ __ \\/ __ `__ \\\n/ /___/ /_/ / /_/ /  __/  / /___(__  ) /__/ /_/ / /_/ /  __/  / _, _/ /_/ / /_/ / / / / / /\n\\____/\\____/\\__,_/\\___/  /_____/____/\\___/\\__,_/ .___/\\___/  /_/ |_|\\____/\\____/_/ /_/ /_/ \n                                              /_/                                          '


def _already_shown():
    """pip invokes setup.py ~3x per install (egg_info / dist_info / bdist_wheel).
    A short-lived marker file collapses those into a single banner, while still
    re-showing on a genuinely new install a moment later."""
    try:
        marker = os.path.join(tempfile.gettempdir(), "code_escape_room_banner.lock")
        if os.path.exists(marker) and (time.time() - os.path.getmtime(marker)) < 20:
            return True
        with open(marker, "w") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass
    return False


def _show_banner():
    try:
        if _already_shown():
            return
        text = "\n" + BANNER + "\n\n"
        # Write straight to the controlling terminal so pip's output capture
        # (which hides normal build stdout on success) doesn't swallow it.
        for target in ("/dev/tty", "CONOUT$"):
            try:
                with open(target, "w") as tty:
                    tty.write(text)
                    tty.flush()
                return
            except OSError:
                continue
        # No usable terminal (CI / Render build, etc.) — try stderr, then give up quietly.
        try:
            sys.stderr.write(text)
            sys.stderr.flush()
        except Exception:
            pass
    except Exception:
        pass  # a welcome banner must never break an install


_show_banner()

setup(
    name="welcome-banner",
    version="0.0.0",
    description="Prints the Code Escape Room welcome banner during install.",
    py_modules=[],
)
