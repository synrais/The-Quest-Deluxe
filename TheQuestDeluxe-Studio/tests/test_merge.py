"""Merging one quest into another (studio/merge.py): what is new, the same or clashing, the warnings with examples, the numbers that follow a
renumbered creature or item into maps, shops and loot, levels added after the last, one Undo, and old packs that open as they are.

Needs tkinter and a display (xvfb-run python tests/test_merge.py); everything is done on copies in a temporary folder.
"""
import copy
import os
import shutil
import sys
import tempfile
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
tmp = tempfile.mkdtemp()
os.environ['HOME'] = tmp

import core.custom as custom  # noqa: E402
import engine.pack as enginepack  # noqa: E402
custom_dir = os.path.join(tmp, 'Custom Maps')
enginepack.CUSTOM_DIR = custom.CUSTOM_DIR = custom_dir

from core.project import Project  # noqa: E402
from studio import merge, storytext  # noqa: E402
from studio.model import Session  # noqa: E402
from studio.pages import welcome  # noqa: E402

root = tk.Tk()
root.withdraw()


def check(name, cond, extra=''):
    assert cond, f'{name}  [{extra}]'


def count_squares(project, layer_index, value):
    return sum(1 for n in range(1, project.levels + 1) for x in range(1, 101) for y in range(1, 101) if project.grid(n).sq[x][y][layer_index] == value)


# the target: a blank quest; the source: The Quest with some things changed
target_path = welcome.make_quest('Target', True)
source_path = os.path.join(custom_dir, 'Source')
shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), source_path)
src = Project(source_path)
for r in src.tables['creatures']:
    if r['id'] == 1:
        r['name'] = 'Dragonling'; r['life'] = 99                   # the same number as the target's Imp, but a different creature
src.tables['items'].append({'id': 250, 'name': 'Moon Blade', 'price': 77, 'type': 'weapon', 'power': 9})
src.tables['creatures'].append({'id': 70, 'name': 'Moon Wolf', 'life': 40, 'power': 5, 'atk': 80, 'def': 20, 'range': 1, 'att': 5,
                                'loot': [[100, 100, 'item', 250]]})
src.tiles['floors'].append({'id': 9, 'name': 'Moon Dust', 'map_colour': [7, 8]})
src.grid(2).sq[12][12][3] = 70
src.grid(2).sq[13][12][2] = 250
src.grid(2).sq[14][12][0] = 9
src.shops[2][1] = src.shops[2].get(1, '1 2 3 4') + '\n250 1\n'
src.quest['title'] = 'The Other Quest'
src.dirty |= {'creatures', 'items', 'tiles', 'quest', ('map', 2), ('shops', 2)}
src.save()
src = Project(source_path)

session = Session(root, target_path)
dst = session.project
before_levels = dst.levels
before_creatures = copy.deepcopy(dst.tables['creatures'])

plan = merge.build_plan(src, dst)
by = lambda kind, key: plan.entry(kind, key)  # noqa: E731
check('a creature with a free number is new', by('creatures', 70).status == 'new')
check('the same creature in both is the same', by('creatures', 2).status in ('same', 'clash') and by('creatures', 3).status == 'same')
check('a different creature under the same number is a clash', by('creatures', 1).status == 'clash' and by('creatures', 1).mine == 'Imp', str(by('creatures', 1)))
check('a clash is renumbered unless told otherwise', by('creatures', 1).action == 'renumber')
check('settings differ', by('settings', 'title').status == 'clash' and by('settings', 'title').mine == 'Target' or by('settings', 'title').status == 'new')

# nothing ticked: a note, and nothing happens
w = merge.warnings(plan, src, dst)
check('nothing ticked is said', any('Nothing is ticked' in x.title for x in w))

for kind in ('creatures', 'items', 'floors', 'levels', 'stories'):
    plan.choose(kind)
plan.level_picks = [1, 2]
w = merge.warnings(plan, src, dst)
check('a renumbered creature is explained', any('Dragonling' in x.title and 'comes in as number' in x.title for x in w), str([x.title for x in w][:8]))
check('levels are said to go after the last', any('after your last level' in x.title for x in w))

# keep mine for one clash, replace another: the lost one is warned about with an example
plan.act('creatures', 1, 'skip')
w = merge.warnings(plan, src, dst)
check('keeping mine says what the maps will show instead', any('squares of creature 1 will be "Imp"' in x.title for x in w), str([x.title for x in w if 'squares' in x.title][:3]))
plan.act('creatures', 1, 'replace')
w = merge.warnings(plan, src, dst)
lost = [x for x in w if x.severity == 'lost']
check('replacing mine is a loss with the old name and the new', lost and 'Imp' in lost[0].title and 'Dragonling' in lost[0].title, str([x.title for x in lost]))
plan.act('creatures', 1, 'renumber')

rep = merge.apply(session, src, plan)
check('levels were added after the last', dst.levels == before_levels + 2 and rep.first_level == before_levels + 1, f'{dst.levels} {rep.first_level}')
new_imp = by('creatures', 1).new_key
check('the clashing creature came in under a free number', new_imp not in {r['id'] for r in before_creatures} and
      any(r['id'] == new_imp and r['name'] == 'Dragonling' for r in dst.tables['creatures']), str(new_imp))
check('the target\'s own Imp is untouched', any(r['id'] == 1 and r['name'] == 'Imp' for r in dst.tables['creatures']))
check('a new creature came in with its loot', any(r['id'] == 70 and r['loot'] == [[100, 100, 'item', 250]] for r in dst.tables['creatures']))
check('and the item it drops', any(r['id'] == 250 and r['name'] == 'Moon Blade' for r in dst.tables['items']))
check('the new floor came in', any(r['id'] == 9 and r['name'] == 'Moon Dust' for r in dst.tiles['floors']))
first = rep.first_level
imps_in_src = sum(1 for x in range(1, 101) for y in range(1, 101) if src.grid(1).sq[x][y][3] == 1)
check('the squares that had the clashing creature now have its new number', imps_in_src > 0 and
      sum(1 for x in range(1, 101) for y in range(1, 101) if dst.grid(first).sq[x][y][3] == new_imp) == imps_in_src, f'{imps_in_src} {new_imp}')
check('the new wolf, blade and dust are on the added level 2', dst.grid(first + 1).sq[12][12][3] == 70 and dst.grid(first + 1).sq[13][12][2] == 250
      and dst.grid(first + 1).sq[14][12][0] == 9)
check('its shop sells the blade', '250' in dst.shops[first + 1][1].split())
check('its story pages came with it, under free numbers', all(storytext.get(dst, n) is not None for n in dst.constant(first, 'STORIES', [])), str(dst.constant(first, 'STORIES', None)))
check('the pictures came too', (dst.picture('creatures', new_imp) is None) == (src.picture('creatures', 1) is None))
check('the settings were not touched (not ticked)', dst.quest['title'] == 'Target')

session.autosave()
re_read = Project(target_path)
check('it is on disk', re_read.levels == before_levels + 2 and any(r['id'] == 70 for r in re_read.tables['creatures']))
session.undo()
check('one Undo takes the whole merge back', dst.levels == before_levels and dst.tables['creatures'] == before_creatures and
      not any(r['id'] == 250 for r in dst.tables['items']), f'{dst.levels}')
session.redo()
check('and Redo brings it again', dst.levels == before_levels + 2)
session.undo()

# replace: the target's version is overwritten, and a setting too
plan2 = merge.build_plan(src, dst)
plan2.choose('creatures'); plan2.choose('settings')
plan2.act('creatures', 1, 'replace')
plan2.act('settings', 'title', 'replace')
merge.apply(session, src, plan2)
check('replace overwrites', any(r['id'] == 1 and r['name'] == 'Dragonling' for r in dst.tables['creatures']))
check('the settings chosen are copied', dst.quest['title'] == 'The Other Quest')
session.undo()
check('and it can be undone', dst.quest['title'] == 'Target' and any(r['id'] == 1 and r['name'] == 'Imp' for r in dst.tables['creatures']))
print('merge: new / same / clash, warnings with examples, renumbering followed into maps, shops, loot and stories, levels added, one Undo: ok')

# old packs: missing files and a wrong level count open and are mended
from studio import upgrade  # noqa: E402
old = os.path.join(tmp, 'old')
shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), old)
os.remove(os.path.join(old, 'skills.json'))
shutil.rmtree(os.path.join(old, 'levels', '7'))
os.makedirs(os.path.join(old, 'levels', '7'))
os.remove(os.path.join(old, 'text', 'questions.txt'))
import json  # noqa: E402
q = json.load(open(os.path.join(old, 'quest.json')))
q['levels'] = 3
json.dump(q, open(os.path.join(old, 'quest.json'), 'w'))
notes = upgrade.upgrade(old)
check('the mending is reported', notes and any('skills' in n for n in notes), str(notes))
p = Project(old)
check('an old pack opens, its levels counted from its folders', p.levels == 6 and p.tables['skills'], str(p.levels))
check('mending twice changes nothing more', upgrade.upgrade(old) == [])
print('merge: old packs with missing files open and are mended: ok')
root.destroy()
print('all merge checks passed')
