"""The original's bugs, fixed when a pack asks (quest.json's "fixes") or the player does (settings.ini),
and kept when neither does.

packs/TheQuest asks for none, so it plays exactly as the original (the lockstep test holds it to that);
each check here runs the same thing without and with the fix.

    python tests/test_fixes.py [screenshot.png]
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 480))

from engine import ui, savefile  # noqa: E402
from engine.pack import Pack  # noqa: E402
from engine.render import EGA  # noqa: E402
from engine.state import Enemy  # noqa: E402
from test_limits import pack_copy  # noqa: E402


def game(fixes=None, change=None):
    def edit(folder, json):
        if change:
            change(folder, json)
        if fixes is not None:
            path = os.path.join(folder, 'quest.json')
            q = json.load(open(path))
            q['fixes'] = fixes
            json.dump(q, open(path, 'w'))
    g = pack_copy(edit)
    g.quick_start(1, 1)
    return g


def none_in_quest_i():
    pk = Pack(os.path.join(ROOT, 'packs', 'TheQuest'))
    assert not any(pk.fixed(n) for n in Pack.FIXES), 'packs/TheQuest must keep every bug'
    g = game(['talk'])
    assert g.pack.fixed('talk') and not g.pack.fixed('dead_scan')
    g = game(True)
    assert all(g.pack.fixed(n) for n in Pack.FIXES)
    print('packs/TheQuest fixes nothing; a list fixes those named; true fixes all: ok')


def shield_ice():
    def stronger_ice(folder, json):
        path = os.path.join(folder, 'spells.json')
        data = json.load(open(path))
        for s in data['spells']:
            if s['id'] == 5:
                s['power'] = 30                           # Ring of Ice stronger than the Shield's 10
        json.dump(data, open(path, 'w'))
    assert game(None, stronger_ice).pack.shield_absorbs() == 30      # the original reads Ring of Ice's
    assert game(['shield_ice'], stronger_ice).pack.shield_absorbs() == 10
    print("shield and ring of ice: each its own power with the fix: ok")


def quiz_ties():
    g = game(None)
    assert {ui.quiz_class(1001) for _ in range(30)} == {4}           # Knight and Monk tie: a Monk
    g = game(['quiz_ties'])
    quiz = ui.Quiz(g)
    g.overlay = quiz
    quiz.q[7] = quiz.q[7][:4] + ['1'] + quiz.q[7][5:]                 # the last question's answer A: a Monk
    results = set()
    for _ in range(40):
        quiz.result, quiz.n, quiz.total = 0, 7, 1000
        quiz.pick(g, 1)                                               # answer A adds 1: 1001
        results.add(quiz.result)
    assert results == {1, 4}, results
    print('questionnaire ties: random between the tied classes with the fix: ok')


def fault_colours(shot=None):
    def sheet(g):
        p = g.player
        p.skill.cow = p.skill.ras = 1
        p.skill.hon = 0
        p.hero.life = 1
        g.overlay = ui.CharacterSheet()
        g.renderer.draw(g, present=False)
        scr = g.renderer.screen
        box = [scr.get_at((x, y))[:3] for x in range(290, 400) for y in range(441, 458)]
        return scr, EGA[14][:3] in box, EGA[4][:3] in box
    scr, yellow, red = sheet(game(None))
    assert yellow and not red, (yellow, red)                          # Rashness in yellow
    scr, yellow, red = sheet(game(['fault_colours']))
    assert red and not yellow, (yellow, red)
    if shot:
        pygame.image.save(scr, shot)
    print('fault colours: Rashness stays red while Cowardice shows, with the fix: ok')


def shop_memory():
    for fixes, expect in ((None, 3), (['shop_memory'], 0)):
        g = game(fixes)
        g.last_shop = 3                                               # a shop from before
        g.open_shop()                                                 # on a screen with none
        assert g.last_shop == expect, (fixes, g.last_shop)
        g.overlay = None
    print("shops: a screen without one sells nothing with the fix, the last shop's stock without: ok")


def dead_scan():
    for fixes, left in ((None, 1), (['dead_scan'], 0)):
        g = game(fixes)
        w = g.world
        w.enemies.clear()
        ox, oy = w.origin
        for k in range(2):
            e = Enemy(type=1, x=ox + 2 + k, y=oy + 2, life=0, mlife=5)
            w.enemies.append(e)
            w.sq(e.x, e.y).mon = 1
        g.combat.check_dead()
        assert len(w.enemies) == left, (fixes, len(w.enemies))
    print('deaths: the creature that slides into place is checked at once with the fix: ok')


def load_gaps():
    g = game(None)
    slots = savefile.Slots(tempfile.mkdtemp())
    g.slots = slots
    raw = savefile.to_bytes(g.to_save())
    for n in (1, 3):
        os.makedirs(slots.dir, exist_ok=True)
        with open(slots.path(n), 'wb') as fh:
            fh.write(raw)
    assert [n for n, *_ in slots.listing()] == [1]
    assert [n for n, *_ in slots.listing(all_=True)] == [1, 3]
    g = game(['load_gaps'])
    g.slots = slots
    ls = ui.LoadScreen(g)
    g.overlay = ls
    g.renderer.draw(g, present=False)
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode=''))
    assert ls.i == 2 and ls.games[ls.i - 1][0] == 3
    print('Load Game: every saved game past a gap, with the fix: ok')


def talk():
    from engine.events import talk_text, talk_text_fixed
    raw = open(os.path.join(ROOT, 'packs', 'TheQuest', 'text', 'talk.txt')).read()
    assert talk_text(raw, 1, -6, 1) == (' "Hello."', '', -3)
    assert talk_text_fixed(raw, 1, -6, 1) == ('\xff"Hello."', '', 8)
    one, two, x = talk_text(raw, 1, -6, 10)
    assert talk_text_fixed(raw, 1, -6, 10) == (one, two.lstrip('\n'), x)
    assert talk_text_fixed(raw, 1, -6, 99) is None                    # where the original hangs
    g = game(['talk'])
    g.events.talk(-6)
    assert g.talk_log[-1][2] == 8, g.talk_log[-1]
    print('talk: entries found by their lines, one-line messages placed like two-line ones, a missing '
          'line says nothing: ok')


def blank_rows():
    from engine.state import new_player
    g = game(None)
    sel = ui.SkillSelect(1, g.pack)                                   # a Knight: five rows, one of them blank
    assert [s['id'] for s in sel.skills] == ['bar', 'amb', 'mem', 'mar', 'sch'] and not sel.allowed(4)
    faults = ui.FaultSelect(1, 1, g.pack)                             # and three faults, Cowardice blank
    assert [f['id'] for f in faults.faults] == ['cow', 'ras', 'hon'] and not faults.allowed(1)
    g = game(['blank_rows'])
    sel = ui.SkillSelect(1, g.pack)                                   # four rows, no blank
    assert [s['id'] for s in sel.skills] == ['bar', 'amb', 'mem', 'sch']
    assert not any(sel.allowed(i) and sel.skills[i - 1]['id'] == 'mar' for i in range(1, 5))
    g.overlay = sel
    for _ in range(3):
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode=''))
    assert sel.i == 4
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=''))
    assert isinstance(g.overlay, ui.FaultSelect) and g.overlay.skill == 5, g.overlay.skill   # Scholar
    p = new_player(1, 5, 1, pack=g.pack)
    assert p.skill.sch == 1 and p.skill.mar == 0
    rogue = ui.SkillSelect(3, g.pack)                                 # the Rogue keeps Marksmanship's row
    assert [s['id'] for s in rogue.skills] == ['bar', 'amb', 'mem', 'mar', 'sch'] and not rogue.allowed(4)
    # the faults: a Knight is offered Rashness and Honor, in rows 1 and 2
    faults = ui.FaultSelect(1, 5, g.pack)
    assert [f['id'] for f in faults.faults] == ['ras', 'hon'] and faults.allowed(1) and faults.allowed(2)
    g.overlay = faults
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, unicode=''))
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=''))
    assert g.player.skill.hon == 1 and g.player.skill.cow == 0 and g.player.skill.sch == 1 and g.player.skill.amb == 1
    assert [f['id'] for f in ui.FaultSelect(4, 1, g.pack).faults] == ['cow', 'ras', 'hon']   # the Monk: all three
    # a class can hide more: a list of skills and faults
    g.pack.classes[4]['no_skill'] = ['bar', 'mem']
    g.pack.classes[4]['no_fault'] = ['cow', 'hon']
    assert [s['id'] for s in ui.SkillSelect(4, g.pack).skills] == ['amb', 'sch']
    assert [f['id'] for f in ui.FaultSelect(4, 1, g.pack).faults] == ['ras']
    print("creation's lists: no blank rows with the fix, for skills and faults; Marksmanship stays the Rogues' "
          'own, and a class can hide more: ok')


def map_corrections():
    for fixes, tree, shield in ((None, -5, 311), (['map'], 0, 0)):
        g = game(fixes)
        g.goto_level(6)
        assert g.world.sq(24, 82).item == tree, (fixes, g.world.sq(24, 82).item)
        g.goto_level(7)
        assert g.world.sq(45, 65).item == shield
    print("the map: the item in a tree and the shield that doesn't exist are gone with the fix: ok")


def player_settings():
    from engine import settings
    from engine.formats import GameData
    from engine.game import Game
    path = os.path.join(tempfile.mkdtemp(), 'settings.ini')
    assert settings.load(path) == settings.DEFAULTS                  # no file
    open(path, 'w').write('[play]\nfixes = ON ; a comment\nsound = maybe\n')
    assert settings.load(path) == {'fixes': 'on', 'sound': None, 'items_on_top': 'off', 'floating_numbers': 'off',
                                   'fps_quality': 'normal', 'fps_dither': 'ordered', 'fps_view_distance': 'level',
                                   'smooth_scaling': 'off', 'render_quality': 'normal', 'fps_texture_filter': 'off', 'fps_fog_start': 45, 'fps_transition': 'on'}   # not a choice: default
    shipped = settings.load()
    assert shipped['fixes'] == 'on' and shipped['items_on_top'] == 'on', shipped   # the folder's settings.ini
    # the player's choice beats the pack's, both ways; without settings the pack's own stands
    g = game(['talk'])
    data = GameData.load(g.data.src)
    for s, talk, gaps in (({'fixes': 'on'}, True, True), ({'fixes': 'off'}, False, False),
                          ({'fixes': 'pack'}, True, False), (None, True, False)):
        g2 = Game(pygame.Surface((640, 480)), data=data, settings=s)
        assert (g2.pack.fixed('talk'), g2.pack.fixed('load_gaps')) == (talk, gaps), s
    g3 = Game(pygame.Surface((640, 480)), data=data, settings={'fixes': 'on'})
    g3.renderer.draw(g3, present=False)                               # the title says so
    assert any(g3.renderer.screen.get_at((x, y))[:3] == EGA[15][:3] for x in range(4, 110) for y in range(470, 478))
    g4 = Game(pygame.Surface((640, 480)), data=data)
    g4.renderer.draw(g4, present=False)
    assert not any(g4.renderer.screen.get_at((x, y))[:3] == EGA[15][:3] for x in range(4, 110) for y in range(470, 478))
    print("settings.ini: fixes on / off / pack over the pack's own, and the title's note: ok")


def main():
    none_in_quest_i()
    shield_ice()
    quiz_ties()
    fault_colours(sys.argv[1] if len(sys.argv) > 1 else None)
    shop_memory()
    dead_scan()
    load_gaps()
    talk()
    blank_rows()
    map_corrections()
    player_settings()
    print('all fix checks passed')


if __name__ == '__main__':
    main()
