"""The Quest Studio: the editor for The Quest Deluxe quests.

    python run_studio.py                 opens the quest you had open last (asks the first time)
    python run_studio.py --pack mypack   opens Custom Maps/mypack (or any pack folder)
    python run_studio.py --choose        asks which quest

Needs Python 3.10+ with tkinter (the python.org installer includes it) and pygame-ce.
"""
import os
import sys


def main():
    pack = None
    if '--pack' in sys.argv:
        pack = sys.argv[sys.argv.index('--pack') + 1]
        if not os.path.isdir(pack):
            from core import custom
            pack = custom.pack_dir(pack)
    import tkinter as tk
    from studio import theme
    from studio.app import Studio
    theme.make_dpi_aware()
    root = tk.Tk()
    app = Studio(root, pack)
    if not app.closed:
        root.mainloop()


if __name__ == '__main__':
    main()
