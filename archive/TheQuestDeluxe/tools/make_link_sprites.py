"""Draws the five starter pictures for the level links (ladder, rope, stairs, hole, jump pad) into
packs/TheQuest/sprites/items/ and lists them in its items.json. They are plain placeholders in the
16 EGA colours, to be painted over in the editor.

    python tools/make_link_sprites.py
"""
from __future__ import annotations

import json
import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(os.path.dirname(HERE), 'packs', 'TheQuest')
EGA = [(0, 0, 0), (0, 0, 168), (0, 168, 0), (0, 168, 168), (168, 0, 0), (168, 0, 168), (168, 84, 0),
       (168, 168, 168), (84, 84, 84), (84, 84, 252), (84, 252, 84), (84, 252, 252), (252, 84, 84),
       (252, 84, 252), (252, 252, 84), (252, 252, 252)]
BROWN, GREY, DARK, WHITE, YELLOW, BLACK = EGA[6], EGA[7], EGA[8], EGA[15], EGA[14], EGA[0]

ITEMS = [(1101, 'Ladder', 'ladder'), (1102, 'Rope', 'rope'), (1103, 'Stairs', 'stairs'), (1104, 'Hole', 'hole'),
         (1105, 'Jump Pad', 'jump_pad')]


def canvas() -> pygame.Surface:
    s = pygame.Surface((40, 40), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def ladder():
    s = canvas()
    for x in (11, 27):                                   # two rails
        pygame.draw.rect(s, BROWN, (x, 2, 3, 37))
        pygame.draw.line(s, EGA[14], (x, 2), (x, 38))
    for y in range(6, 38, 6):                            # the rungs
        pygame.draw.rect(s, BROWN, (11, y, 19, 2))
        pygame.draw.line(s, BLACK, (11, y + 2), (29, y + 2))
    return s


def rope():
    s = canvas()
    pygame.draw.circle(s, DARK, (20, 5), 4, 2)           # the hook it hangs from
    for y in range(8, 38):
        x = 20 + (2 if (y // 3) % 2 else -2)             # a twisted strand
        pygame.draw.rect(s, EGA[14] if (y // 3) % 2 else BROWN, (x - 1, y, 3, 1))
        pygame.draw.rect(s, BROWN, (20 - (x - 20) - 1, y, 3, 1))
    pygame.draw.rect(s, BROWN, (18, 36, 5, 3))           # the knot at the bottom
    return s


def stairs():
    s = canvas()
    for i in range(6):                                   # steps seen from above, going down into the dark
        shade = (WHITE, GREY, GREY, DARK, DARK, BLACK)[i]
        pygame.draw.rect(s, shade, (4, 4 + i * 6, 32, 6))
        pygame.draw.line(s, BLACK, (4, 4 + i * 6 + 5), (35, 4 + i * 6 + 5))
    pygame.draw.rect(s, EGA[6], (2, 3, 2, 36))
    pygame.draw.rect(s, EGA[6], (36, 3, 2, 36))
    return s


def hole():
    s = canvas()
    pygame.draw.ellipse(s, BROWN, (3, 8, 34, 26))
    pygame.draw.ellipse(s, BLACK, (6, 11, 28, 20))
    pygame.draw.ellipse(s, DARK, (10, 15, 20, 12), 1)
    return s


def jump_pad():
    s = canvas()
    pygame.draw.ellipse(s, EGA[3], (3, 14, 34, 20))
    pygame.draw.ellipse(s, EGA[11], (6, 16, 28, 14))
    pygame.draw.polygon(s, YELLOW, [(20, 3), (28, 15), (23, 15), (23, 21), (17, 21), (17, 15), (12, 15)])
    pygame.draw.polygon(s, BLACK, [(20, 3), (28, 15), (23, 15), (23, 21), (17, 21), (17, 15), (12, 15)], 1)
    return s


DRAW = {'ladder': ladder, 'rope': rope, 'stairs': stairs, 'hole': hole, 'jump_pad': jump_pad}


def main():
    pygame.init()
    folder = os.path.join(PACK, 'sprites', 'items')
    for v, name, kind in ITEMS:
        pygame.image.save(DRAW[kind](), os.path.join(folder, f'{v}.png'))
    path = os.path.join(PACK, 'items.json')
    text = open(path, encoding='utf-8').read()
    have = {r['id'] for r in json.loads(text)['items']}
    new = [f' {{"id": {v}, "name": "{name}", "type": "{kind}"}}' for v, name, kind in ITEMS if v not in have]
    if new:
        end = text.rindex('\n ]')
        text = text[:end] + ',\n' + ',\n'.join(new) + text[end:]
        open(path, 'w', encoding='utf-8', newline='').write(text)
    print(f'{len(new)} items added, {len(ITEMS)} pictures drawn')


if __name__ == '__main__':
    main()
