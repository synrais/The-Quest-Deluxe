"""Quest Deluxe — launcher.

    python run_deluxe.py                start a new game of the pack in packs/quest1
    QUEST_PACK=mypack python run_deluxe.py   play packs/mypack instead
    python run_deluxe.py --level 3      start directly on level 3 (testing)
"""
import argparse

import pygame

from deluxe.game import Game


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--scale', type=int, default=2)
    args = ap.parse_args()
    pygame.init()
    window = pygame.display.set_mode((640 * args.scale, 480 * args.scale), pygame.RESIZABLE)
    game = Game(window, start_level=args.level)
    pygame.display.set_caption(f'{game.pack.quest.get("title", "The Quest")} - Deluxe')
    game.run()
    pygame.quit()


if __name__ == '__main__':
    main()
