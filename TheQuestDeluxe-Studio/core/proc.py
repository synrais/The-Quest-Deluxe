"""Starting programs from the Studio without a terminal window appearing (Windows opens one for every console program unless told not to)."""
from __future__ import annotations

import sys

NO_WINDOW = 0x08000000                                           # CREATE_NO_WINDOW


def quiet() -> dict:
    """Extra arguments for subprocess.run / Popen: no console window on Windows, nothing on other systems."""
    return {'creationflags': NO_WINDOW} if sys.platform.startswith('win') else {}
