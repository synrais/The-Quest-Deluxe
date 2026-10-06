"""The Quest Deluxe Editor — makes and changes quest packs for The Quest Deluxe.

    python run_editor.py                 opens the pack you had open last (packs/TheQuest the first time)
    python run_editor.py --pack mypack   opens packs/mypack (or any pack folder)

Needs Python 3.10+ with tkinter (the python.org installer includes it) and pygame-ce.
"""
from editor.app import main

if __name__ == '__main__':
    main()
