"""What the editor's tooltips say. FIELDS: what each field of the Items, Creatures, Spells, Classes and Tiles
tabs does, by its name in the pack's files; BUTTONS: buttons, tools and boxes, by their text. apply(widget)
gives every widget inside it whose text is listed here its tooltip; the tables' forms add their own."""
from __future__ import annotations

from .uikit import tip

FIELDS = {
    'id': 'The number the maps, scripts and other tables use for it. It cannot be changed; Duplicate makes '
          'a new one.',
    '_role': 'Monsters have numbers above 0, people -1 to -99 (-5 is a shopkeeper), summoned allies -100 and below.',
    # creatures
    'name': 'The name shown in the editor and in messages ("the <name> hits you").',
    'log_name': "The name in the combat log (D in the game). Empty: the name, in lower case.",
    'life': 'Hit points. When they run out it dies. For a class, the hero starts with this many.',
    'power': 'The damage of its blows or spells, varied by up to a third each time, before armour takes some off. '
             'For a weapon: the damage it adds.',
    'atk': 'Chance to hit: its attack minus the defender\'s defence is the percent chance. 0 for a creature that '
           'only casts.',
    'def': "Makes it harder to hit: the attacker's chance falls by this many percent.",
    'warm': 'Weapon armour: taken off every blow from a weapon, arrow or sling stone (magic ignores it).',
    'marm': 'Magic armour: taken off every blow from a spell or a magic weapon.',
    'range': '1 = it fights hand to hand. More: it shoots arrows or casts spells from that many squares away. '
             'For a spell: how far the target may be (0 = on the hero).',
    'att': 'How it behaves: hostile (and how far it sees), neutral until hit, peaceful, a follower, or a caster '
           'that stays away.',
    'exp': 'Experience the hero gets for killing it (the hero levels up as the number runs out).',
    'loot': 'What it drops. A roll of 1-100 is made and the first rule whose range holds it applies, e.g. '
            '"20-100: gold 3+1; 10-20: item 620".',
    'drop_on_level': 'An item it always drops on a level: "level: item".',
    'corpse': 'What it leaves: a body (blood and remains), bones (which a necromancer can raise) or nothing.',
    'bleeds': 'Does it leave blood when hurt? Fire spells with Burns can clear it.',
    'magic_attack': 'Its blows are magic: stopped by magic armour instead of weapon armour.',
    'poison_melee': 'Its hand-to-hand blows poison the hero 1 time in this many.',
    'poison_ranged': 'Its missiles poison the hero 1 time in this many.',
    'poison_cast': 'Its spells poison the hero 1 time in this many.',
    'missile_anim': 'The picture that plays where its (or the weapon\'s) missile lands: a stone, arrow or bolt.',
    'cast_anim': 'The spell animation it plays when it casts. Pick a name from the list, then add its numbers '
                 '(e.g. aflame 1).',
    'heals_allies': 'Instead of attacking it heals wounded creatures on its side (a cleric).',
    'raises_dead': 'Turns bones on the screen into this creature (a necromancer).',
    'explodes': 'Blasts the hero this many times, then dies.',
    'drains_life': 'Heals itself by the damage its spell does.',
    'invisible': 'Not drawn and not a target, until it attacks (see Shows itself as). A potion of foresight shows it.',
    'reveals_as': 'The creature it turns into when it attacks, so that it can be seen.',
    'hides_as': 'The creature it turns back into when the hero leaves the screen.',
    'rests_after_moving': "It does not attack in a turn in which it moved.",
    'animal': "Doesn't fight people, and killing it earns no reputation penalty or reward.",
    'silences_witnesses': 'Nobody reports a killing that happens near it.',
    'size': 'Squares across: 2 is a giant on 2 x 2 squares. Put it on the map at its top-left square and keep the '
            'others free. Its picture is stretched to fit.',
    'regenerates_from_blood': 'After it dies the nearest pile of blood on the screen slides to its body and it rises '
                              'again at full life. Burn the blood and it stays dead.',
    'blood_range': 'How many squares from its body blood still feeds it. Empty: the whole screen.',
    'resists': "Elements it shrugs off: fire, ice, poison, drain (weapons, arrows and spells).",
    # items
    'type': 'What kind of thing it is. This decides which of the fields below apply.',
    'bag_name': 'The name printed under the map in the inventory.',
    'price': "Its price in gold in shops. Empty: it isn't sold.",
    'view3d': 'How FPS mode shows it: flat on the ground, small, or full size. Walls: a block, a billboard or flat.',
    'req_str': 'Strength the hero needs to use it.',
    'req_int': 'Intelligence needed to use it (for a spell: to learn and cast it).',
    'kind': 'Weapons: normal, double strike (1 in 5), parry (1 in 5), magic (ignores armour), ranged, two-handed.',
    'str': 'Strength it adds while worn.', 'int': 'Intelligence it adds while worn.',
    'dex': 'Dexterity it adds while worn.', 'acc': 'Accuracy it adds while worn.',
    'fires': 'The kinds of ammunition this launcher shoots.',
    'fps_attack': "How the weapon in view moves when the hero attacks in FPS mode.",
    'fps_turn': 'Degrees to turn its picture so that it stands upright in the hand in FPS mode.',
    'no_ammo_bonus': 'Ammunition that doubles a launcher\'s power (poisoned arrows) does not, with this one.',
    'power_x2': "Doubles the power of the launcher that shoots it (poisoned arrows).",
    'power_bonus': 'An amulet adds its power to melee blows, or to shots.',
    'potion': 'Which potion it is: 1-8 are the original\'s, 9 and 10 are set on the Quest tab.',
    'key': 'The colour of lock it opens. More colours are set on the Quest tab.',
    'quest': "A quest item: it can't be sold or dropped.",
    'regen': 'Life the hero gains every turn while he wears it.',
    'mana_regen': 'Mana the hero gains every turn while he wears it.',
    'thorns': 'Damage to any creature that hits the hero in melee, while worn.',
    'lifesteal': 'Percent of the damage of his melee blows that heals him, while worn.',
    'sight': 'Squares further the eye sees in FPS mode, while worn.',
    'poison_immune': 'Nothing can poison him while he wears it.',
    'see_invisible': 'Invisible creatures show for what they are (like a potion of foresight), while worn.',
    'water_walk': 'He can walk on water: walls that freeze to ice (water) do not stop him.',
    'makes_small': 'He is small while he wears it: through small-only walls, low eyes in FPS mode. With Makes him a '
                   'giant as well, they cancel.',
    'makes_giant': 'He is a giant while he wears it: hits half as hard again, smashes giant-only walls, high eyes.',
    'pickup.grow': 'Picked up with Enter, it is eaten at once and the hero grows for this many turns '
                   '(a shrinking effect running instead cancels).',
    'pickup.shrink': 'Picked up with Enter, it is eaten at once and the hero shrinks for this many turns.',
    'pickup.life': 'Life gained (or, with a minus, lost) when it is eaten.',
    'pickup.mana': 'Mana gained when it is eaten.',
    'pickup.foresight': 'Turns of foresight when it is eaten.',
    'pickup.poison': 'It poisons the hero when eaten.',
    'pickup.message': 'What the combat log says (empty: "You eat the <name>.").',
    'giant_breaks': 'A solid wall that a giant (potion of gigantism, or an item) smashes down by walking into it.',
    'element': 'What a hit adds: fire and poison keep hurting, ice freezes, drain heals the hero. '
               'A bow and its arrows both count.',
    'element_chance': 'Percent of hits that the element takes hold on. Empty: every hit.',
    'element_power': 'Damage a turn while it burns or is poisoned (empty: 3).',
    'element_turns': 'Turns it burns, is poisoned or stays frozen (empty: 3).',
    # spells
    'mana': 'Mana it costs to cast.',
    'duration': 'Turns it lasts (shield, invisibility, freeze, clones, disguise, ice).',
    'effect': 'What the spell does. The fields that apply to the effect appear below.',
    'anim': 'The animation it plays. Pick a name from the list, then add its numbers (e.g. aflame 0).',
    'repeat': 'How many times the animation (or the ward) repeats.',
    'creature': 'The ally it summons (-100 and below).',
    'fizzle': 'Percent chance the spell fails.',
    'empties_mana': 'Casting it leaves the hero with no mana.',
    'needs_target': 'Can only be cast at a creature.',
    'burns': 'Fire: burns the blood off the ground within this many squares of where it lands (0: that square). '
             'Bones stay.',
    'freezes_water': 'Frost: turns water within this many squares to ice for the Duration (10 turns if none). '
                     'The water tile needs a "Freezes to" ice tile.',
    'clones_hero': "Each clone has this percent of the hero's life, power and armour. Empty: the creature's own.",
    'npc_anger': 'Percent chance that each friendly person turns on the disguised hero (50 if empty).',
    'creatures': 'The shapes a disguise picks from. None ticked: any monster that shows.',
    'absorb_power_of': "Quest I's Shield reads another spell's power (a bug the original has).",
    'freeze_power_of': "Quest I's Ring of Ice reads another spell's power (a bug the original has).",
    # classes
    'growth': 'What the hero gains at each level-up: life, then mana.',
    'skill': 'The skill this class always has.',
    'no_skill': 'Skills character creation does not offer this class.',
    'no_fault': 'Faults character creation does not offer this class.',
    'look.colour': 'The colour the hero is drawn in. Or paint him: the Painted hero picture replaces this.',
    'look.shield_and_sword': 'Draws a shield and sword on the hero.',
    'bag': 'What the hero starts with, by place (weapon, off hand, helmet, armour, amulet, backpack).',
    'spells': 'The spells this class knows from the start.',
    'reclass': 'Whether the hero can change class at level-ups (see the Quest tab).',
    # tiles
    'solid': 'Blocks the way for the hero and every creature.',
    'small_only': 'A solid wall that a hero under a potion of shrinking can walk through (a crack, a mouse hole). '
                  'Give it the billboard look for FPS mode.',
    'door': 'Opens when walked into: a plain door, a secret one, or one that needs a key.',
    'map_colour': 'Its colour on the level map: EGA colour, priority.',
    'role': 'What the engine puts this decoration down for (blood, bones, an open door ...). One decoration each.',
    'roof': 'Indoors: the wall picture FPS mode draws overhead.',
    'water': 'Water: a hero wearing something that lets him walk on water crosses it. (A wall that freezes counts '
             'as water too.)',
    'freezes_to': 'Water: the wall (ice, not solid) that a freezing spell turns it into.',
    'needs_item': 'Walked into with this item in the bag, the wall gives way (a boulder, rubble, a hedge).',
    'becomes': 'What the wall becomes when it gives way. Clear: nothing is left.',
    'consumes': 'The item is used up when the wall gives way.',
    'message': 'Said in the combat log when it gives way.',
    'blocked_message': 'Said in the combat log when you walk into it without the item.',
}

BUTTONS = {
    # the window
    'Save': 'Write everything to the pack folder (Ctrl+S).',
    'Play from here (F5)': 'Test play: starts the game on the level with a new hero of the chosen class, on the '
                           'square you clicked last on the map (or the level start).',
    # the map tab
    'Paint': 'Left button paints the chosen thing; drag to draw a line of squares. Right button picks what is '
             'under the pointer.',
    'Rectangle': 'Drag to fill a rectangle with the chosen thing.',
    'Fill': 'Click to fill the connected area that has the same thing in this layer.',
    'Pick': 'Click a square to take what is on it into the palette (the right button does this with any tool).',
    'Start': 'Click the square where the hero arrives on this level.',
    'Shop': 'Click a screen to say which shop its shopkeeper runs. Shops are stocked on the Shops tab.',
    'Peaceful': "Click a screen to make it one where people and allies leave monsters alone.",
    'Link': 'Click a ladder, rope, stairs, hole or jump pad (put it on the map first) to say where it leads: a '
            'square on another level. Can make the way back too.',
    'Floor': 'The ground. Every square has one.', 'Wall / door': 'Walls, trees, water and doors.',
    'Decoration': 'Blood, bones, an open door and other things drawn over the floor.',
    'Item': 'Things lying on the ground: chests, potions, weapons, stairs and ladders ...',
    'Creature': 'Monsters and people standing on the map.', 'Gold': 'A heap of gold: set how much below.',
    'Gold per square': 'How much gold the Gold layer puts on each square.',
    'Screens': 'Show the yellow lines between the 10 x 10 screens.',
    'Squares': 'Show a thin line round every square, inside each screen.',
    'Add': 'Add a new level at the end, or add this to the list.',
    'Remove last': 'Remove the last level, its map, script and shops.',
    'Apply': 'Keep the settings above.',
    'Pick...': 'Choose from a list.',
    '3D view from here...': "Opens a first-person view of the level from the square you clicked, as FPS mode "
                            "shows it. F5 in that window refreshes it.",
    'Stories before it': 'Story screens (from the Stories tab) shown before the level starts: numbers like 2, 3.',
    'Teleporter jump': 'How far a teleporter pad sends the hero: dx, dy squares.',
    'Ask before leaving': 'Ask "Want to travel further?" at the level exit.',
    'Jingle when leaving': 'Play the leaving tune at the exit.',
    '3D sky colour': 'FPS mode: the EGA colour (0-15) of the sky. Empty: the default.',
    '3D fog colour': 'FPS mode: the colour distance fades into. Empty: the sky colour.',
    '3D range': 'FPS mode: how many squares the eye sees (2-30).',
    # the tables
    'New': 'Make a new entry (spells and creatures ask what to start from).',
    'Duplicate': 'Copy the chosen entry, with its pictures, under a new number.',
    'Delete': 'Delete the chosen entry. You are told where it is still used first.',
    'Find': 'Type to narrow the list.',
    'Paint...': 'Opens the painter on this picture. In it you can start from another picture.',
    'Import...': 'Use a picture file (png, gif, bmp). It is scaled to 40 x 40 and its colours are made EGA ones.',
    'New ammo kind...': 'Makes a whole new kind of ammunition: stacks of 1 to 20, each its own item.',
    # the painter
    'Pencil': 'Paint pixels; drag to draw.', 'Line': 'Drag from one end of a line to the other.',
    'Clear': 'Empty the whole picture (Undo brings it back).',
    'Left': 'Move the picture one pixel left (or: the left button colour).',
    'Right': 'Move the picture one pixel right (or: the right button colour).',
    'Up': 'Move the picture one pixel up.', 'Down': 'Move the picture one pixel down.',
    'Flip ↔': 'Mirror the picture left to right.', 'Flip ↕': 'Turn the picture upside down.',
    'Use it (Undo goes back)': 'Replace the picture with the one chosen above, to change it into yours.',
    'Close': 'Close the painter (it asks about unsaved changes).',
    # events
    'Check': 'Reads the text the way the game will and marks any line it cannot understand.',
    'Add an event...': 'Builds a rule from drop-down menus (when, only if, then) and writes the script and any '
                       'Dialogue lines for you.',
    'A message...': 'Pick a Dialogue line: inserts say(n) inside talk(), message(person, n) elsewhere.',
    'An item...': 'Pick an item and put its number into the script.',
    'A creature...': 'Pick a creature and put its number into the script.',
    'A story...': 'Pick a story and put its number into the script.',
    'Add a condition': 'The event only happens if this is true. Several are all needed.',
    'Remove the selected': 'Take the chosen action out of the list.',
    'Add the event to the script': 'Writes the rule into the level script (and its words into the Dialogue).',
    'Insert': 'Put the chosen number into the script at the cursor.',
    'Add a handler:': 'Adds an empty handler (a place the game calls your script) to this level script.',
    'New line': 'A new Dialogue line for the chosen level and person.',
    'Title': 'The quest\'s name, shown by the game and the editor.', 'Author': 'Who made the quest.',
    'Year': 'The year, shown on the title screen.', 'First level': 'The level a new game starts on.',
    'Class changes': 'Whether the hero can change class at level-ups, and by which rule.',
    'Starting potions': 'Potions a new hero carries: "potion number: count", e.g. 6: 1.',
    'More key colours': 'Key colours past the original\'s yellow, red and blue: "name: EGA colour".',
}


def apply(widget):
    """Give a tooltip to every widget under `widget` whose text is in BUTTONS."""
    try:
        text = widget.cget('text')
    except Exception:                               # noqa: BLE001  (not every widget has text)
        text = ''
    if isinstance(text, str) and text in BUTTONS:
        tip(widget, BUTTONS[text])
    for child in widget.winfo_children():
        apply(child)


def field_tip(field) -> str:
    explain = FIELDS.get(field.key) or FIELDS.get(field.key.split('.')[-1], '')
    hint = field.hint or ''
    if explain and hint and hint.lower() not in explain.lower():
        return f'{field.label}\n{explain}\n({hint})'
    return f'{field.label}\n{explain or hint}' if (explain or hint) else ''
