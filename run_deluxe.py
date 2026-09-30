"""Quest Deluxe — launcher.

    python run_deluxe.py                       a new game of packs/quest1, from the title
    python run_deluxe.py --pack mypack         play packs/mypack (or any pack folder)
    python run_deluxe.py --level 3             new games start on level 3

Test play (what the editor's Play button runs): skip the title and character creation and put a
new hero of the given class straight on a level, optionally on a square:

    python run_deluxe.py --pack mypack --quick 1 --level 2 --at 45,60
"""
import argparse
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', help='a pack folder, or a name under packs/')
    ap.add_argument('--level', type=int, default=None)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--quick', type=int, metavar='CLASS', help='start at once with a hero of this class')
    ap.add_argument('--at', help='x,y: where the quick-start hero stands')
    args = ap.parse_args()
    if args.pack:
        os.environ['QUEST_PACK'] = args.pack          # before the engine loads the pack

    import pygame
    from deluxe.game import Game

    pygame.init()
    window = pygame.display.set_mode((640 * args.scale, 480 * args.scale), pygame.RESIZABLE)
    game = Game(window, start_level=args.level or 1)
    pygame.display.set_caption(f'{game.pack.quest.get("title", "The Quest")} - Deluxe')
    if args.quick:
        at = tuple(int(v) for v in args.at.split(',')) if args.at else None
        game.quick_start(args.quick, args.level or game.pack.quest.get('first_level', 1), at)
    game.run()
    pygame.quit()


if __name__ == '__main__':
    main()
