"""The PC speaker: Borland's sound(freq) / nosound(), as a square wave through pygame.mixer.

The original's asound() plays a tone only when sound.txt holds 1 (the manual: "1=sound, 0=no
sound"). The Quest Deluxe reads sound.txt from its folder, else from the quest pack (as sound.txt); with
neither, the sound is on.
"""
from __future__ import annotations

import array
import os

import pygame

from . import speed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the TheQuestDeluxe folder

RATE = 22050
VOLUME = 0.12


def sound_setting(source=None) -> bool:
    path = os.path.join(ROOT, 'sound.txt')
    try:
        if os.path.exists(path):
            with open(path, 'rb') as fh:
                raw = fh.read()
        elif source is not None:
            raw = source.read('sound.txt')
        else:
            return True
        return raw.split()[0] == b'1' if raw.split() else False
    except (OSError, FileNotFoundError):
        return True


class Speaker:
    """sound(freq) / nosound() as the original calls them. At 1x a tone plays while the game waits. When the game is sped up (engine.speed) the waiting
    is shorter than the tone: the speaker then keeps its own clock (advance(), told each delay in the original's milliseconds), cuts each tone and
    rest to the length the original gives it and plays them one after another, so the sounds are the same pitch and speed at any game speed."""
    BACKLOG = 8000                                           # ms of sound that may be waiting its turn (the oldest is dropped past it)
    LONGEST_REST = 1500                                      # ms of silence kept between two tones of one run

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.channel = None
        self.freq = 0
        self.t = 0                                           # the original's time, in ms, as the delays have told it
        self._note = None                                    # (freq, when it began) while a tone is sounding in a sped up game
        self._last_end = 0
        self.queue: list = []                                # [(freq or 0 for a rest, ms)] waiting to be played
        self._cache: dict = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=RATE, size=-16, channels=1)
            self.rate, _, self.chans = pygame.mixer.get_init()
            self.channel = pygame.mixer.Channel(0)
        except pygame.error:
            self.enabled = False

    def _wave(self, freq: int) -> pygame.mixer.Sound:
        snd = self._cache.get(freq)
        if snd is None:
            cycles = max(1, round(freq * 0.1))               # ~0.1 s of whole cycles, looped
            n = max(2, round(cycles * self.rate / freq))
            amp = int(32767 * VOLUME)
            samples = array.array('h')
            for k in range(n):
                v = amp if (k * cycles * 2 // n) % 2 == 0 else -amp
                samples.extend([v] * self.chans)
            snd = pygame.mixer.Sound(buffer=samples.tobytes())
            self._cache[freq] = snd
        return snd

    def _piece(self, freq: int, ms: int) -> pygame.mixer.Sound:
        """A tone of exactly ms milliseconds (freq 0: a rest)."""
        key = (freq, ms)
        snd = self._cache.get(key)
        if snd is None:
            n = max(2, round(self.rate * ms / 1000))
            amp = int(32767 * VOLUME)
            samples = array.array('h')
            if freq:
                period = self.rate / freq
                samples.extend(amp if (k % period) < period / 2 else -amp for k in range(n))
            else:
                samples.extend([0] * n)
            if self.chans > 1:
                wide = array.array('h')
                for v in samples:
                    wide.extend([v] * self.chans)
                samples = wide
            if len(self._cache) > 400:
                self._cache = {k: v for k, v in self._cache.items() if not isinstance(k, tuple)}
            snd = self._cache[key] = pygame.mixer.Sound(buffer=samples.tobytes())
        return snd

    def sound(self, freq: int):
        if not self.enabled or freq == self.freq:
            return
        freq &= 0xFFFF
        if speed.get() > 1:                                  # sped up: noted, and played at its own length when it ends
            self._close_note()
            self.freq = freq
            self._note = (freq, self.t)
            return
        self.freq = freq
        if 20 <= freq <= 20000:
            self.channel.play(self._wave(freq), loops=-1)
        else:
            self.channel.stop()

    def nosound(self):
        if not self.enabled:
            return
        if self._note is not None:
            self._close_note()
        elif self.freq:
            self.channel.stop()
        self.freq = 0

    # ── a sped up game ──────────────────────────────────────────────────────
    def advance(self, ms: float):
        """The game waited ms of the original's time (a delay() of an animation, sped up or not)."""
        self.t += ms
        if self.queue:
            self.pump()

    def _close_note(self):
        note, self._note = self._note, None
        if note is None:
            return
        freq, began = note
        ms = int(self.t - began)
        if ms <= 0:
            return
        playing = bool(self.queue) or self.channel.get_busy()
        if playing and began > self._last_end:               # the silence before it, so the run keeps its rhythm
            self.queue.append((0, int(min(began - self._last_end, self.LONGEST_REST))))
        self.queue.append((freq if 20 <= freq <= 20000 else 0, ms))
        self._last_end = self.t
        while sum(m for _, m in self.queue) > self.BACKLOG:
            self.queue.pop(0)
        self.pump()

    def pump(self):
        """Hand the next waiting tones to the channel: one playing and one queued behind it, so there is no gap between them."""
        if not self.enabled:
            return
        while self.queue:
            if not self.channel.get_busy():
                self.channel.play(self._piece(*self.queue.pop(0)))
            elif self.channel.get_queue() is None:
                self.channel.queue(self._piece(*self.queue.pop(0)))
            else:
                break
