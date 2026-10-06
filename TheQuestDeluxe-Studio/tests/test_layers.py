"""Packs that hold only their own pictures: the rest come from the locked game (quest.json "base").   xvfb-run python tests/test_layers.py

Everything is done on copies in a temporary folder."""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp

import pygame  # noqa: E402

import core.custom as custom  # noqa: E402
import engine.pack as enginepack  # noqa: E402
from core import pack_edits  # noqa: E402
from core.project import Project  # noqa: E402
from engine import render  # noqa: E402

custom_dir = os.path.join(tmp, 'Custom Maps')
enginepack.CUSTOM_DIR = custom.CUSTOM_DIR = custom_dir
pygame.init()
pygame.display.set_mode((64, 64))


def pictures(pack):
    """Every picture the game would draw for the pack: {(kind, n): bytes}."""
    s = render.Sprites(pack)
    out = {k: pygame.image.tobytes(v, 'RGBA') for k, v in s.images.items()}
    out.update({('bag', n): pygame.image.tobytes(v, 'RGBA') for n, v in s.bag.items()})
    out.update({('hero', n): pygame.image.tobytes(v, 'RGBA') for n, v in s.hero.items()})
    return out


def main():
    shipped = enginepack.DEFAULT_PACK
    # a new pack holds no pictures of the locked game: only the marker, and it still shows them all
    new = custom.create('Layered Test')
    assert not os.path.exists(os.path.join(new, 'sprites')), 'a new pack has no copy of the locked game\'s pictures'
    assert Project(new).quest['base'] == 'TheQuest'
    assert pictures(enginepack.Pack(new)) == pictures(enginepack.Pack(shipped)), 'the game draws the same pictures'
    size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(new) for f in fs)
    assert size < 2 * 10 ** 6, size

    # the Studio's model: own pictures over the base's, a delete hides the base's with an empty file, undo of it works
    p = Project(new)
    assert p.picture_ids('creatures') == Project(shipped).picture_ids('creatures')
    assert p.picture('creatures', 1) is not None and p.sprite('mon', 1) == os.path.join(shipped, 'sprites', 'creatures', '1.png')
    mine = pygame.Surface((40, 40), pygame.SRCALPHA)
    mine.fill((250, 10, 10, 255))
    p.set_picture('creatures', 1, mine)
    p.set_picture('creatures', 2, None)
    p.dirty.add('pictures')
    p.save()
    assert os.path.getsize(os.path.join(new, 'sprites', 'creatures', '1.png')) > 0
    assert os.path.exists(os.path.join(new, 'sprites', 'creatures', '2.png')) and os.path.getsize(os.path.join(new, 'sprites', 'creatures', '2.png')) == 0
    q = Project(new)
    assert 2 not in q.picture_ids('creatures') and 1 in q.picture_ids('creatures') and q.picture('creatures', 2) is None
    assert q.picture('creatures', 1).get_at((5, 5))[:3] == (250, 10, 10)
    game = pictures(enginepack.Pack(new))
    assert ('enemy', 2) not in game and game[('enemy', 1)] != pictures(enginepack.Pack(shipped))[('enemy', 1)]
    assert ('enemy', 3) in game, 'the rest still come from the locked game'

    # the report says what the pack made, and does not call the missing pictures removed
    deluxe = os.path.join(tmp, 'game')
    os.makedirs(os.path.join(deluxe, 'Custom Maps'))
    shutil.copytree(shipped, os.path.join(deluxe, 'packs', 'TheQuest'))
    shutil.copytree(new, os.path.join(deluxe, 'Custom Maps', 'Layered Test'))
    files, report = pack_edits.gather(deluxe)
    mine_files = sorted(a for _, a in files)
    assert any(a.endswith('sprites/creatures/1.png') for a in mine_files) and 'removed: sprites' not in report, report[:600]

    # a complete (old) pack is slimmed: same pictures drawn, nothing of its own lost
    old = os.path.join(custom_dir, 'Old Full')
    shutil.copytree(shipped, old)
    odd = pygame.Surface((40, 40), pygame.SRCALPHA)
    odd.fill((10, 200, 10, 255))
    pygame.image.save(odd, os.path.join(old, 'sprites', 'items', '1.png'))
    before = pictures(enginepack.Pack(old))
    kept, removed = custom.slim(old)
    assert kept == 1 and removed > 400, (kept, removed)
    assert pictures(enginepack.Pack(old)) == before, 'slimmed: the game draws exactly the same'
    assert custom.slim(old)[1] == 0, 'again: nothing more to do'
    print('layered packs: a new pack holds no copy of the locked game\'s pictures, draws all of them, own pictures win, a delete hides one, '
          'old packs slim without changing a pixel: ok')


if __name__ == '__main__':
    main()
