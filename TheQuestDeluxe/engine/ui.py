"""Modal screens (overlays). Each takes keys and draws over the 640x480 frame."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

from . import rules
from .rules import SP_INT, SP_MANA
from .state import KNIGHT, MAGE, ROGUE, MONK
from .render import EGA, W, H, TILE

if TYPE_CHECKING:
    from .game import Game

CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER)
ARROWS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
PANEL = pygame.Rect(411, 0, 229, 400)


class Overlay:
    covers_map = False     # True for full-screen overlays

    def key(self, g: 'Game', ev) -> None: ...

    def draw(self, r, scr) -> None: ...

    def close(self, g: 'Game'):
        if g.overlay is self:
            g.overlay = None


# Fonts as the original sets them with settextstyle(font, 0, size)
GOTHIC = (4, 4)        # page titles
COMPLEX = (8, 2)       # character sheet labels
COMPLEX_S = (8, 1)     # character sheet values
SIMPLEX = (6, 2)       # story, menus
SIMPLEX_S = (6, 1)     # NPC talk
SCRIPT = (7, 2)        # the message strip
TRIPLEX = (1, 2)
ROM = (0, 1)           # the 8x8 ROM font


def panel(r, scr, title: str, x: int = 455):
    """The right-hand page: black, with a Gothic title at the top (spellbook(), inventory(), ...)."""
    pygame.draw.rect(scr, (0, 0, 0), PANEL)
    r.btext(scr, title, (x, 0), 15, GOTHIC)


def bottom(r, scr, lines: list[tuple[str, int]]):
    """The message strip: settextstyle(7, 0, 2) at (9, 413)."""
    pygame.draw.rect(scr, (0, 0, 0), (0, 411, W, 69))
    y = 413
    for s, col in lines[:3]:
        r.btext(scr, s, (9, y), col, SCRIPT)
        y += 22


# ── simple screens ────────────────────────────────────────────────────────────

class TextScreen(Overlay):
    covers_map = True

    def __init__(self, title: str, body: str, then: Callable | None = None, header: list[str] | None = None,
                 esc: Callable | None = None):
        self.title, self.body, self.then, self.header, self.esc = title, body, then, header or [], esc

    def key(self, g, ev):
        if ev.key == pygame.K_ESCAPE and self.esc:
            g.tones((500, 50), (600, 50))
            g.story_wipe()
            self.close(g)
            self.esc()
        elif ev.key in CONFIRM:                              # story(): Esc only leaves story 0
            g.tones((500, 50), (600, 50))                    # a chime as the page closes
            g.story_wipe()                                   # and the black circle
            self.close(g)
            if self.then:
                self.then()

    def draw(self, r, scr):
        """story(): light blue Simplex lines 30 pixels apart, then a yellow prompt. Story 1 opens with
        lines about the new character and starts its text 150 pixels down."""
        scr.fill((0, 0, 0))
        y = 0
        if self.title:
            r.btext(scr, self.title, (W // 2, 0), 15, GOTHIC, center=True)
            y = 60
        for n, line in enumerate(self.header):
            r.btext(scr, line, (0, 30 * n), 9, SIMPLEX)
        if self.header:
            y = 150
        for line in r.bwrap(self.body, 636, SIMPLEX):
            r.btext(scr, line, (0, y), 9, SIMPLEX)
            y += 30
        r.btext(scr, 'Press <Enter> to continue', (150, 440), 14, SIMPLEX)


class Dialog(Overlay):
    def __init__(self, speaker: str, text: str, then: Callable | None = None):
        self.speaker, self.text, self.then = speaker, text, then

    def key(self, g, ev):
        if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            self.close(g)
            if self.then:
                self.then()

    def draw(self, r, scr):
        """talk(): the NPC's words in the bottom strip, small Simplex, two lines at y 413 and 443."""
        lines = r.bwrap(self.text, 622, SIMPLEX_S)
        top = 413 - 30 * max(0, len(lines) - 2)
        if top < 413:
            pygame.draw.rect(scr, (0, 0, 0), (0, top - 2, W, 413 - top + 2))
        pygame.draw.rect(scr, (0, 0, 0), (0, 411, W, 69))
        y = top
        for n, line in enumerate(lines):
            r.btext(scr, line, (9 + (n > 0), y), 15, SIMPLEX_S)
            y += 30


def bgi_on(r, scr):
    g = r.bgi
    g.s = scr
    return g


# title(): the menu-cursor weapons, drawn beside the chosen box (from the original's own calls)
def _title_cursor(g, n):
    if n == 0:                                  # short sword
        g.setfillstyle(1, 0)
        g.bar(166, 220, 170, 211)
        g.bar(163, 210, 173, 211)
        g.setcolor(15)
        g.setfillstyle(1, 15)
        g.bar(166, 209, 170, 193)
        g.line(166, 193, 168, 185)
        g.line(170, 193, 168, 185)
        g.floodfill(168, 191, 15)
    elif n == 1:                                # mace
        g.setlinestyle(0, 0, 3)
        g.setcolor(0)
        g.line(168, 274, 168, 299)
        g.setlinestyle(0, 0, 1)
        g.setfillstyle(1, 0)
        g.fillellipse(168, 270, 7, 7)
        g.setcolor(7)
        g.setfillstyle(1, 7)
        for cx, cy in ((168, 270), (168, 263), (168, 277), (161, 270), (175, 270)):
            g.fillellipse(cx, cy, 1, 1)
    elif n == 2:                                # axe
        g.setcolor(0)
        g.setfillstyle(1, 0)
        g.bar(158, 378, 161, 349)
        g.setcolor(15)
        g.line(161, 349, 172, 343)
        g.line(172, 343, 172, 364)
        g.line(172, 364, 161, 353)
        g.line(161, 349, 161, 353)
        g.setfillstyle(1, 15)
        g.floodfill(168, 359, 15)
    else:                                       # rapier
        g.setcolor(0)
        g.setfillstyle(1, 0)
        g.bar(167, 452, 169, 460)
        g.line(168, 460, 168, 421)
        g.arc(168, 456, 0, 180, 5)


class TitleScreen(Overlay):
    """title() + mastermind(): the main menu. New Game, Load Game, Credits, Quit Game."""
    covers_map = True

    def __init__(self):
        self.i = 0
        self._bg = None

    def key(self, g, ev):
        if ev.key in (pygame.K_UP, pygame.K_DOWN):          # title(): the sword wraps around
            self.i = (self.i + (-1 if ev.key == pygame.K_UP else 1)) % 4
            g.tones((400, 50), (300, 50))
        elif ev.key == pygame.K_p and g.settings and len(g.pack_choices()) > 1:
            g.tones((600, 50), (700, 50))
            g.switch_pack()                                  # P: the next pack (Custom Maps), see pack_label
        elif ev.key in CONFIRM:
            g.tones((400, 50), (300, 50), (600, 50), (700, 50), (500, 50), (400, 50))
            self.close(g)
            if self.i == 0:
                g.new_game()
            elif self.i == 1:
                g.overlay = LoadScreen(g)
            elif self.i == 2:
                g.overlay = Credits(lambda: setattr(g, 'overlay', TitleScreen()))
            else:
                g.quit()

    def draw(self, r, scr):
        if self._bg is None:
            self._bg = pygame.Surface((W, H))
            g = bgi_on(r, self._bg)
            g.setfillstyle(1, 0)
            g.bar(0, 0, 640, 500)
            g.setfillstyle(10, 8)
            g.bar(0, 0, 640, 500)
            g.setcolor(15)
            g.setfillstyle(1, 0)
            g.bar3d(20, 15, 600, 145, 20, 1)
            g.setfillstyle(2, 0)
            g.floodfill(300, 5, 15)
            g.floodfill(610, 115, 15)
            g.settextstyle(4, 0, 20)
            g.setcolor(9)
            g.outtextxy(40, -15, 'The Quest')
            for top in (175, 255, 335, 415):
                g.setcolor(15)
                g.setfillstyle(1, 4)
                g.bar3d(150, top, 450, top + 57, 20, 1)
                g.setfillstyle(2, 4)
                g.floodfill(200, top - 10, 15)
                g.floodfill(460, top + 30, 15)
            g.settextstyle(4, 0, 6)
            g.setcolor(0)
            for label, y in (('New Game', 165), ('Load Game', 245), ('Credits', 325), ('Quit Game', 405)):
                g.outtextxy(185, y, label)
            g.settextstyle(4, 0, 3)
            g.setcolor(14)
            left = ['A path leads', 'toward the', 'unknown...', 'Will you', 'follow the ', 'path or get',
                    'lost on the', 'way?']
            right = ['The time has', 'come. The', 'journey awaits.', 'Are you ready', 'for Defeat or',
                     'Victory? Can', 'you complete', 'The Quest?']
            for k in range(8):
                g.outtextxy(10, 150 + 40 * k, left[k])
                g.outtextxy(480, 150 + 40 * k, right[k])
        scr.blit(self._bg, (0, 0))
        fixes = (getattr(r, 'game', None) and r.game.settings or {}).get('fixes')
        if fixes in ('on', 'off'):                    # the player's settings.ini, bottom left
            g = bgi_on(r, scr)
            g.settextstyle(0, 0, 1)
            g.setcolor(15)
            g.outtextxy(4, 470, f'Bug fixes: {fixes}')
        pack_label(r, scr)
        _title_cursor(bgi_on(r, scr), self.i)


def pack_label(r, scr):
    """Bottom right, when there are Custom Maps: which pack is in play, and P to change."""
    g = getattr(r, 'game', None)
    if g is None or not g.settings or len(g.pack_choices()) < 2:     # (a game made without settings, as the tests do, is as it was)
        return
    b = bgi_on(r, scr)
    b.settextstyle(0, 0, 1)
    b.setcolor(14)
    b.outtextxy(380, 470, f'Pack: {g.pack_name()}   (P: change pack)')


class LoadScreen(Overlay):
    """loadscreen(): 'Available Games', the saves 1, 2, ... up to the first empty or reserved slot,
    each with the hero's class and level. Up/Down move the yellow cross (with a click), Enter loads,
    Esc goes back to the title."""
    covers_map = True

    def __init__(self, g: 'Game'):
        self.games = g.slots.listing(all_=g.pack.fixed('load_gaps'))
        self.i = 1

    def key(self, g, ev):
        if ev.key == pygame.K_UP and self.i > 1:
            self.i -= 1
            g.tones((400, 50), (300, 50))
        elif ev.key == pygame.K_DOWN and self.i < len(self.games):
            self.i += 1
            g.tones((400, 50), (300, 50))
        elif ev.key in CONFIRM and self.games:
            self.close(g)
            g.tones((500, 50), (600, 50))
            g.status.level = 0                        # no 'Want to load?' from here
            g.status.saveslot = self.games[self.i - 1][0]
            g.load_game()
        elif ev.key == pygame.K_p and g.settings and len(g.pack_choices()) > 1:
            g.tones((600, 50), (700, 50))
            g.switch_pack()                          # the saves of the next pack: the load list opens again there
            g.reopen_load = True
        elif ev.key == pygame.K_ESCAPE:
            g.overlay = TitleScreen()

    def draw(self, r, scr):
        g = bgi_on(r, scr)
        g.setfillstyle(1, 0)
        g.bar(0, 0, 640, 500)
        g.setcolor(15)
        g.settextstyle(4, 0, 4)
        g.outtextxy(180, 0, 'Available Games')
        pack_label(r, scr)
        g.setcolor(9)
        g.settextstyle(6, 0, 2)
        for k, (n, level, htype) in enumerate(self.games, start=1):
            y = k * 20 + 30                            # the original's k is n: it stops at the first gap
            g.outtextxy(140, y, f'{n:2d}.')
            g.outtextxy(180, y, r.pack.class_name(htype))
            g.outtextxy(240, y, 'Level')
            g.outtextxy(295, y, f'{level:<2d}' if level < 10 else str(level))
        g.setlinestyle(0, 0, 3)
        g.setcolor(14)
        y = self.i * 20 + 3
        g.line(129, y + 38, 129, y + 50)
        g.line(123, y + 44, 135, y + 44)
        g.setlinestyle(0, 0, 1)


class Credits(Overlay):
    """credits(): a black square grows from the middle, then the credits wait for a key."""
    covers_map = True

    def __init__(self, then: Callable | None = None):
        self.then = then
        self.step = 0

    def key(self, g, ev):
        if self.step >= 330:
            self.close(g)
            if self.then:
                self.then()

    def draw(self, r, scr):
        g = bgi_on(r, scr)
        if self.step < 330:
            if self.step == 0:
                self._under = scr.copy()
            scr.blit(self._under, (0, 0))
            g.setfillstyle(1, 0)
            k = self.step
            g.bar(320 - k, 250 - k, 320 + k, 250 + k)
            self.step = min(330, self.step + 12)
            return
        g.setfillstyle(1, 0)
        g.bar(0, 0, 640, 500)
        g.settextstyle(4, 0, 8)
        g.setcolor(9)
        g.outtextxy(190, -15, 'Credits')
        heads = [(65, 'Game Creator and Programmer...'), (135, 'Beta Testing...'), (260, 'Inspiration...')]
        for y, t in heads:
            g.settextstyle(4, 0, 4)
            g.setcolor(5)
            g.outtextxy(0, y, t)
        g.setcolor(9)
        g.settextstyle(5, 0, 4)
        g.outtextxy(70, 95, 'Alex Kutsenok')
        g.outtextxy(70, 175, 'Canterbury High School Students')
        g.outtextxy(70, 215, 'Anya Kutsenok')
        g.settextstyle(5, 0, 3)
        g.outtextxy(70, 295, '"The Wheel of Time" by Robert Jordan')
        g.outtextxy(70, 335, 'Every RPG I have ever played')
        g.outtextxy(20, 375, '"We are not permitted to choose the frame of our destiny.')
        g.outtextxy(20, 415, 'But what we put into it is ours."   -Dag Hammarskjold')


class TalkBox(Overlay):
    """talk(): the message strip, small Simplex, two lines at (x, 413) and (x + 1, 443), exactly the
    strings the original builds (x is -3 for a one-line message: the original's quirk). Space closes."""

    def __init__(self, text, then: Callable | None = None):
        self.text, self.then = text, then

    def key(self, g, ev):
        if ev.key == pygame.K_SPACE:
            self.close(g)
            if self.then:
                self.then()

    def draw(self, r, scr):
        pygame.draw.rect(scr, (0, 0, 0), (0, 410, W, 70))
        if self.text is None:
            return                  # the original would hang searching Talk.dat
        s, ss, x = self.text
        r.btext(scr, s, (x, 413), 15, SIMPLEX_S)
        r.btext(scr, ss, (x + 1, 443), 15, SIMPLEX_S)


class Notice(Overlay):
    """A line in the message strip that waits for Space (death2(), cantsave(), ...)."""

    def __init__(self, text: str, colour: int = 15, then: Callable | None = None):
        self.t, self.colour, self.then = text, colour, then

    def key(self, g, ev):
        if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            self.close(g)
            if self.then:
                self.then()

    def draw(self, r, scr):
        bottom(r, scr, [(self.t, self.colour)])


class YesNo(Overlay):
    def __init__(self, question: str, on_yes, on_no=None):
        self.q, self.on_yes, self.on_no = question, on_yes, on_no

    """The original's '... (Y)es (N)o' questions in the message strip: only Y and N answer."""

    def key(self, g, ev):
        if ev.key == pygame.K_y:
            self.close(g)
            self.on_yes()
        elif ev.key == pygame.K_n:
            self.close(g)
            if self.on_no:
                self.on_no()

    def draw(self, r, scr):
        bottom(r, scr, [(self.q, 15)])


class Menu(Overlay):
    covers_map = True

    def __init__(self, title: str, options: list[tuple[str, Callable]], footer: str = '', cancel=None):
        self.title, self.options, self.footer, self.cancel = title, options, footer, cancel
        self.i = 0

    def key(self, g, ev):
        if ev.key == pygame.K_UP:
            self.i = (self.i - 1) % len(self.options)
        elif ev.key == pygame.K_DOWN:
            self.i = (self.i + 1) % len(self.options)
        elif ev.key in CONFIRM:
            self.close(g)
            self.options[self.i][1]()
        elif ev.key == pygame.K_ESCAPE and self.cancel:
            self.close(g)
            self.cancel()

    def draw(self, r, scr):
        """loadscreen(): a Gothic title and Simplex entries."""
        scr.fill((0, 0, 0))
        r.btext(scr, self.title, (W // 2, 20), 15, GOTHIC, center=True)
        for n, (label, _) in enumerate(self.options):
            r.btext(scr, label, (150, 110 + 40 * n), 14 if n == self.i else 7, SIMPLEX)
        if self.footer:
            r.btext(scr, self.footer, (W // 2, 440), 7, SIMPLEX, center=True)


def plus(r, scr, x, cy, colour=14):
    """creation()/levelup() cursor: a thick '+' 13 pixels across, centred on (x, cy)."""
    g = r.bgi
    g.s = scr
    g.setlinestyle(0, 0, 3)
    g.setcolor(colour)
    g.line(x, cy - 6, x, cy + 6)
    g.line(x - 6, cy, x + 6, cy)
    g.setlinestyle(0, 0, 1)


def creation_page(r, scr):
    scr.fill((0, 0, 0))
    r.btext(scr, 'Character Creation', (200, 0), 15, GOTHIC)


class Choice(Overlay):
    """A creation() page: up/down moves the '+', Enter picks (if allowed)."""
    covers_map = True
    count = 1

    def __init__(self):
        self.i = 1

    def allowed(self, i) -> bool:
        return True

    def pick(self, g, i): ...

    def key(self, g, ev):
        if ev.key == pygame.K_UP and self.i > 1:
            self.i -= 1
            g.tones((400, 50), (300, 50))
        elif ev.key == pygame.K_DOWN and self.i < self.count:
            self.i += 1
            g.tones((400, 50), (300, 50))
        elif ev.key in CONFIRM and self.allowed(self.i):      # a refused choice is silent
            g.tones((500, 50), (600, 50))
            self.close(g)
            self.pick(g, self.i)


class ClassSelect(Choice):
    """creation(), first page: the pack's classes, then the questionnaire."""

    def __init__(self, pack):
        super().__init__()
        self.pack = pack
        self.classes = list(pack.classes.values())
        self.count = len(self.classes) + 1

    def pick(self, g, i):
        g.overlay = Quiz(g) if i == self.count else SkillSelect(self.classes[i - 1]['id'], self.pack)

    def draw(self, r, scr):
        creation_page(r, scr)
        r.btext(scr, 'What class do you choose to play as?', (0, 40), 9, SIMPLEX)
        r.btext(scr, '                           Strength   Intelligence   Dexterity   Accuracy', (0, 70), 5, SIMPLEX)
        names = [c['name'] for c in self.classes] + ['Answer questions to determine class (recommended)']
        step = min(30, 330 // self.count)             # the original's 30; closer for a pack of many classes
        for n, name in enumerate(names):
            r.btext(scr, name, (150, 100 + step * n), 9, SIMPLEX)
        for n, c in enumerate(self.classes):
            row = '         '.join(f'{c[k]:<2}' for k in ('str', 'int', 'dex', 'acc'))
            r.btext(scr, row, (240, 100 + step * n), 9, SIMPLEX)
        r.btext(scr, 'Press <Enter> to continue', (150, 440), 14, SIMPLEX)
        plus(r, scr, 129, 100 + step * (self.i - 1) + 17)


class Quiz(Choice):
    """creation(): eight questions from qs.dat. Each answer scores 1000 (Knight), 100 (Mage),
    10 (Rogue) or 1 (Monk), and the largest digit of the total picks the class. The Quest Deluxe: an
    answer can instead score "class: points, ..." (e.g. "5: 1" for a pack's own class 5); then the
    class with the most points wins, a tie drawn at random between them."""
    count = 3

    def __init__(self, g):
        super().__init__()
        lines = g.data.src.text('qs.dat').splitlines()
        self.q = [lines[k:k + 9] for k in range(0, 72, 9)]
        self.n, self.total, self.result = 0, 0, 0
        self.points, self.own = {}, False

    def key(self, g, ev):
        if self.result:
            if ev.key in CONFIRM:
                self.close(g)
                g.overlay = SkillSelect(self.result, g.pack)
            return
        super().key(g, ev)

    def pick(self, g, i):
        score = self.q[self.n][2 + 2 * i]
        if ':' in score:
            self.own = True
            for part in score.split(','):
                if part.strip():
                    cls, pts = (int(v) for v in part.split(':'))
                    if cls in g.pack.classes:            # a class the pack doesn't have scores nothing
                        self.points[cls] = self.points.get(cls, 0) + pts
        else:
            self.total += int(score)
        g.overlay = self
        if self.n == 7:                              # shown over the last question
            if self.own:
                self.result = quiz_best(self.points, self.total)
            elif g.pack.fixed('quiz_ties'):
                self.result = quiz_best({}, self.total)
            else:
                self.result = quiz_class(self.total)
        else:
            self.n += 1
            self.i = 1

    def draw(self, r, scr):
        q = self.q[self.n]
        creation_page(r, scr)
        for text, y in zip((q[0], q[1], q[2], q[3], q[5], q[7]), (60, 90, 120, 160, 200, 240)):
            r.btext(scr, text, (50, y), 9, SIMPLEX)
        plus(r, scr, 37, self.i * 40 + 137)
        r.btext(scr, 'Press <Enter> to continue', (150, 440), 14, SIMPLEX)
        if self.result:
            r.btext(scr, f'You decided to become a {r.pack.class_name(self.result)}.', (50, 300), 9, SIMPLEX)


def quiz_class(total: int) -> int:
    """The original's tie-breaking, quirks included: a tie involving the Monk digit, or any three- or
    four-way tie, gives a Monk; Knight/Mage, Knight/Rogue and Mage/Rogue ties are a coin flip."""
    c1, c2, c3, c4 = total // 1000, total % 1000 // 100, total % 100 // 10, total % 10
    if c1 > c2 and c1 > c3 and c1 > c4:
        return KNIGHT
    if c2 > c1 and c2 > c3 and c2 > c4:
        return MAGE
    if c3 > c1 and c3 > c2 and c3 > c4:
        return ROGUE
    if c4 > c1 and c4 > c2 and c4 > c3:
        return MONK
    if c1 == c2 and c1 > c3 and c1 > c4:
        return rules.random(2) + 1
    if c1 == c3 and c1 > c2 and c1 > c4:
        return ROGUE if rules.random(2) + 1 == 2 else KNIGHT
    if c2 == c3 and c2 > c1 and c2 > c4:
        return rules.random(2) + 2
    return MONK


def quiz_best(points: dict, total: int) -> int:
    """The Quest Deluxe's questionnaire with a pack's own classes: the original's scores (1000 Knight,
    100 Mage, 10 Rogue, 1 Monk) count as points too, and the most points win; a tie is drawn at random."""
    points = dict(points)
    for cls, value in ((KNIGHT, 1000), (MAGE, 100), (ROGUE, 10), (MONK, 1)):
        if total // value % 10:
            points[cls] = points.get(cls, 0) + total // value % 10
    if not points:
        return MONK
    best = max(points.values())
    tied = sorted(c for c, v in points.items() if v == best)
    return tied[rules.random(len(tied))] if len(tied) > 1 else tied[0]


class SkillSelect(Choice):
    """creation(): choose one extra skill. A second '+' marks the class's own free skill, which can't be
    chosen again. A skill that only comes free with a class (Marksmanship) is only listed for that
    class and can never be chosen; a class's no_skill aren't offered either. The original leaves a hidden
    skill's row blank, and the '+' can still stop there; the "blank_rows" fix leaves the row out."""

    def __init__(self, cls, pack):
        super().__init__()
        self.cls, self.pack = cls, pack
        self.own = pack.classes[cls]['skill']
        self.hidden = pack.hidden_from(cls, 'skill')
        every = [pack.skill(s) for s in pack.skill_ids('skill')]
        self.rows = [n for n, s in enumerate(every)                 # which of them are rows here
                     if not (pack.fixed('blank_rows') and s['id'] in self.hidden)]
        self.skills = [every[n] for n in self.rows]
        self.count = len(self.skills)

    def allowed(self, i):
        s = self.skills[i - 1]
        return s['id'] != self.own and s['id'] not in self.hidden

    def pick(self, g, i):
        g.overlay = FaultSelect(self.cls, self.rows[i - 1] + 1, self.pack)

    def draw(self, r, scr):
        creation_page(r, scr)
        r.btext(scr, 'Choose a skill:', (50, 60), 9, SIMPLEX)
        for n, s in enumerate(self.skills):
            if s['id'] not in self.hidden:
                r.btext(scr, s['name'], (100, 100 + 40 * n), 9, SIMPLEX)
        own = next((n + 1 for n, s in enumerate(self.skills) if s['id'] == self.own), 0)
        plus(r, scr, 79, own * 40 + 77)
        plus(r, scr, 59, self.i * 40 + 77)
        r.btext(scr, 'Press <Enter> to continue', (150, 440), 14, SIMPLEX)


class FaultSelect(Choice):
    """creation(): choose a fault. Each class may forbid one (Knights can't be cowards, Mages can't be
    rash, Rogues can't be honorable); its name isn't drawn, but the original leaves its row, blank, for
    the '+' to stop on. The "blank_rows" fix leaves the row out."""

    def __init__(self, cls, skill, pack):
        super().__init__()
        self.cls, self.skill = cls, skill
        self.banned = pack.hidden_from(cls, 'fault')
        every = [pack.skill(s) for s in pack.skill_ids('fault')]
        self.rows = [n for n, f in enumerate(every) if not (pack.fixed('blank_rows') and f['id'] in self.banned)]
        self.faults = [every[n] for n in self.rows]
        self.count = len(self.faults)

    def allowed(self, i):
        return self.faults[i - 1]['id'] not in self.banned

    def pick(self, g, i):
        g.start_new(self.cls, self.skill, self.rows[i - 1] + 1)

    def draw(self, r, scr):
        creation_page(r, scr)
        r.btext(scr, 'Choose a fault:', (50, 60), 9, SIMPLEX)
        for n, f in enumerate(self.faults):
            if f['id'] not in self.banned:
                r.btext(scr, f['name'], (100, 100 + 40 * n), 9, SIMPLEX)
        plus(r, scr, 59, self.i * 40 + 77)
        r.btext(scr, 'Press <Enter> to continue', (150, 440), 14, SIMPLEX)


# ── map cursors ───────────────────────────────────────────────────────────────

class Cursor(Overlay):
    """Moves a highlight over the current screen; used for spell targets and ranged targets."""

    def __init__(self, g: 'Game', x: int, y: int, title: str, on_pick, allowed=None, can_pick=None,
                 on_cancel=None):
        self.x, self.y, self.title = x, y, title
        self.on_pick, self.allowed, self.can_pick, self.on_cancel = on_pick, allowed, can_pick, on_cancel
        g.cursor = (x, y)

    def key(self, g, ev):
        if ev.key in ARROWS:
            dx, dy = ARROWS[ev.key]
            nx, ny = self.x + dx, self.y + dy
            if g.world.in_room(nx, ny) and (self.allowed is None or self.allowed(nx, ny)):
                self.x, self.y = nx, ny
                g.cursor = (nx, ny)
        elif ev.key in CONFIRM + (pygame.K_TAB, pygame.K_SPACE):
            if self.can_pick is None or self.can_pick(self.x, self.y):
                self.close(g)
                g.cursor = None
                self.on_pick(self.x, self.y)
        elif ev.key == pygame.K_ESCAPE:
            self.close(g)
            g.cursor = None
            if self.on_cancel:
                self.on_cancel()

    def draw(self, r, scr):
        bottom(r, scr, [(self.title, 14), ('Arrows move, Enter selects, Esc cancels', 7)])


# ── spell book ────────────────────────────────────────────────────────────────

class SpellBook(Overlay):
    """spellbook(): browse the 2x10 book, cast with Enter, bind F1-F9 by pressing the key. A pack with
    more than 20 spells has more pages: Left and Right go on from column to column, page to page."""

    def __init__(self, g: 'Game'):
        self.i = 0

    def spell(self, g):
        return g.player.book[self.i]

    def key(self, g, ev):
        if ev.key == pygame.K_UP:
            self.i = self.i - 1 if self.i % 10 else self.i
        elif ev.key == pygame.K_DOWN:
            self.i = self.i + 1 if self.i % 10 != 9 else self.i
        elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            size = len(g.player.book)                # 20 in Quest I: either key flips the column
            self.i = (self.i + (10 if ev.key == pygame.K_RIGHT else -10)) % size
        elif pygame.K_F1 <= ev.key <= pygame.K_F9:
            s = self.spell(g)
            if s:
                n = ev.key - pygame.K_F1 + 1
                fk = g.player.fkey
                for k in range(1, 10):
                    if fk[k] == s:
                        fk[k] = 0
                fk[n] = s
        elif ev.key in CONFIRM:
            s = self.spell(g)
            if s:
                self.close(g)
                g.begin_cast(s)
        elif ev.key in (pygame.K_ESCAPE, pygame.K_s):
            self.close(g)

    def draw(self, r, scr):
        """spellbook() + dispfkey(): two columns of ten spells 42 pixels apart. Mana cost in blue (red if
        you lack the mana), intelligence needed in white (red if too high), a magenta F-key label beside
        bound spells, a yellow countdown on spells still being learnt, and the name in the strip below."""
        g = r.game
        p = g.player
        pygame.draw.rect(scr, (0, 0, 0), PANEL)
        pygame.draw.rect(scr, (0, 0, 0), (0, 411, W, 69))
        r.btext(scr, 'Spell Book', (455, 0), 15, GOTHIC)
        page, pages = self.i // 20, len(p.book) // 20
        if pages > 1:
            r.btext(scr, f'Page {page + 1} of {pages}  (Left/Right)', (412, 470), 7, ROM)
        for n in range(20):
            col, row = divmod(n, 10)
            b = 108 * col
            x, y = 440 + b, 45 + 42 * row
            s = p.book[page * 20 + n]
            if s:
                fk = next((k for k in range(1, 10) if p.fkey[k] == s), 0)
                if fk:
                    r.btext(scr, f'F{fk}', (b + 415, 42 * row + 50), 5, (1, 3))
                if p.spells[s] == 1:
                    icon = r.sprites.get('spell', s)
                    if icon:
                        scr.blit(icon, (x, y))
                elif p.spells[s] > 1:
                    r.btext(scr, str(p.spells[s] - 1), (b + 471, 42 * row + 46), 14, ROM)
                mana = g.spells.tell(s, SP_MANA)
                req = g.spells.tell(s, SP_INT)
                r.btext(scr, str(mana), (b + 485, 42 * row + 42), 4 if mana > p.hero.mana else 9, TRIPLEX)
                r.btext(scr, str(req), (b + 485, 42 * row + 62), 4 if req > p.hero.intl else 15, TRIPLEX)
            if page * 20 + n == self.i:
                pygame.draw.rect(scr, EGA[14], (x - 1, y - 1, 42, 42), 2)
        s = p.book[self.i]
        if s:
            r.btext(scr, r.pack.spell_name(s), (1, 422), 4 if g.spells.tell(s, SP_INT) > p.hero.intl else 1, (1, 4))


class LearnSpell(Overlay):
    """After a level-up: choose one new spell to start memorising (spellbook() with lvup=1)."""

    def __init__(self, candidates: list[int], then: Callable):
        self.c, self.i, self.then = candidates, 0, then

    def key(self, g, ev):
        if ev.key == pygame.K_UP:
            self.i = (self.i - 1) % len(self.c)
        elif ev.key == pygame.K_DOWN:
            self.i = (self.i + 1) % len(self.c)
        elif ev.key in CONFIRM:
            self.close(g)
            g.learn_spell(self.c[self.i])
            self.then()
        elif ev.key == pygame.K_ESCAPE:
            self.close(g)
            self.then()

    def draw(self, r, scr):
        g = r.game
        panel(r, scr, 'New Spell')
        first = 0 if len(self.c) <= 20 else max(0, min(self.i - 6, len(self.c) - 12))   # a long list scrolls
        shown = self.c if len(self.c) <= 20 else self.c[first:first + 12]
        for n, s in enumerate(shown):
            r.btext(scr, r.pack.spell_name(s), (420, 50 + n * 28), 14 if first + n == self.i else 7, TRIPLEX)
        takes = 2 if g.player.skill.mem == 1 else 3
        bottom(r, scr, [(f'Choose a spell to memorise (takes {takes} level-ups).', 14),
                        ('Enter chooses, Esc skips', 7)])


# ── level up / character ──────────────────────────────────────────────────────

STAT_LABELS = ['Strength', 'Intelligence', 'Dexterity', 'Accuracy']


def rep_word(rep: int) -> str:
    if rep <= -4:
        return 'Evil'
    if rep < 0:
        return 'Indecent'
    if rep == 0:
        return 'Neutral'
    if rep < 4:
        return 'Virtuous'
    if rep < 6:
        return 'Honored'
    return 'Heroic'


def draw_sheet(r, scr, g, title: str, cursor: int | None = None, gained=()):
    """character2() / levelup(): the stat page, laid out exactly as the original."""
    p, h, sk = g.player, g.player.hero, g.player.skill
    pygame.draw.rect(scr, (0, 0, 0), (411, 0, 229, 480))
    pygame.draw.rect(scr, (0, 0, 0), (0, 411, 400, 69))
    r.btext(scr, title, (475, 0), 15, GOTHIC)
    # skills and faults along the bottom
    r.btext(scr, 'Skills:', (5, 430), 14, COMPLEX)
    for n, (name, have) in enumerate((('Ambidexterity', sk.amb), ('Bargaining', sk.bar), ('Scholar', sk.sch),
                                      ('Memorization', sk.mem), ('Marksmanship', sk.mar))):
        if have == 1:
            r.btext(scr, name, (90, 415 + 13 * n), 14, ROM)
    r.btext(scr, 'Faults:', (205, 430), 4, COMPLEX)
    colour = 4
    cowering = sk.cow == 1 and h.mlife and h.life / h.mlife <= 0.3
    if sk.cow == 1:
        r.btext(scr, 'Cowardice', (290, 415), 12 if cowering else colour, ROM)
        if cowering and not g.pack.fixed('fault_colours'):
            colour = 14                      # the original leaves the colour at yellow here
    if sk.hon == 1:
        r.btext(scr, 'Honor', (290, 428), colour, ROM)
    elif sk.hon > 1:
        r.btext(scr, 'Honor', (290, 428), 12, ROM)
        colour = 4
    if sk.ras >= 1:
        r.btext(scr, 'Rashness', (290, 441), colour, ROM)
    # labels
    labels = [('Strength', 9), ('Intelligence', 9), ('Dexterity', 9), ('Accuracy', 9), ('Power', 5),
              ('W Armor', 5), ('M Armor', 5), ('Attack', 5), ('Defense', 5), ('Life', 3), ('Mana', 3),
              ('Reputation', 14), ('Exp Needed', 14), ('Level', 14)]
    for n, (label, col) in enumerate(labels):
        r.btext(scr, label, (420, 42 + 31 * n), col, COMPLEX)
    # values (2 pixels lower, smaller font)
    row = lambda n: 44 + 31 * n
    for n, (base, now) in enumerate(((h.bstr, h.str), (h.bintl, h.intl), (h.bdex, h.dex), (h.bacc, h.acc))):
        if cursor is not None:
            col = 5 if (n + 1) in gained else 15     # levelup(): raised stats in magenta
            val = now
        else:
            col = 15 if now == base else (2 if now > base else 4)
            val = now
        r.btext(scr, str(val), (570, row(n)), col, COMPLEX_S)
    for n, val in ((4, h.power), (5, h.warm), (6, h.marm)):
        r.btext(scr, str(val), (570, row(n)), 15, COMPLEX_S)
    r.btext(scr, f'{h.atk}%', (570, row(7)), 4 if cowering else 15, COMPLEX_S)
    r.btext(scr, f'{h.defense}%', (570, row(8)), 15, COMPLEX_S)
    r.btext(scr, f'{h.life}/{h.mlife}', (535, row(9)), 15, COMPLEX_S)
    r.btext(scr, f'{h.mana}/{h.mmana}', (535, row(10)), 15, COMPLEX_S)
    r.btext(scr, rep_word(h.rep), (550, row(11)), 2 if h.rep >= 0 else 4, COMPLEX_S)
    r.btext(scr, str(h.exper), (570, row(12)), 15, COMPLEX_S)
    r.btext(scr, str(h.level), (570, row(13)), 15, COMPLEX_S)
    if cursor is not None:
        # levelup(): a thick yellow "+" beside the stat being chosen
        g2 = r.bgi
        g2.s = scr
        g2.setlinestyle(0, 0, 3)
        g2.setcolor(14)
        cy = 31 * cursor + 14
        g2.line(614, cy + 38, 614, cy + 50)
        g2.line(608, cy + 44, 620, cy + 44)
        g2.setlinestyle(0, 0, 1)


class LevelUpScreen(Overlay):
    def __init__(self, g: 'Game', gained: list[int], picks: int, then: Callable):
        self.gained, self.picks, self.then, self.i = gained, picks, then, 0

    def key(self, g, ev):
        if ev.key == pygame.K_UP:
            self.i = max(0, self.i - 1)
        elif ev.key == pygame.K_DOWN:
            self.i = min(3, self.i + 1)
        elif ev.key in CONFIRM:
            rules.apply_stat_point(g.player.hero, self.i + 1)
            self.gained = list(self.gained) + [self.i + 1]
            rules.status_update(g.player, g.status, g.items)
            self.picks -= 1
            g.tones((400, 50), (500, 50))
            if self.picks <= 0:
                self.then()                   # a class change is announced over this page
                self.close(g)

    def draw(self, r, scr):
        draw_sheet(r, scr, r.game, 'Level Up', cursor=self.i, gained=self.gained)


class CharacterSheet(Overlay):
    def key(self, g, ev):
        if ev.key in (pygame.K_ESCAPE, pygame.K_c, pygame.K_SPACE) + CONFIRM:
            self.close(g)

    def draw(self, r, scr):
        draw_sheet(r, scr, r.game, 'Character')


# ── inventory & shops ─────────────────────────────────────────────────────────

# pygame keys -> what the original's getch() returns (the arrows come as 0 and a scan code)
GETCH = {pygame.K_UP: [0, 72], pygame.K_DOWN: [0, 80], pygame.K_LEFT: [0, 75], pygame.K_RIGHT: [0, 77],
         pygame.K_KP8: [0, 72], pygame.K_KP2: [0, 80], pygame.K_KP4: [0, 75], pygame.K_KP6: [0, 77],
         pygame.K_RETURN: [13], pygame.K_KP_ENTER: [13], pygame.K_ESCAPE: [27], pygame.K_BACKSPACE: [8]}


def getch_codes(ev) -> list[int]:
    if ev.key in GETCH:
        return GETCH[ev.key]
    ch = getattr(ev, 'unicode', '') or ''
    if len(ch) == 1 and ord(ch) < 128:
        return [ord(ch)]
    return []


class Page(Overlay):
    """One of the original's own key loops (engine.invshop): the generator draws on its own copy of
    the screen and waits for keys; when it returns, then(key it returned) runs."""
    covers_map = True

    def __init__(self, g: 'Game', layer: pygame.Surface, gen, then: Callable):
        self.layer, self.gen, self.then = layer, gen, then
        self.done = False
        self._run(g, None)

    def _run(self, g, key):
        try:
            v = self.gen.send(key) if key is not None else next(self.gen)
            while v is not None:                       # a delay() inside a tone
                g.renderer.wait(self.layer, v, fast=g.fast)
                v = next(self.gen)
        except StopIteration as stop:
            self.done = True
            g.speaker.nosound()
            self.close(g)
            self.then(stop.value)

    def key(self, g, ev):
        for code in getch_codes(ev):
            if self.done:
                return
            self._run(g, code)

    def draw(self, r, scr):
        scr.blit(self.layer, (0, 0))
