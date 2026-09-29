"""Spells: port of cast() (RPG.CPP 0a45:832a).

Spells.dat columns: id, required INT, mana, range (0 = self), power, duration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .rules import random, SP_INT, SP_MANA, SP_RANGE, SP_POWER, SP_DURATION

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
    def strike(self, spell: int, e, x: int, y: int):
        """cast()'s common blow: Honor is engaged, hurt(power, w, 1, -1), and bhit(5) (the spell is
        absorbed) when it did no damage. The original shows no text for any of this."""
        g, p = self.g, self.g.player
        if p.skill.hon == 1:
            p.skill.hon = 2
        if g.combat.hurt(self.tell(spell, SP_POWER), e, 1, by_hero=True) == 0:
            g.play_at('bhit', x, y, 5)

    def cast_self(self, spell: int) -> None:
        """The range-0 half of cast(): mana first, then each spell with its animation on the hero."""
        g, p, h, st = self.g, self.g.player, self.g.player.hero, self.g.status
        h.mana -= self.tell(spell, SP_MANA)
        power, dur = self.tell(spell, SP_POWER), self.tell(spell, SP_DURATION)
        if spell in HEAL_SPELLS:
            h.life = min(h.mlife, h.life + power)
            g.play_at({1: 'aheal', 10: 'arestore', 17: 'acure'}[spell], p.X, p.Y)
        elif spell == 7:
            h.invisible = dur + 1
            for e in g.world.enemies:
                if e.att > 0 and e.att != 8 and e.att > -10:
                    e.att = -5
            g.play_at('ainvisibility', p.X, p.Y)
        elif spell == 4:
            st.Shield, st.fShield = dur, 0
            g.play_at('ashield', p.X, p.Y, 1)
        elif spell == 13:
            st.fShield, st.Shield = dur, 0
            g.play_at('ashield', p.X, p.Y, 2)
        elif spell == 6:
            self.area(spell, 'ablackward', [(p.X + dx, p.Y + dy) for dx, dy in RING8])
        elif spell == 20:
            h.mana = 0
            for _ in range(6):
                self.area(spell, 'adarkhour', [(p.X + dx, p.Y + dy) for dx, dy in RING8])

    def area(self, spell: int, anim: str, tiles):
        """Black Ward / Dark Hour: each square around the hero in turn, animation then the blow."""
        g = self.g
        for x, y in tiles:
            if not g.world.in_room(x, y):
                continue
            g.play_at(anim, x, y)
            e = g.world.enemy_at(x, y)
            if e:
                self.strike(spell, e, x, y)

    def cast_at(self, spell: int, x: int, y: int) -> None:
        """The targeted half of cast(), in the original order."""
        g, w, p, h = self.g, self.g.world, self.g.player, self.g.player.hero
        target = w.enemy_at(x, y)
        h.mana -= self.tell(spell, SP_MANA)
        power = self.tell(spell, SP_POWER)
        if spell == 2:
            g.play_at('aflame', x, y, 0)
        if spell == 12:
            for _ in range(5):
                g.play_at('athunder', x, y)
        if spell == 9:
            g.play_at('ainferno', x, y, 0)
        if spell == 19:
            g.play_at('adeaths', x, y)
        if spell == 14:
            g.play_at('adeteriorate', x, y, 40)
            h.mana = 0
        if spell == 11:                                     # life drain
            if p.skill.hon == 1:
                p.skill.hon = 2
            g.play_at('adrain', x, y, 1)
            dealt = g.combat.hurt(power, target, 1, by_hero=True)
            if dealt < 1:
                g.play_at('bhit', x, y, 5)
            g.play_at('adrain', p.X, p.Y, 2)
            if dealt > 0:
                h.life = min(h.mlife, h.life + dealt)
            return
        if spell in SUMMONS:
            g.play_at({8: 'asskeleton', 18: 'asscorpion', 15: 'astoneknight'}[spell], x, y,
                      *((1,) if spell == 8 else ()))
            g.spawn(SUMMONS[spell], x, y)
            return
        if spell == 3:
            def move(sx, sy):
                ox, oy = w.origin
                p.X, p.Y = ox + sx - 1, oy + sy - 1
            g.play_at('ateleport', x, y, *g.on_screen(p.X, p.Y), on_move=move)
            return
        if spell == 5:                                      # ring of ice: freeze if it beats magic armour
            g.play_at('aicering', x, y)
            g.combat.hurt(0, target, 1, by_hero=True)       # even with nobody there: hurt(0, -1, ...)
            if target:
                if self.tell(4, SP_POWER) > target.marm:
                    target.att = -11 - self.tell(5, SP_DURATION)
                else:
                    g.play_at('bhit', x, y, 5)
            return
        if spell == 16:                                     # earthquake: the cross, the centre may shake again
            ww = 0
            while ww < 5:
                dx, dy = ((0, 0), (-1, 0), (0, -1), (1, 0), (0, 1))[ww]
                tx, ty = x + dx, y + dy
                if w.in_room(tx, ty):
                    g.play_at('aearthq', tx, ty)
                    e = w.enemy_at(tx, ty)
                    if e:
                        self.strike(spell, e, tx, ty)
                    elif (tx, ty) == (p.X, p.Y):
                        g.combat.hurt(power, None, 1)
                        if h.life < -5:
                            return
                if ww == 0 and random(3) == 0:
                    g.play('pause', 100)
                    ww -= 1
                ww += 1
            return
        if target:
            self.strike(spell, target, x, y)
