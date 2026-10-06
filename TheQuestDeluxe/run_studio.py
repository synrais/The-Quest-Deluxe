"""The Quest Studio — the editor for The Quest Deluxe quests (a rebuild of run_editor.py).

    python run_studio.py                 opens the quest you had open last (asks the first time)
    python run_studio.py --pack mypack   opens Custom Maps/mypack (or any pack folder)
    python run_studio.py --choose        asks which quest

Needs Python 3.10+ with tkinter (the python.org installer includes it) and pygame-ce.
"""
import sys

if __name__ == '__main__':
    from studio.app import Studio, main
    import tkinter as tk
    pack = None
    if '--pack' in sys.argv:
        pack = sys.argv[sys.argv.index('--pack') + 1]
        from editor import custom
        import os
        if not os.path.isdir(pack):
            pack = custom.pack_dir(pack)
    from studio import theme
    theme.make_dpi_aware()
    root = tk.Tk()
    app = Studio(root, pack)
    if not app.closed:
        root.mainloop()
