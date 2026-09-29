"""Spells: port of cast() (RPG.CPP 0a45:832a).

Spells.dat columns: id, required INT, mana, range (0 = self), power, duration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import rules
from .rules import random, SP_INT, SP_MANA, SP_RANGE, SP_POWER, SP_DURATION, SPELL_NAMES

if TYPE_CHECKING:
    from .game import Game

HEAL_SPELLS = (1, 10, 17)
SUMMONS = {8: -100, 15: -101, 18: -102}
DAMAGE_SPELLS = (2, 9, 12, 14, 19)
RING8 = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]


class Magic:
    def __init__(self, game: 'Game'):
        self.g = game

    def tell(self, spell: int, col: int) -> int:
        return self.g.spells.tell(spell, col)

    def can_cast(self, spell: int) -> str | None:
        p = self.g.player
        if not spell or p.spells[spell] != 1:
            return "You don't know that spell."
        if self.tell(spell, SP_MANA) > p.hero.mana:
            return 'Not enough mana.'
        if self.tell(spell, SP_INT) > p.hero.intl:
            return 'You are not intelligent enough to cast that.'
        return None

    def fizzles(self, spell: int) -> bool:
        """Rashness (20% while enemies are near) and Invisibility's own 50% / shield conflicts."""
        p, st = self.g.player, self.g.status
        if p.hero.invisible > -1:
            p.hero.invisible = 0
        fail = False
        if p.skill.ras == 1 and st.ems > 0 and random(100) > 79:
            fail = True
        if spell == 7 and (random(100) > 49 or st.Shield > 0 or st.fShield > 0):
            fail = True
        if fail and p.skill.ras == 1:
            p.skill.ras = 3
        return fail

    # ── targeting rules (Enter in the cast cursor) ────────────────────────────
    def valid_target(self, spell: int, x: int, y: int) -> bool:
        w, p, st = self.g.world, self.g.player, self.g.status
        q = w.sq(x, y)
        if (q.wall != 0 or q.item >= 999) and spell != 16:
            return False
        if (x, y) == (p.X, p.Y) and spell != 16:
            return False
        if q.mon < 0 and not st.killer and not (spell in SUMMONS or spell == 3):
            return False
        if spell == 3 and q.mon != 0:
            return False
        if spell in SUMMONS and q.mon != 0:
            return False
        if spell in (11, 14) and q.mon == 0:
            return False
        return True

    def in_range(self, spell: int, x: int, y: int) -> bool:
        r = self.tell(spell, SP_RANGE)
        p = self.g.player
        return abs(x - p.X) <= r and abs(y - p.Y) <= r and self.g.world.in_room(x, y)

    # ── effects ───────────────────────────────────────────────────────────────
    def cast_self(self, spell: int) -> None:
        g, p, h, st = self.g, self.g.player, self.g.player.hero, self.g.status
        h.mana -= self.tell(spell, SP_MANA)
        name = SPELL_NAMES.get(spell, 'spell')
        power, dur = self.tell(spell, SP_POWER), self.tell(spell, SP_DURATION)
        g.fx.append(('spell', spell, p.X, p.Y))
        if spell in HEAL_SPELLS:
            h.life = min(h.mlife, h.life + power)
            g.log(f'{name}: you recover {power} life.')
        elif spell == 7:
            h.invisible = dur + 1
            for e in g.world.enemies:
                if e.att > 0 and e.att != 8 and e.att > -10:
                    e.att = -5
            g.log('You fade from sight.')
        elif spell == 4:
            st.Shield, st.fShield = dur, 0
            g.log('A magical shield surrounds you.')
        elif spell == 13:
            st.fShield, st.Shield = dur, 0
            g.log('You are wreathed in fire.')
        elif spell == 6:
            self.area(spell, [(p.X + dx, p.Y + dy) for dx, dy in RING8])
        elif spell == 20:
            h.mana = 0
            for _ in range(6):
                self.area(spell, [(p.X + dx, p.Y + dy) for dx, dy in RING8])
            g.log('Darkness falls.')

    def area(self, spell: int, tiles):
        g = self.g
        power = self.tell(spell, SP_POWER)
        for x, y in tiles:
            if not g.world.in_room(x, y):
                continue
            g.fx.append(('spell', spell, x, y))
            e = g.world.enemy_at(x, y)
            if e:
                if g.player.skill.hon == 1:
                    g.player.skill.hon = 2
                dmg = g.combat.hurt(power, e, 1, by_hero=True)
                g.log(f'{SPELL_NAMES[spell]} hits the {g.monster_name(e.type)} for {dmg}.')

    def cast_at(self, spell: int, x: int, y: int) -> None:
        g, w, p, h = self.g, self.g.world, self.g.player, self.g.player.hero
        target = w.enemy_at(x, y)
        h.mana -= self.tell(spell, SP_MANA)
        power = self.tell(spell, SP_POWER)
        name = SPELL_NAMES.get(spell, 'spell')
        g.fx.append(('spell', spell, x, y))
        if spell == 14:
            h.mana = 0
        if spell == 11:                                     # life drain
            if p.skill.hon == 1:
                p.skill.hon = 2
            dealt = g.combat.hurt(power, target, 1, by_hero=True) if target else 0
            if dealt > 0:
                h.life = min(h.mlife, h.life + dealt)
                g.log(f'You drain {dealt} life.')
            else:
                g.log('The drain has no effect.')
            return
        if spell in SUMMONS:
            e = g.spawn(SUMMONS[spell], x, y)
            g.log(f'{name}!')
            return
        if spell == 3:
            p.X, p.Y = x, y
            g.log('You teleport.')
            return
        if spell == 5:                                      # ring of ice: freeze if it beats magic armour
            if target:
                g.combat.hurt(0, target, 1, by_hero=True)
                if target in w.enemies:
                    if self.tell(4, SP_POWER) > target.marm:
                        target.att = -11 - self.tell(5, SP_DURATION)
                        g.log(f'The {g.monster_name(target.type)} is frozen solid!')
                    else:
                        g.log(f'The {g.monster_name(target.type)} resists the cold.')
            return
        if spell == 16:                                     # earthquake: the cross, the centre may shake again
            ww = 0
            while ww < 5:
                dx, dy = ((0, 0), (-1, 0), (0, -1), (1, 0), (0, 1))[ww]
                tx, ty = x + dx, y + dy
                if w.in_room(tx, ty):
                    g.fx.append(('spell', 16, tx, ty))
                    e = w.enemy_at(tx, ty)
                    if e:
                        dmg = g.combat.hurt(power, e, 1, by_hero=True)
                        g.log(f'The earth crushes the {g.monster_name(e.type)} for {dmg}.')
                    elif (tx, ty) == (p.X, p.Y):
                        dmg = g.combat.hurt(power, None, 1)
                        g.log(f'The earthquake hits you for {dmg}!')
                if ww == 0 and random(3) == 0:
                    ww -= 1
                ww += 1
            return
        if target:
            if p.skill.hon == 1:
                p.skill.hon = 2
            dmg = g.combat.hurt(power, target, 1, by_hero=True)
            g.log(f'{name} hits the {g.monster_name(target.type)} for {dmg}.' if dmg else f'{name} has no effect.')
        else:
            g.log(f'{name} strikes the ground.')
