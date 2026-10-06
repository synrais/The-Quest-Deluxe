"""Programs started without a terminal window (the launchers use pythonw): if one stops with an error there is no console to read it in, so the
error is written to a file in the user's folder and shown in a box."""
from __future__ import annotations

import os
import sys
import traceback


def guard(main, name: str):
    """Run main(); an error is saved to ~/.quest_<name>_log.txt and shown, and the exit code is 1."""
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as e:                                   # noqa: BLE001
        text = traceback.format_exc()
        path = os.path.join(os.path.expanduser('~'), f'.quest_{name}_log.txt')
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(text)
        except OSError:
            pass
        try:
            import tkinter
            from tkinter import messagebox
            root = tkinter.Tk()
            root.withdraw()
            messagebox.showerror('The Quest', f'It stopped with an error: {e}\n\nThe details are in {path}')
            root.destroy()
        except Exception:                                        # noqa: BLE001
            print(text, file=sys.stderr)
        return 1
