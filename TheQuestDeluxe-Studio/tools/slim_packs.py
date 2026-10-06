"""Make packs hold only their own pictures (the rest come from the locked game, packs/TheQuest).

    python tools/slim_packs.py                      every pack in Custom Maps
    python tools/slim_packs.py "Custom Maps/Jonos Pack"

A picture that is exactly the locked game's is removed from the pack (it is not lost: the game and the Studio find it in
packs/TheQuest); pictures the pack changed or added stay. Safe to run again. "Send my edits" and the zips of every Save keep
copies, and a pack's own folder is the only thing it changes."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import custom  # noqa: E402
from engine import pack  # noqa: E402


def main(argv):
    folders = argv or [os.path.join(pack.CUSTOM_DIR, n) for n in pack.custom_packs()]
    for f in folders:
        kept, removed = custom.slim(f)
        print(f'{os.path.basename(f)}: {removed} pictures the same as the locked game taken out, {kept} of its own kept')


if __name__ == '__main__':
    main(sys.argv[1:])
