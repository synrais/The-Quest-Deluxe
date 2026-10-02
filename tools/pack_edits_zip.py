"""Packs what was added in the editor into a dated zip beside the game folders (run by "Make Edits Zip.bat").

    python tools/pack_edits_zip.py [--all] [--note ...] [--baseline]

The work is done by TheQuestDeluxe/editor/pack_edits.py, which the editor's "Send my edits..." button uses too.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'TheQuestDeluxe'))
from editor.pack_edits import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
