"""Main game: input handling and turn processing (port of main2()).

Keys (as in the original):
  arrows / numpad   move, attack, open doors, talk
  Enter             pick up          1-8        drink potion
  Space             shoot nearest    Tab        choose a ranged target
  s                 spell book       F1-F9      cast bound spell
  i                 inventory        c          character sheet
  k                 killer switch    v / Home   save      l / Insert  load
  Esc               quit to the title (asks first)
"""
from __future__ import annotations

import os
from dataclasses import asdict

import pygame

from .formats import GameData, Square, MAP_SIZE
from .state import (Status, Player, Hero, Inventory, Skills, new_player, POTION_FIELDS, KNIGHT, Enemy,
                    potions, add_potions, has_key, give_key)
from .world import World, screen_of, room_origin
from .savefile import SaveData, Slots
from . import savefile
from . import rules
from .rules import SP_RANGE, SP_INT
from .combat import Combat
from .magic import Magic
from .ai import monsmove
from .events import Events
from .render import Renderer, TILE
from .speaker import Speaker, sound_setting
from .settings import fix_override
from .hands import attack_kind
from . import anim
from . import invshop
from . import ui
from . import view3d

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIRS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
        pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0), pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1)}
FACES = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}
TURNS = {pygame.K_LEFT: -1, pygame.K_KP4: -1, pygame.K_RIGHT: 1, pygame.K_KP6: 1}      # FPS mode
STRAFE = {pygame.K_COMMA: -1, pygame.K_q: -1, pygame.K_PERIOD: 1, pygame.K_e: 1}     # FPS mode: step sideways


class ScreenHost(anim.Host):
    """Where the original's animations draw in the game: the real screen, the speaker, and the
    renderer's tiles for clean2()/guy2() (1-based screen squares)."""

    def __init__(self, game):
        super().__init__(game.renderer.bgi)
        self.game = game
        self.on_move = None

    def asound(self, freq):
        self.game.speaker.sound(freq)

    def nosound(self):
        self.game.speaker.nosound()

    def clean2(self, x, y):
        w, r = self.game.world, self.game.renderer
        ox, oy = w.origin
        r.draw_tile(r.screen, (x - 1) * TILE, (y - 1) * TILE, w.grid[ox + x - 1][oy + y - 1],
                    on_top=r.on_top(self.game))

    def guy2(self, x, y):
        r = self.game.renderer
        r.draw_hero(r.screen, self.game, (x - 1) * TILE, (y - 1) * TILE)

    def move_hero(self, x, y):
        if self.on_move:
            self.on_move(x, y)


class PageHost:
    """What the inventory and shop pages (engine.invshop) work on: the player's own bag, gold and
    potions, a copy of the hero (the original passes it by value), and a BGI on the page's surface."""

    def __init__(self, game, layer, store):
        from dataclasses import replace
        from .bgi import BGI
        self.game = game
        p = game.player
        self.g = BGI(layer, game.data.src)
        self.g._fonts = game.renderer.bgi._fonts
        self.layer = layer
        self.bag, self.store, self.inv, self.skill, self.more = p.bag, store, p.inv, p.skill, p.more
        self.hero = replace(p.hero)
        self.level = game.world.level
        self.tell = game.items.tell
        self.pack = game.pack
        self._prices = {r[0]: r[1] for r in game.data.prices if len(r) > 1}
        self.recompute()

    def price(self, it):
        return self._prices.get(it, 0)

    def recompute(self):
        tmp = Player(hero=self.hero, inv=self.inv, skill=self.skill)
        tmp.bag = self.bag
        rules.status_update(tmp, self.game.status, self.game.items)

    def asound(self, f):
        self.game.speaker.sound(f)

    def nosound(self):
        self.game.speaker.nosound()

    def bagdraw(self, i, ii, a):
        it = (self.store if a == 2 else self.bag).get((i, ii), 0)
        img = self.game.renderer.sprites.bag.get(it) if it else None
        if img:
            self.layer.blit(img, invshop.icon_pos(i, ii, a))

    def put3(self, it):
        """put3(): drop the item at the hero's square (or the nearest free one) and redraw it."""
        g, p = self.game, self.game.player
        g.put_item(p.X, p.Y, it)
        r = g.renderer
        ox, oy = g.world.origin
        for x, y in g.world.room_tiles():
            r.draw_tile(self.layer, (x - ox) * TILE, (y - oy) * TILE, g.world.grid[x][y])
        r.draw_hero(self.layer, g, (p.X - ox) * TILE, (p.Y - oy) * TILE)


class Msg(str):
    """A message line with its BGI colour (the game prints most in white, some in red/green)."""

    def __new__(cls, text: str, colour: int = 15):
        m = super().__new__(cls, text)
        m.colour = colour
        return m


class Game:
    def __init__(self, window, data: GameData | None = None, start_level: int = 1, settings: dict | None = None):
        self.data = data or GameData.load()
        self.pack = self.data.src.pack
        # the player's settings.ini (run_deluxe.py); without them, the pack plays as it is
        self.settings = settings or {}
        self.pack.fix_override = fix_override(settings)
        self.items = rules.ItemTable(self.data.items, self.pack)
        self.spells = rules.SpellTable(self.data.spells)
        self.rewards = self.pack.rewards()
        self.renderer = Renderer(window, self.data.src, self.pack)
        # saves/<pack>/save01.dat .. save20.dat: the original's format, kept apart from the classic port's
        self.slots = Slots(os.path.join(ROOT, 'saves', os.path.basename(self.pack.root)))
        # scripted runs (tests, the dummy video driver) play animations instantly and silently
        self.fast = os.environ.get('SDL_VIDEODRIVER') == 'dummy'
        sound = self.settings.get('sound')
        self.speaker = Speaker(enabled=not self.fast and (sound == 'on' if sound else sound_setting(self.data.src)))
        self.anim_host = ScreenHost(self)
        self.world = World(self.data)
        self.status = Status()
        self.player = new_player(KNIGHT, pack=self.pack)
        self.combat = Combat(self)
        self.magic = Magic(self)
        self.events = Events(self)
        self.start_level = start_level
        self.levels = self.data.level_count()
        self.messages: list[str] = []
        self.target: Enemy | None = None
        self.cursor = None
        self.overlay = None
        self.talk_log: list = []           # every talk() message shown, in order (read by the verifiers)
        self.last_shop = 0                 # peddler()'s remembered shop number
        self.pending_next_level = False    # set by a level script (e.g. the end of level 7)
        self.overlay = ui.TitleScreen()     # title() / mastermind()
        self.running = True
        self.view3d = False                # FPS mode: the world through the hero's eyes (F)
        self.facing = 0                    # which way the hero looks: 0 north, 1 east, 2 south, 3 west
        self.minimap = True                # FPS mode: the Map box shows this screen from above (M: the level map)
        # the combat log (Deluxe, D): who hit whom for how much, over the bottom of the map, and the
        # damage rising off whoever took it. Off in scripted runs, which compare screens with classic.
        self.combat_log = not self.fast
        self.log_lines: list = []          # (text, EGA colour, the key it came from)
        self.log_key = 0
        self.floaters: list = []           # damage numbers rising off a square

    # ── helpers ───────────────────────────────────────────────────────────────
    def log(self, text: str, colour: int = 15):
        if text:
            self.messages.append(Msg(text, colour))

    def a_name(self, it: int) -> str:
        """'a healing potion', 'an axe': an item as the combat log names it."""
        row = self.pack.item(it)
        name = (row.get('name') or self.item_name(it)).lower() or 'something'
        if row.get('type') == 'ammo':                    # 'Arrows-12': 12 arrows
            return f'{row.get("count", 1)} {name.split("-")[0].strip()}'
        return f'{"an" if name[0] in "aeiou" else "a"} {name}'

    def start_swing(self):
        """FPS mode: the weapon in view (engine.hands) attacks from now. Only the picture moves."""
        if self.view3d and not self.fast:
            item = self.pack.item(self.player.bag.get((12, 4), 0)) if self.player.bag.get((12, 4)) else {}
            self.swing = (attack_kind(item), pygame.time.get_ticks())

    def fly(self, anim_name, frm, to, hit: bool, towards_hero: bool = False):
        """FPS mode: the missile's flight (Renderer.fly), before its landing animation. A creature
        whose shot has no landing picture shows no flight either."""
        if towards_hero and not anim_name:
            return
        self.renderer.fly(self, anim_name, frm, to, hit, towards_hero, fast=self.fast)

    def swing_missed(self):
        """FPS mode: the blow in progress missed (engine.hands carries it too far)."""
        if getattr(self, 'swing', None):
            self.swing = (self.swing[0], self.swing[1], True)

    def fps_side(self, e) -> int:
        """FPS mode: the side a blow on the hero comes from, as ahit()/bhit2() take it (1 right, 2 below,
        3 left, 4 above), for the stroke drawn over the view: from the way the hero faces, and turned
        around so that one from in front rises from the bottom."""
        p = self.player
        dx, dy = (e.x > p.X) - (e.x < p.X), (e.y > p.Y) - (e.y < p.Y)
        if dx and dy:
            dy = 0                                       # a diagonal: by its side
        absolute = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}.get((dx, dy), 0)
        rel = (absolute - self.facing) % 4               # 0 in front, 1 right, 2 behind, 3 left
        return (2, 3, 4, 1)[rel]

    def key_name(self, colour: str) -> str:
        """The key of a colour, by its item's name ('gold key' for the yellow one in Quest I)."""
        for v, row in self.pack.items.items():
            if row.get('type') == 'key' and row.get('key') == colour:
                return (row.get('name') or self.item_name(v)).lower()
        return f'{colour} key'

    def report(self, text: str, colour: int = 15, at=None, amount=None):
        """A combat log line, and the amount rising off the square at (Deluxe; changes nothing)."""
        if not self.combat_log:
            return
        self.log_lines = self.log_lines[-40:] + [(text, colour, self.log_key)]
        if at is not None and amount is not None:
            shown = amount if isinstance(amount, str) else f'-{amount}' if amount else '0'
            self.floaters.append({'at': tuple(at), 'text': shown, 'colour': colour, 't0': None, 'key': self.log_key})

    def change_rep(self, delta: int):
        """hero.rep += delta, then reput()'s message."""
        self.player.hero.rep += delta
        self.play('reput2', delta)

    def play(self, name: str, *args, on_move=None, redraw=True, raw=False, in_view=True):
        """Run one of the original's animations now (engine.anim), blocking like the original.
        Its rand() draws happen even when drawing is skipped, so the random sequence stays the same.
        redraw=False keeps drawing over what the previous animation left on the screen. in_view=False:
        in FPS mode it is heard and waited for but not shown (the weapon in view shows the blow)."""
        self.anim_host.on_move = on_move
        try:
            self.renderer.play(self, getattr(anim, name)(self.anim_host, *args), fast=self.fast, redraw=redraw,
                               raw=raw, in_view=in_view)
        finally:
            self.speaker.nosound()
            self.anim_host.on_move = None

    def tones(self, *seq):
        """asound(f); delay(ms) ... nosound(): one of the original's short beeps."""
        self.play('tones', *seq)

    def on_screen(self, x: int, y: int) -> tuple[int, int]:
        """Map square -> the original's 1-based screen square (ax, ay)."""
        ox, oy = self.world.origin
        return x - ox + 1, y - oy + 1

    def play_at(self, name: str, x: int, y: int, *args, **kw):
        """An animation at map square (x, y)."""
        self.renderer.anchor = (x, y)
        try:
            self.play(name, *self.on_screen(x, y), *args, **kw)
        finally:
            self.renderer.anchor = None

    def monster_name(self, t: int) -> str:
        """How the combat log names a creature: its log_name, else its name in lower case."""
        return self.pack.trait(t, 'log_name') or self.renderer.sprites.names.get(('enemy', t), 'creature').lower()

    def item_name(self, it: int) -> str:
        return self.renderer.sprites.names.get(('object', it), f'item {it}')

    def spawn(self, t: int, x: int, y: int) -> Enemy:
        e = Enemy(type=t, x=x, y=y)
        ms = self.data.monsters.get(t)
        if ms:
            e.life = e.mlife = ms.life
            e.power, e.atk, e.defense = ms.power, ms.atk, ms.defense
            e.warm, e.marm, e.range, e.att = ms.warm, ms.marm, ms.range, ms.att
        self.world.sq(x, y).mon = t
        self.world.enemies.append(e)
        self.status.mons = len(self.world.enemies)
        return e

    def put_item(self, x: int, y: int, it: int):
        """put()/put3(): drop an item at map square (x, y), or the nearest free square the original
        way (1 then 2 squares left/right/up/down, then random squares)."""
        ox, oy = self.world.origin
        self.events.f_put(x - ox + 1, y - oy + 1, it)

    def count_hostiles(self):
        self.status.ems = sum(1 for e in self.world.enemies
                              if e.att >= 0 or e.att in (-4, -5) or e.att < -10)

    # ── setup ─────────────────────────────────────────────────────────────────
    def new_game(self):
        """newgame(): story 0, then newsave() takes the first free save slot (even when Esc leaves
        the story, as in the original), then creation()."""
        def reserve(then):
            self.status = Status(saveslot=self.slots.new())
            if not self.status.saveslot:
                self.overlay = ui.Notice('Error: you have too many save files! You need to delete at least '
                                         'one to play.', 15, lambda: setattr(self, 'overlay', ui.TitleScreen()))
                return
            then()
        self.show_story(0, lambda: reserve(lambda: setattr(self, 'overlay', ui.ClassSelect(self.pack))),
                        esc=lambda: reserve(lambda: setattr(self, 'overlay', ui.TitleScreen())))

    def start_new(self, cls: int, skill: int = 0, fault: int = 0):
        """The end of creation() and newgame(): build the hero, then newmap() shows story 1."""
        self.player = new_player(cls, skill, fault, self.pack)
        self.status = Status(Shield=0, fShield=0, powboost=-1, armboost=-1, saveslot=self.status.saveslot)
        self.status.p1, self.status.p2, self.status.p3 = rules.jumble()
        rules.status_update(self.player, self.status, self.items)

        def begin():
            self.goto_level(self.start_level)
            if self.status.saveslot:
                self.save_game(ask=False)             # newgame(): save(0, ...) before play starts
        self.show_story(1, begin, header=self.story_header())

    def quick_start(self, cls: int, level: int, at=None):
        """Test play: a new hero of class cls straight on the level (at square at, if it's free),
        without the title, the stories or character creation, and without a save slot."""
        self.overlay = None
        self.player = new_player(cls, pack=self.pack)
        self.status = Status(Shield=0, fShield=0, powboost=-1, armboost=-1)
        self.status.p1, self.status.p2, self.status.p3 = rules.jumble()
        self.goto_level(level)
        w = self.world
        if at and w.in_map(*at) and not self.pack.wall(w.sq(*at).wall).get('solid') and not w.sq(*at).mon:
            w.leave_room()
            self.player.X, self.player.Y = at
            w.enter_room(self.player, self.status)
            self.count_hostiles()
            self.events.on_enter_room()
        rules.status_update(self.player, self.status, self.items)
        self.messages = []

    def story_header(self) -> list[str]:
        """story(1): who the hero became, in the original's order."""
        sk, pk = self.player.skill, self.pack
        lines = [f'When you were 18,you decided to become a {pk.class_name(self.player.hero.type)}.']
        for sid in pk.quest.get('story_order', []):
            if getattr(sk, sid) == 1:
                lines.append(pk.skill(sid).get('story', ''))
        return lines

    def story_wipe(self):
        """story()'s black circle, drawn over whatever the screen shows (the 3D view too)."""
        self.play('story_circle', redraw=False, raw=True)

    def show_story(self, sid: int, then=None, header=None, esc=None):
        if sid in self.data.story:
            if sid not in (10, 11):                  # story() opens with the black circle (not 10 and 11)
                self.story_wipe()
            self.overlay = ui.TextScreen('', self.data.story[sid], then, header=header, esc=esc)
        elif then:
            then()

    def goto_level(self, level: int):
        self.world.load_level(level, self.player, self.status, tuple(self.events.meta(level, 'START', (5, 5))))
        rules.status_update(self.player, self.status, self.items)
        self.count_hostiles()
        self.target = None
        self.events.on_level_start()
        self.events.run('level_start')

    def next_level(self):
        if self.world.level and self.events.meta(self.world.level, 'LEAVE_JINGLE', True):
            self.play('song_bevcop')
        nxt = self.world.level + 1
        if nxt > self.levels:
            ending = [8, 9] if self.status.mission1 == 2 else [8]

            def chain(i=0):
                # newmap(): the ending stories, then credits(), then back to the title (mastermind())
                done = lambda: setattr(self, 'overlay', ui.Credits(lambda: setattr(self, 'overlay', ui.TitleScreen())))
                self.show_story(ending[i], (lambda: chain(i + 1)) if i + 1 < len(ending) else done)
            chain()
            return
        stories = self.events.meta(nxt, 'STORIES', [])

        def run(i=0):
            if i < len(stories):
                self.show_story(stories[i], lambda: run(i + 1))
            else:
                self.goto_level(nxt)
        run()

    def quit(self):
        self.running = False

    # ── input ─────────────────────────────────────────────────────────────────
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return
        if ev.type != pygame.KEYDOWN:
            return
        if self.overlay:
            self.overlay.key(self, ev)
            return
        k = ev.key
        if self.view3d and k in TURNS:
            self.facing = (self.facing + TURNS[k]) % 4    # FPS mode: turning is free, and not an action
            return
        self.log_key += 1                                # the log shows only what this key brought
        self.messages = []
        acted = False
        if self.view3d and (k in DIRS or k in STRAFE):
            acted = self.step_3d(k)
        elif k in DIRS:
            self.facing = FACES[DIRS[k]]
            acted = self.try_move(*DIRS[k])
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            acted = self.pick_up()
        elif pygame.K_1 <= k <= pygame.K_8:
            acted = self.drink(k - pygame.K_0)
        elif k in (pygame.K_9, pygame.K_0) and (10 if k == pygame.K_0 else 9) in self.pack.extra_potions():
            acted = self.drink(10 if k == pygame.K_0 else 9)          # The Quest Deluxe's potions 9 and 10
        elif k in (pygame.K_SPACE, pygame.K_TAB):
            acted = self.ranged(choose=k == pygame.K_TAB)
        elif pygame.K_F1 <= k <= pygame.K_F9:
            s = self.player.fkey[k - pygame.K_F1 + 1]
            if s:
                self.begin_cast(s)
        elif k == pygame.K_s:
            self.overlay = ui.SpellBook(self)
        elif k == pygame.K_i:
            self.open_inventory(1)
        elif k == pygame.K_c:
            self.overlay = ui.CharacterSheet()
        elif k == pygame.K_k:
            if self.events.ask('killer_allowed'):
                self.status.killer ^= 1
        elif k in (pygame.K_v, pygame.K_HOME):
            self.save_key()
        elif k in (pygame.K_l, pygame.K_INSERT):
            self.load_game()
        elif k == pygame.K_ESCAPE:
            self.quit_prompt()
        elif k == pygame.K_f:
            self.view3d = not self.view3d            # FPS mode (Deluxe)
        elif k == pygame.K_m and self.view3d:
            self.minimap = not self.minimap          # the Map box: this screen from above, or the level map
        elif k == pygame.K_d:
            self.combat_log = not self.combat_log        # the combat log (Deluxe)
            self.log_lines, self.floaters = [], []
        if acted:
            self.end_turn()
        self.events.run('after_action', 'space' if k == pygame.K_SPACE else 'key')
        if self.pending_next_level and not self.overlay:
            self.pending_next_level = False
            self.next_level()

    # ── movement ──────────────────────────────────────────────────────────────
    def step_3d(self, k) -> bool:
        """FPS mode: Up walks forward, Down back, , and . (or Q and E) step sideways (Left and Right
        turn, in handle()). Walking is the classic move, so bumping still fights, talks and opens."""
        f = self.facing
        way = {pygame.K_UP: f, pygame.K_KP8: f, pygame.K_DOWN: f + 2, pygame.K_KP2: f + 2}.get(k)
        if way is None:
            way = f + STRAFE[k]
        return self.try_move(*view3d.FACINGS[way % 4])

    def try_move(self, dx: int, dy: int) -> bool:
        p, w, st = self.player, self.world, self.status
        nx, ny = p.X + dx, p.Y + dy
        if not w.in_map(nx, ny):
            return False
        q = w.sq(nx, ny)
        wall = self.pack.wall(q.wall)
        if wall.get('solid'):
            return False
        e = w.enemy_at(nx, ny)
        if e and (st.killer or e.att > -1 or e.type > 0):
            self.combat.melee(e)
            return True
        door = wall.get('door')
        if door in ('plain', 'fake') or (door == 'locked' and has_key(p, wall['key'])):
            q.wall, q.deco = 0, self.pack.deco('open_door')
            self.tones((400, 100))
            if door == 'locked':
                self.report(f'You unlock the door with the {self.key_name(wall["key"])}.', 14)
            elif door == 'fake':
                self.report('The wall gives way: a secret passage!', 14)
            return True
        if door == 'locked':                         # locked: the original just doesn't move
            self.report(f'The door is locked. You need the {self.key_name(wall["key"])}.', 12)
            return True
        if q.mon < 0 and q.mon > -100:
            if p.hero.invisible == -1:
                if q.mon == -5:
                    self.open_shop()
                elif q.mon <= -6:
                    self.talk(q.mon, nx, ny)
            return True
        if e is not None:                     # an ally or neutral in the way
            return False
        if not w.in_room(nx, ny):
            if p.skill.hon == 2 and st.ems > 0:
                self.play('honor')
                return False
            w.leave_room()
            p.X, p.Y = nx, ny
            w.enter_room(p, st)
            self.target = None
            if p.skill.hon > 0:
                p.skill.hon = 1
            self.count_hostiles()
            self.events.on_enter_room()
        else:
            p.X, p.Y = nx, ny
        self.events.on_step(p.X, p.Y)
        kind = self.pack.item_type(q.item)
        if kind == 'exit':
            if self.events.meta(w.level, 'ASK_TO_LEAVE', True):
                self.overlay = ui.YesNo('Want to travel further? (Y)es (N)o', self.next_level)
            else:
                self.next_level()
        elif kind == 'teleporter':
            # teleporter1() on the pad, the jump (level 5), then teleporter2() where the hero lands
            self.play_at('teleporter1', p.X, p.Y)
            ddx, ddy = self.events.meta(w.level, 'TELEPORT', (0, 0))
            if (ddx, ddy) != (0, 0) and w.in_map(p.X + ddx, p.Y + ddy):
                w.leave_room()
                p.X += ddx
                p.Y += ddy
                w.enter_room(p, st)
                self.events.on_enter_room()
                self.target = None
                self.count_hostiles()
            self.play_at('teleporter2', p.X, p.Y)
        return True

    def talk(self, npc: int, x: int, y: int):
        self.events.on_talk(npc, x, y)

    def show_talk(self, text):
        """The end of talk(): a chime, the message in the strip, then a wait for Space. Like the
        original, nothing after the conversation happens until then (a scene's animations, the
        next line, the monsters' turn)."""
        self.talk_log.append(text)
        self.tones((500, 50), (600, 50), (500, 50))
        self.renderer.wait_talk(self, text, fast=self.fast)

    def autosave(self, ask: int):
        """A story point where the original calls save() itself (ask = 1: 'Want to save?')."""
        if self.world.grid and self.status.saveslot:
            self.save_game(ask=bool(ask))

    # ── items ─────────────────────────────────────────────────────────────────
    def pick_up(self) -> bool:
        """main2(), Enter: take what lies here, in the original order. It only costs a turn when there
        was something to take; the level script hears about it at the same points as the original's
        checks (before, after a chest, after an item goes into the backpack)."""
        p, q = self.player, self.world.sq(self.player.X, self.player.Y)
        turn = bool(q.item or q.gold)
        if turn:
            self.tones((300, 50), (400, 50))
        self.events.run('before_pickup')
        pk = self.pack
        if pk.item_type(q.item) == 'chest':
            found = rules.random(40) + 80
            p.inv.coins += found
            q.item, q.deco = 0, pk.deco('open_chest')
            self.report(f'You open the chest: {found} gold.', 14)
            self.events.run('opened_chest')
        if q.gold > 0:
            p.inv.coins += q.gold
            self.report(f'You pick up {q.gold} gold.', 14)
            q.gold = 0
        if pk.item_type(q.item) == 'potion':
            add_potions(p, pk.item(q.item)['potion'])
            self.report(f'You pick up {self.a_name(q.item)}.', 15)
            q.item = 0
        if pk.item_type(q.item) == 'key':
            give_key(p, pk.item(q.item)['key'])
            self.report(f'You pick up the {self.key_name(pk.item(q.item)["key"])}.', 15)
            q.item = 0
            self.play('song_key')
        free = p.free_backpack_slot()
        if free and pk.item_type(q.item) != 'exit':
            if q.item:
                it = q.item
                p.bag[free] = it
                q.item = 0
                self.report(f'You pick up {self.a_name(it)}.', 15)
                self.events.run('took', it)
        elif q.item:
            self.tones((150, 150))                   # no room in the backpack
            if pk.item_type(q.item) != 'exit':
                self.report(f'Your backpack is full: you leave {self.a_name(q.item)}.', 12)
        return turn

    def drink(self, n: int) -> bool:
        p, h, inv = self.player, self.player.hero, self.player.inv
        if n not in POTION_FIELDS:
            return self.drink_extra(n)
        f = POTION_FIELDS[n]
        if getattr(inv, f) <= 0 or (n == 7 and not h.poisoned):
            return False
        setattr(inv, f, getattr(inv, f) - 1)
        half = lambda cur, mx: cur + mx // 2 + (mx % 2)
        if n == 1:
            h.life = half(h.life, h.mlife)
        elif n == 2:
            h.life = h.mlife
        elif n == 3:
            h.mana = half(h.mana, h.mmana)
        elif n == 4:
            h.mana = h.mmana
        elif n == 5:
            h.life, h.mana = half(h.life, h.mlife), half(h.mana, h.mmana)
        elif n == 6:
            h.life, h.mana = h.mlife, h.mmana
        elif n == 7:
            h.poisoned = 0
            self.play('ampoisoned2', 0)
        elif n == 8:
            self.status.powboost = self.status.armboost = 11
        h.life, h.mana = min(h.life, h.mlife), min(h.mana, h.mmana)
        rules.status_update(p, self.status, self.items)
        self.tones((740, 100))
        return True

    def drink_extra(self, n: int) -> bool:
        """Potion 9 or 10, as the pack defines it (quest.json "potions"): life and mana ("half", "full"
        or a number), cure_poison, berserk (turns of doubled power and armour, like potion 8)."""
        p, h = self.player, self.player.hero
        pot = self.pack.extra_potions().get(n)
        if not pot or potions(p, n) <= 0:
            return False
        heals = pot.get('life') or pot.get('mana') or pot.get('berserk')
        if pot.get('cure_poison') and not heals and not h.poisoned:
            return False                                  # like Cure Poison: only when poisoned
        add_potions(p, n, -1)

        def gain(cur, mx, how):
            if how == 'full':
                return mx
            if how == 'half':
                return cur + mx // 2 + (mx % 2)
            return cur + int(how or 0)
        h.life = gain(h.life, h.mlife, pot.get('life'))
        h.mana = gain(h.mana, h.mmana, pot.get('mana'))
        if pot.get('cure_poison') and h.poisoned:
            h.poisoned = 0
            self.play('ampoisoned2', 0)
        if pot.get('berserk'):
            self.status.powboost = self.status.armboost = int(pot['berserk'])
        h.life, h.mana = min(h.life, h.mlife), min(h.mana, h.mmana)
        rules.status_update(p, self.status, self.items)
        self.report(f'You drink the {pot.get("name", f"potion {n}").lower()}.', 10)
        self.tones((740, 100))
        return True

    # ── the inventory and the shops: the original's own pages (engine.invshop) ──
    def page_layer(self) -> pygame.Surface:
        """The screen as it is when a page opens; the page draws over its right side and strip."""
        self.renderer.draw(self)
        return self.renderer.screen.copy()

    def open_inventory(self, mode: int = 1, store=None):
        """inventory(mode): 1 from the i key, 2 as the shop's selling page. Afterwards
        statusupdate(); 'b' on the selling page goes back to buying."""
        layer = self.page_layer()
        host = PageHost(self, layer, store or {})

        def done(key):
            rules.status_update(self.player, self.status, self.items)
            if mode == 2 and key == ord('b'):
                self.open_shop()
        self.overlay = ui.Page(self, layer, invshop.inventory(host, mode), done)

    def open_shop(self):
        """peddler(): the shop's wares come from S0000<level><n>.dat, n from the screen. The file-name
        buffer keeps the last shop's number, so an unlisted screen sells the last shop's wares
        (0: none). 's' or 'i' goes to the selling page."""
        sx, sy = screen_of(self.player.X, self.player.Y)
        self.last_shop = self.events.meta(self.world.level, 'SHOPS', {}).get(
            (sx, sy), 0 if self.pack.fixed('shop_memory') else self.last_shop)
        store = {}
        if self.last_shop:
            try:
                nums = [v for row in self.data.shop(self.world.level, self.last_shop) for v in row][:40]
            except FileNotFoundError:
                nums = []
            store = {(12 + k % 4, 2 + k // 4): v for k, v in enumerate(nums)}
        layer = self.page_layer()
        host = PageHost(self, layer, store)

        def done(key):
            if key in (ord('s'), ord('i')):
                self.open_inventory(2, store)
        self.overlay = ui.Page(self, layer, invshop.peddler(host), done)

    # ── magic ─────────────────────────────────────────────────────────────────
    def begin_cast(self, spell: int):
        self.messages = []
        if self.magic.can_cast(spell):              # unknown, too little mana or INT: the key does nothing
            return
        p = self.player
        if self.magic.fizzles(spell):                 # dcast(), then a low beep; the spell is lost
            self.play_at('dcast2', p.X, p.Y)
            self.tones((50, 200))
            self.end_turn()
            return
        self.play_at('dcast2', p.X, p.Y)              # dcast(): the hero's eyes flicker
        if self.spells.tell(spell, SP_RANGE) == 0:
            self.magic.cast_self(spell)
            self.end_turn()
            return

        def picked(x, y):
            self.messages = []
            self.magic.cast_at(spell, x, y)
            self.end_turn()
        self.overlay = ui.Cursor(self, p.X, p.Y, f'Cast {self.pack.spell_name(spell)}: choose a target',
                                 picked, allowed=lambda x, y: self.magic.in_range(spell, x, y),
                                 can_pick=lambda x, y: self.magic.valid_target(spell, x, y),
                                 on_cancel=self.end_turn)       # Esc: nothing cast, but the turn is used

    def learn_spell(self, s: int):
        p = self.player
        p.spells[s] = 3 if p.skill.mem == 1 else 4
        if s not in p.book:
            free = next((i for i, v in enumerate(p.book) if not v), None)
            if free is not None:
                p.book[free] = s

    # ── ranged ────────────────────────────────────────────────────────────────
    def ranged(self, choose: bool) -> bool:
        why = self.combat.can_shoot()
        if why == 'noarrows':
            self.play('noarrows2')                    # a ranged weapon with nothing in the off-hand
            return False
        if why:
            # main2(): nothing is shot, but Space still uses the turn (so does Tab with a ranged
            # weapon); only Tab without a ranged weapon is free
            return not choose or why == 'badammo'
        p = self.player
        if self.target and (self.target not in self.world.enemies or
                            (abs(self.target.x - p.X) < 2 and abs(self.target.y - p.Y) < 2)):
            self.target = None
        cands = self.combat.ranged_candidates()
        if choose and not cands:
            return True                               # target() is only reached with someone in range
        if choose:
            start = self.target or (cands[0] if cands else None)
            sx, sy = (start.x, start.y) if start else (p.X, p.Y)

            def ok(x, y):
                e = self.world.enemy_at(x, y)
                q = self.world.sq(x, y)
                return e is not None and max(abs(x - p.X), abs(y - p.Y)) > 1 and \
                    (q.mon > 0 or self.status.killer or q.mon < -99)

            def picked(x, y):
                self.messages = []
                self.combat.shoot(self.world.enemy_at(x, y))
                self.end_turn()
            self.overlay = ui.Cursor(self, sx, sy, 'Choose a target', picked, can_pick=ok,
                                     on_cancel=self.end_turn)   # target() cancelled: the turn is used
            return False
        e = self.target if self.target in cands else (cands[0] if cands else None)
        if not e:
            return True                               # nothing in range: the turn passes anyway
        self.combat.shoot(e)
        return True

    # ── turn end ──────────────────────────────────────────────────────────────
    def end_turn(self):
        """Everything main2() does after the hero acts, in the original order."""
        p, h, st, w = self.player, self.player.hero, self.status, self.world
        if st.fShield > 0:
            self.combat.fire_shield()
        if h.invisible == 0:
            h.invisible = -1
            for e in w.enemies:
                if e.att == -5:
                    e.att = 9
        self.combat.enemy_attacks()
        monsmove(self)
        self.combat.check_dead()
        # dying and death
        if h.life < 1:
            if h.life <= -5:
                self.death()
                return
            h.life -= 1
            q = w.sq(p.X, p.Y)
            if q.deco == 0:
                q.deco = self.pack.deco('blood')
            self.play('dying2')                       # "You are bleeding!", then the potion belt again
        self.upkeep()
        if h.exper <= 0 and not self.overlay:
            self.level_up()

    def death(self):
        """death(): the hero's body, death2()'s last words, then 'Want to load?'; No closes the
        screen in a black box and goes back to the title (mastermind())."""
        p = self.player
        self.world.sq(p.X, p.Y).deco = self.pack.deco('remains2')
        self.messages = []
        self.play('death2')

        def no():
            self.play('death_wipe', redraw=False)
            self.overlay = ui.TitleScreen()
        self.load_game(on_no=no)

    def upkeep(self):
        """Top of the main2() loop after a turn: faults, poison, spell timers, boosts."""
        p, h, st, sk = self.player, self.player.hero, self.status, self.player.skill
        if sk.ras > 1:
            sk.ras -= 1
        if h.poisoned == 1 and h.life > 0:
            h.life -= max(1, h.mlife // 100)
        if h.invisible > 0:
            h.invisible -= 1
        if st.armboost == 1:
            st.armboost = st.powboost = 0
        if st.armboost > 0:
            st.armboost -= 1
        if st.powboost > 0:
            st.powboost -= 1
        if st.Shield >= 0:
            st.Shield -= 1
        if st.fShield >= 0:
            st.fShield -= 1
        if h.invisible == 0:
            h.invisible = -1
            for e in self.world.enemies:
                if e.att == -5:
                    e.att = 9
        for e in self.world.enemies:
            e.moved = False
        self.count_hostiles()
        rules.status_update(p, st, self.items)

    def level_up(self):
        p, st = self.player, self.status
        gained = rules.level_up_auto(p, st, self.pack)
        rules.status_update(p, st, self.items)

        def after_points():
            new = rules.reclassify(p, self.pack)
            rules.status_update(p, st, self.items)
            if new:
                self.play('class_change', new, self.pack.class_name(new))
            self.after_level_spells()
        self.play('alevelup')                         # "Level Up!" in the strip, then song_jazz()
        self.play('song_jazz', redraw=False)
        self.overlay = ui.LevelUpScreen(self, gained, rules.choices_this_level(p), after_points)

    def after_level_spells(self):
        """main2: advance the spell being learnt, or offer new ones if none is in progress."""
        p = self.player
        finished_or_none = True
        count = self.pack.spell_count()
        for s in range(1, count + 1):
            if p.spells[s] > 1:
                p.spells[s] -= 1
                if p.spells[s] != 1:
                    finished_or_none = False
                break
        if not finished_or_none:
            return
        cands = [s for s in range(1, count + 1) if p.spells[s] == 0 and self.spells.tell(s, SP_INT) <= p.hero.intl
                 and s in self.spells.rows]
        if cands:
            self.overlay = ui.LearnSpell(cands, lambda: None)

    # ── saving: the original's data\\saveNN.dat, one slot per game ──────────────
    def can_save(self) -> bool:
        return not (self.status.ems > 0 and any(e.type > 0 and not self.pack.trait(e.type, 'invisible')
                                                for e in self.world.enemies))

    def save_key(self):
        """Home / v in main2(): save() with its question, or cantsave() with monsters about."""
        if not self.world.grid:
            return
        if not self.can_save():
            self.play('cantsave')
            return
        self.save_game(ask=True)

    def save_game(self, ask: bool = False):
        """save(type): type 1 asks 'Want to save? (Y)es (N)o'; type 0 (after creation) saves silently."""
        def write():
            if ask:
                self.tones((500, 50), (600, 50))
                self.play('strip_text', 'Saving. . .')
            self.slots.write(self.status.saveslot, self.to_save())
        if ask:
            self.overlay = ui.YesNo('Want to save? (Y)es (N)o', write)
        else:
            write()

    def load_game(self, on_no=None):
        """load(): in a game it asks 'Want to load? (Y)es (N)o' (from the title's list it doesn't),
        then load2() reads the game's own slot."""
        def read():
            if self.status.level:
                self.play('strip_text', 'Loading. . .')
            d = self.slots.read(self.status.saveslot)
            if d is None:
                return
            self.tones((500, 50), (600, 50))
            self.from_save(d, self.status.saveslot)
            self.play('death_wipe', redraw=False)          # load2() ends by closing the screen
        if self.status.level:
            self.overlay = ui.YesNo('Want to load? (Y)es (N)o', read, on_no)
        else:
            read()

    def quit_prompt(self):
        """Esc: quit() asks 'Want to quit? (Y)es (N)o'; Yes returns to the title (without saving)."""
        def yes():
            self.tones((500, 50), (600, 50))
            self.play('death_wipe', redraw=False)
            self.world.grid = []
            self.overlay = ui.TitleScreen()
        self.overlay = ui.YesNo('Want to quit? (Y)es (N)o', yes)

    def to_save(self) -> SaveData:
        """The game in save() terms: the current screen as map[] has it (as it was on arrival) and
        as room[] has it (live), creatures in screen coordinates."""
        p, st, w = self.player, self.status, self.world
        ox, oy = w.origin
        d = SaveData(hero=asdict(p.hero), inv=asdict(p.inv), skill=asdict(p.skill), st=asdict(st))
        d.X, d.Y = p.X, p.Y
        d.ax, d.ay = self.on_screen(p.X, p.Y)
        shadow = self.events.shadow
        for x in range(1, MAP_SIZE + 1):
            for y in range(1, MAP_SIZE + 1):
                q = w.grid[x][y]
                if w.in_room(x, y) and (x, y) in shadow:
                    v = shadow[(x, y)]
                    d.map[(x, y)] = (v['floor'], v['wall'], v['item'], v['mon'], v['gold'], v['deco'])
                else:
                    d.map[(x, y)] = (q.floor, q.wall, q.item, q.mon, q.gold, q.deco)
        for i in range(1, 11):
            for ii in range(1, 11):
                q = w.grid[ox + i - 1][oy + ii - 1]
                d.room[(i, ii)] = (q.floor, q.wall, q.item, q.mon, q.gold, q.deco)
        d.enemies = [{f: getattr(e, f) for f in savefile.ENEMY} for e in w.enemies]
        for e in d.enemies:
            e['x'], e['y'] = e['x'] - ox + 1, e['y'] - oy + 1
        d.bag = {c: p.bag.get(c, 0) for c in savefile.BAG_CELLS}
        d.book = {(13, 2 + k): p.book[k] for k in range(10)}
        d.book.update({(16, 2 + k): p.book[10 + k] for k in range(10)})
        d.spells = list(p.spells[:21])
        d.carta = {(sx + 1, sy + 1): 1 for sx, sy in w.visited}
        d.fkey = list(p.fkey)
        # past the original's structures: the DELUXE block, only when there is something in it
        if any(p.spells[21:]):
            d.extra['spells'] = list(p.spells[21:])
        if any(p.book[20:]):
            d.extra['book'] = list(p.book[20:])
        more = {k: v for k, v in p.more.items() if v}
        if more:
            d.extra['more'] = more
        return d

    def from_save(self, d: SaveData, slot: int):
        """load2() into the game: map[] (with the current screen as it was on arrival), then room[]
        (the screen as it is), the creatures as they were, and everything else."""
        p = Player(hero=Hero(**{f: d.hero.get(f, getattr(Hero, f)) for f in Hero.__dataclass_fields__}),
                   inv=Inventory(**d.inv), skill=Skills(**d.skill))
        p.bag = {c: v for c, v in d.bag.items() if v}
        p.book = [d.book.get((13, 2 + k), 0) for k in range(10)] + [d.book.get((16, 2 + k), 0) for k in range(10)]
        p.spells, p.fkey = list(d.spells), list(d.fkey)
        p.spells += list(d.extra.get('spells', []))          # The Quest Deluxe's block
        p.book += list(d.extra.get('book', []))
        p.more = dict(d.extra.get('more', {}))
        p.fit_spells(self.pack.spell_count())
        p.X, p.Y = d.X, d.Y
        self.player = p
        self.status = Status(**{f: d.st.get(f, 0) for f in Status.__dataclass_fields__})
        self.status.saveslot = slot
        w = self.world
        w.level = self.status.level
        w.grid = [[Square() for _ in range(MAP_SIZE + 2)] for _ in range(MAP_SIZE + 2)]
        for (x, y), (fl, wa, it, mo, go, de) in d.map.items():
            if w.in_map(x, y):
                w.grid[x][y] = Square(fl, wa, mo, it, go, de)
        w.visited = {(i - 1, ii - 1) for (i, ii), v in d.carta.items() if v}
        w.origin = room_origin(p.X, p.Y)
        self.events.snapshot()                          # map[] holds the arrival values
        ox, oy = w.origin
        for (i, ii), (fl, wa, it, mo, go, de) in d.room.items():
            if 1 <= i <= 10 and 1 <= ii <= 10:
                w.grid[ox + i - 1][oy + ii - 1] = Square(fl, wa, mo, it, go, de)
        w.enemies = []
        for e in d.enemies[:max(0, self.status.mons)]:
            e = dict(e)
            e['x'], e['y'] = e['x'] + ox - 1, e['y'] + oy - 1
            w.enemies.append(Enemy(**e))
        self.target = None
        rules.status_update(p, self.status, self.items)
        self.overlay = None
        self.messages = []

    # ── loop ──────────────────────────────────────────────────────────────────
    HOLD_MS = 250                  # FPS mode: a direction held this long keeps going
    REPEAT_MS = 150                # ... a step or a turn at a time, each after the last has glided

    def held_key(self, held: dict, now: int):
        """FPS mode: the walking or turning key to press again for the hero, if one is held down (held:
        key -> when it went down): only once the last step or turn has glided, and no sooner than
        REPEAT_MS after the last repeat, so walking into a wall or a fight doesn't run away."""
        if not self.view3d or self.overlay or not self.renderer.in_3d(self) or self.renderer.gliding(self):
            return None
        if now - getattr(self, '_last_repeat', -10 ** 9) < self.REPEAT_MS:
            return None
        for k, t0 in held.items():
            if (k in DIRS or k in STRAFE or k in TURNS) and now - t0 >= self.HOLD_MS:
                return k
        return None

    def run(self):
        clock = pygame.time.Clock()
        held = {}                                        # keys down now -> when they went down
        while self.running:
            now = pygame.time.get_ticks()
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN:
                    held[ev.key] = now
                elif ev.type == pygame.KEYUP:
                    held.pop(ev.key, None)
                elif ev.type == pygame.WINDOWFOCUSLOST:
                    held.clear()                         # its key-up would never come
                self.handle(ev)
            k = self.held_key(held, now)
            if k is not None:                            # FPS mode: keep walking (or turning)
                self._last_repeat = now
                self.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode='', mod=0))
            self.renderer.draw(self)
            clock.tick(30)

