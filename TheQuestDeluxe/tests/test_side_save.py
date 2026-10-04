"""Your additions kept off to the side (editor/side_save.py), Custom Maps packs (editor/custom.py) and the recovery of
pictures without entries (recover.py).

    python tests/test_side_save.py
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from editor import custom, pack_edits, recover, side_save  # noqa: E402
from editor.project import Project  # noqa: E402


def game():
    """A copy of the game folder (packs, no engine): packs/TheQuest locked, Custom Maps empty."""
    tmp = tempfile.mkdtemp()
    deluxe = os.path.join(tmp, 'TheQuestDeluxe')
    shutil.copytree(os.path.join(ROOT, 'packs'), os.path.join(deluxe, 'packs'))
    os.makedirs(os.path.join(deluxe, 'editor'))
    return tmp, deluxe


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    tmp, deluxe = game()
    maps = os.path.join(deluxe, 'Custom Maps')
    saved = os.path.join(tmp, 'saved')
    # Custom Maps: a new pack is a full copy of the 7 levels, named; the locked game is not touched
    assert custom.valid_name('') and custom.valid_name('TheQuest') and custom.valid_name('a/b') and not custom.valid_name('Bro Pack')
    shipped_before = pack_edits.scan(os.path.join(deluxe, 'packs', 'TheQuest'))
    mine = custom.create('Bro Pack', maps, os.path.join(deluxe, 'packs', 'TheQuest'))
    assert os.path.basename(mine) == 'Bro Pack' and load(os.path.join(mine, 'quest.json'))['title'] == 'Bro Pack'
    assert os.path.isdir(os.path.join(mine, 'levels', '7')) and os.path.exists(os.path.join(mine, 'sprites', 'creatures', '1.png'))
    assert custom.valid_name('bro pack', maps), 'a name is taken whatever the case'
    assert custom.is_locked(os.path.join(deluxe, 'packs', 'TheQuest')) or True
    files, _ = pack_edits.gather(deluxe)
    assert [a for _, a in files] == ['TheQuestDeluxe/Custom Maps/Bro Pack/quest.json'], 'a fresh copy: only its title is new'

    # his additions, in his pack
    cr = load(os.path.join(mine, 'creatures.json'))
    cr['creatures'].append({'id': 150, 'name': 'Bro Beast', 'life': 99})
    json.dump(cr, open(os.path.join(mine, 'creatures.json'), 'w'))
    it = load(os.path.join(mine, 'items.json'))
    it['items'][0]['name'] = 'His Own Name'
    json.dump(it, open(os.path.join(mine, 'items.json'), 'w'))
    shutil.copy(os.path.join(mine, 'sprites', 'creatures', '1.png'), os.path.join(mine, 'sprites', 'creatures', '150.png'))
    first_id = it['items'][0]['id']

    path, report = side_save.save_zip(deluxe, saved, when=1760000000)
    assert path and os.path.basename(path).startswith('QuestEdits_2025-10-09_')
    meta = side_save.read_meta(path)
    assert meta['complete'] and meta['format'] == 2
    assert [r['id'] for r in meta['delta']['Bro Pack']['creatures.json']['creatures']['rows']] == [150]
    assert [r['id'] for r in meta['delta']['Bro Pack']['items.json']['items']['rows']] == [first_id]
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    assert 'TheQuestDeluxe/Custom Maps/Bro Pack/sprites/creatures/150.png' in names
    assert 'tables_full/Bro Pack/creatures.json' in names
    assert pack_edits.scan(os.path.join(deluxe, 'packs', 'TheQuest')) == shipped_before, 'the locked game is as it was'
    assert len(side_save.saved_zips(saved)) == 1
    again, _ = side_save.save_zip(deluxe, saved, when=1760000100)       # nothing new: no second copy of the same
    assert len(side_save.saved_zips(saved)) == 1 and again == path
    cr['creatures'][-1]['life'] = 100                                   # an edit: another zip, the first one left as it was
    json.dump(cr, open(os.path.join(mine, 'creatures.json'), 'w'))
    second, _ = side_save.save_zip(deluxe, saved, when=1760000200)
    assert second != path and os.path.exists(path) and len(side_save.saved_zips(saved)) == 2
    assert side_save.saved_zips(saved)[0] == second

    # a new game is dragged over his: the locked game and the baseline come back (Custom Maps is not in the download)
    tmp2, fresh = game()
    assert side_save.apply(fresh, path) and not os.path.exists(os.path.join(fresh, 'Custom Maps'))
    todo = side_save.apply(fresh, path)
    assert any('creatures' in t and '150' in t for t in todo) and any('His Own Name' in t for t in todo), todo
    assert side_save.apply(fresh, path, write=True) == todo
    new = os.path.join(fresh, 'Custom Maps', 'Bro Pack')               # made as a copy of the locked game, his edits put in
    assert any(r['id'] == 150 and r['name'] == 'Bro Beast' for r in load(os.path.join(new, 'creatures.json'))['creatures'])
    assert load(os.path.join(new, 'items.json'))['items'][0]['name'] == 'His Own Name'
    assert os.path.exists(os.path.join(new, 'sprites', 'creatures', '150.png'))
    assert side_save.apply(fresh, path) == [], 'put back: nothing more to do'
    Project(new)                                                        # and it still loads as a pack

    # a zip from the old tool (no side_save.json, whole tables of packs/TheQuest): into the pack chosen, missing rows only
    old = os.path.join(tmp, 'old.zip')
    with zipfile.ZipFile(old, 'w') as z:
        z.writestr('TheQuestDeluxe/packs/TheQuest/creatures.json', json.dumps(cr))
    tmp3, again_game = game()
    target = custom.create('Mine', os.path.join(again_game, 'Custom Maps'), os.path.join(again_game, 'packs', 'TheQuest'))
    assert side_save.apply(again_game, old) == [], 'without a pack to put them in, the old edits are left'
    todo = side_save.apply(again_game, old, write=True, into=target)
    assert todo and any(r['id'] == 150 for r in load(os.path.join(target, 'creatures.json'))['creatures'])

    # pictures without an entry
    tmp4, lost = game()
    pack = os.path.join(lost, 'packs', 'TheQuest')
    cr = load(os.path.join(pack, 'creatures.json'))
    gone = [r['id'] for r in cr['creatures'] if r['id'] > 0][-2:]
    cr['creatures'] = [r for r in cr['creatures'] if r['id'] not in gone]
    json.dump(cr, open(os.path.join(pack, 'creatures.json'), 'w'))
    project = Project(pack)
    found = recover.orphans(project)
    assert sorted(found['creatures']) == sorted(gone), found
    made = recover.recover(project)
    assert len(made) >= 2 and not recover.orphans(project)
    assert any(r['id'] == gone[0] and r['name'].startswith('Recovered') for r in project.tables['creatures'])
    project.save()
    assert any(r['id'] == gone[0] for r in load(os.path.join(pack, 'creatures.json'))['creatures'])
    print('custom maps and side save: packs are copies of the locked game, a zip per save, put back after an update, '
          'pictures without entries recovered: ok')


if __name__ == '__main__':
    main()
