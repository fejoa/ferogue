#!/usr/bin/env python
import libtcodpy as tcod
import math
import textwrap
import shelve

FULLSCREEN = False
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

# Sizes and coordinates relevant to the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

INVENTORY_WIDTH = 50

MAP_WIDTH = 80
MAP_HEIGHT = 43
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

TURN_BASED = True
TRADITIONAL_LOOK = False
SHOW_ROOM_NUMBERS = False

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

HEAL_AMOUNT = 4
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 10
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

# Experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

tcod.sys_set_fps(LIMIT_FPS)

con = tcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = tcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

colour_dark_wall = tcod.Color(0, 30, 0)
colour_dark_ground = tcod.Color(20, 60, 20)
colour_light_wall = tcod.Color(130, 110, 50)
colour_light_ground = tcod.Color(200, 180, 50)


class Item:
    # An item that can be picked up and used
    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        # Add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            add_message('Your inventory is full, cannot pick up ' + self.owner.name + '.', tcod.yellow)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            add_message('A ' + self.owner.name + ' picked up.', tcod.green)

    def use(self):
        # Just call the "use_function" if it is defined
        if self.use_function is None:
            add_message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) # destroy after use, unless it was cancelled for some reason

    def drop(self):
        # Add to the map and remove from the player's inventory
        # Also, Place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        add_message('You drop a ' + self.owner.name + '.' + tcod.yellow)


class Fighter:
    # Combat-related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.xp = xp
        self.death_function = death_function

    def take_damage(self, damage):
        # Apply damage if possible
        if damage > 0:
            self.hp -= damage
            # Check for death, if there is a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)
        if self.owner != player: # yield experience to the player
            player.fighter.xp += self.xp

    def attack(self, target):
        # A simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            # Make the target take some damage
            add_message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', tcod.grey)
            target.fighter.take_damage(damage)
        else:
            add_message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect.', tcod.grey)

    def heal(self, amount):
        # Heal by the given amount
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp


class BasicMonster:
    # AI for a basic monster
    def take_turn(self):
        # A basic monster takes its turn. If PC can see it, it can see PC
        monster = self.owner
        if tcod.map_is_in_fov(fov_map, monster.x, monster.y):
            # Move towards PC if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            # If close enough, attack if player is still alive
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class ConfusedMonster:
    # AI for a temporarily confused monster
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:
            # Move randomly
            self.owner.move(tcod.random_get_int(0, -1, 1), tcod.random_get_int(0, -1, 1))
            self.num_turns -= 1

        else: # Restore the previous AI and delete this AI
            self.owner.ai = self.old_ai
            add_message('The ' + self.owner.name + ' is no longer confused!', tcod.orange)


class Rect:
    # A rectangle on the map, used to characterise a room
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def centre(self):
        centre_x = (self.x1 + self.x2) // 2
        centre_y = (self.y1 + self.y2) // 2
        return (centre_x, centre_y)

    def intersect(self, other):
        # Returns true if this rectangle intersects with another one
        return(self.x1 <= other.x2 and self.x2 >= other.x1 and
               self.y1 <= other.y2 and self.y2 >= other.y1)


class Tile:
    # A tile of the map and its properties
    def __init__(self, blocked, block_sight=None):
        self.explored = False
        self.blocked = blocked

        # By default, if a tile is blocked, it also blocks sight
        block_sight = blocked if block_sight is None else None
        self.block_sight = block_sight


class Object:
    # This is a generic object: the player, a monster, an item, the toilet...
    # It's always represented by a character on the screen
    def __init__(self, x, y, char, name, colour, blocks=False, always_visible=False, fighter=None, ai=None, item=None):
        self.always_visible = always_visible
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.colour = colour
        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

    def send_to_back(self):
        # Make this object be drawn first, so all others appear above it if they're in the same tile
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def move_towards(self, target_x, target_y):
        # Vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Normalise it to length 1 (preserving direction), then round it and
        # convert to integer so the movement is restricted to the map-grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        # Return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        # Return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx, dy):
        # move by the given amount, if the destination is not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def draw(self):
        if (tcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
            # set the colour and then draw the character that represents this oject at its position
            tcod.console_set_default_foreground(con, self.colour)
            tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        if TRADITIONAL_LOOK:
            tcod.console_put_char_ex(con, self.x, self.y, '.', tcod.white, colour_dark_ground)
        else:
            tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)


def save_game():
    # Open a newly empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player) # Index of player in objects list
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()


def load_game():
    # Open the previously saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state, dungeon_level

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']] # Get index of player in objects list and access it
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()


def from_dungeon_level(table):
    # Return a value that depends on level. Table specifies what value occurs after each level, default is 0.
    for(value, level) in reversed(table):
        if dungeon_level >= level:
            return value

    return 0


def next_level():
    global dungeon_level
    # Advance to the next level
    add_message('You take a moment to rest, and recover some strength.', tcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2) # Heal the player by 50%

    add_message('You descend the stairs.')
    dungeon_level += 1
    make_map()
    initialize_fov()


def check_level_up():
    # See if the player's experience is enough to level-up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        # it is, therefore level up
        player.fighter.xp += 1
        player.fighter.xp -= level_up_xp
        add_message('Your battle skills grow stronger! You reach level ' + str(player.level) + '!', tcod.gold)

        choice = None
        while choice == None: # keep asking until a choice is made
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['Constitution (+10 HP, from ' + str(player.fighter.max_hp) + ')',
                           'Strength (+1 attack, from ' +str(player.fighter.power)+ ')',
                           'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

            if choice == 0:
                player.fighter.max_hp += 10
                player.fighter.hp += 10
            elif choice == 1:
                player.fighter.power += 1
            elif choice == 2:
                player.fighter.defense += 1


def random_choice(chances_dict):
    # Choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = list(chances_dict)

    return strings[random_choice_index(chances)]


def random_choice_index(chances): # Choose one option from list of chances, returning its index
    # The dice will land on some number between 1 and the sum of chances
    dice = tcod.random_get_int(0, 1, sum(chances))

    # Go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        # See if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1


def target_monster(max_range=None):
    # Returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None: # player cancelled
            return None

        # Return the first-clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj


def target_tile(max_range=None):
    # Return the position of a tile left-clicked in player's FOV optionally in range, or None,None if right-clicked
    global key, mouse
    global fov_recompute, fov_map
    while True:
        # Render the screen, this erases the inventory and shows the names of objects under the mouse
        tcod.console_flush()
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS|tcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if (mouse.lbutton_pressed and tcod.map_is_in_fov(fov_map, x , y) and
                (max_range is None or player.distance(x, y) <= max_range)):
            return(x, y)

        if mouse.rbutton_pressed or key.vk == tcod.KEY_ESCAPE:
            return (None, None) # Cancel if the player right-clicked or pressed Esc


def closest_monster(max_range):
    # find closest enemy up to a max range and inside player's FOV
    closest_enemy = None
    closest_dist = max_range + 1 # Start with slightly more than max range

    for object in objects:
        if object.fighter and not object == player and tcod.map_is_in_fov(fov_map, object.x, object.y):
            # Calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist: # It's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy


def cast_fireball():
    # Ask the player for a target tile to throw a fireball at
    add_message('Left-click a target tile for the fireball, or right-click to cancel.', tcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    add_message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', tcod.orange)

    for obj in objects: # Damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            add_message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', tcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)


def cast_confuse():
    # Ask the player for a target to confuse
    add_message('Left-click an enemy to confuse is, or right-click to cancel.', tcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'

    # Replace the monster's AI with confused AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster # tell the ner component who owns it
    add_message('The eyes of the ' + monster.name + ' look vacant. He starts to shamble around.', tcod.light_green)



def cast_lightning():
    # Find closest enemy inside a max range and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: # No enemy found within max range
        add_message("No enemy is close enough to strike.", tcod.yellow)
        return 'cancelled'

    # Zap it
    add_message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
                + str(LIGHTNING_DAMAGE) + ' hit points.', tcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_heal():
    # Heal the player
    if player.fighter.hp == player.fighter.max_hp:
        add_message('You are already at full health', tcod.white)
        return 'cancelled'

    add_message('Your wounds start to feel better!', tcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)


def player_death(player):
    # The game ended
    global game_state
    add_message('You died.', tcod.red)
    game_state = 'dead'

    # For added effect, transform player into corpse
    player.char = '%'
    player.colour = tcod.dark_red


def monster_death(monster):
    # Create monster corpse, doesn't block, can't be attacked, doesn't move
    add_message(monster.name.capitalize() + ' dies screaming. You gain ' + str(monster.fighter.xp) + ' experience points.', tcod.grey)
    monster.char = '%'
    monster.colour = tcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of a ' + monster.name
    monster.send_to_back()


def is_blocked(x, y):
    # First test the map tile
    if map[x][y].blocked:
        return True

    # Now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False


def place_objects(room):
    # Maximum number of monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])

    # Chance of each monster
    monster_chances = {}
    monster_chances['fascist'] = 80 # Fascist always show up, even if all other monsters have 0 chance
    monster_chances['bourgeois'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

    # Maximum number of items per room
    max_items = from_dungeon_level([[1, 1], [2, 4]])

    # Chance of each item (by default they have a chance of 0 at level 1, which then goes up)
    item_chances = {}
    item_chances['heal'] = 35 # Healing potion always shows up, even if all other items have zero chance
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] = from_dungeon_level([[25, 6]])
    item_chances['confuse'] = from_dungeon_level([[10, 2]])

    # Choose random number of monsters
    num_monsters = tcod.random_get_int(0, 0, max_monsters)

    ## Monster and item chances specified here
    #monster_chances = {'fascist': 80, 'bourgeois': 20}
    #item_chances = {'heal': 70, 'lightning': 10, 'fireball': 10, 'confuse': 10}

    for i in range(num_monsters):
        # Choose random spot for this monster
        x = tcod.random_get_int(0, room.x1, room.x2)
        y = tcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'fascist':
                # Create fascist
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'f', 'fascist', tcod.desaturated_fuchsia, blocks=True, fighter=fighter_component, ai=ai_component)
            else:
                # Create bourgeois
                fighter_component = Fighter(hp=16, defense=1, power=4, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'B', 'bourgeois', tcod.darker_fuchsia, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    # Choose random number of items
    num_items = tcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
        # Choose random spot for this item
        x = tcod.random_get_int(0, room.x1+1, room.x2-1)
        y = tcod.random_get_int(0, room.y1+1, room.y2-1)

        # Only place if tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                # Create a healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', tcod.violet, item=item_component, always_visible=True)
            elif choice == 'lightning':
                # Create a lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', 'scroll of lightning bolt', tcod.light_yellow, item=item_component,
                              always_visible=True)
            elif choice == 'fireball':
                # Create a fireball scroll
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'scroll of fireball', tcod.light_yellow, item=item_component,
                              always_visible=True)
            else:
                # Create a scroll of confusion
                item_component = Item(use_function=cast_confuse)

                item = Object(x, y, '#', 'scroll of confusion', tcod.light_yellow, item=item_component,
                              always_visible=True)

            objects.append(item)
            item.send_to_back()  # Items appear below other objects


def create_room(room):
    global map
    # Go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def make_map():
    global map, objects, stairs

    # The list of objects with just the player
    objects = [player]

    # Fill map with "blocked" tiles
    map = [
        [Tile(True) for y in range(MAP_HEIGHT)]
        for x in range(MAP_WIDTH)
    ]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # Random width and height
        w = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # Random position without going out og the boundaries of the map
        x = tcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = tcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        # 'Rect' class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)

        # Run through the other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # This means there are no intersections, so this room is valid

            # "Paint" it to the map's tiles
            create_room(new_room)

            # Centre coordinates of new room, will be useful later
            (new_x, new_y) = new_room.centre()
            if num_rooms == 0:
                # This is the first room, where the player starts
                player.x = new_x
                player.y = new_y
            else:
                # All rooms after the first:
                # Connect it to the previous room with a tunnel

                # Centre co-ordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms - 1].centre()

                # Flip a coin
                if tcod.random_get_int(0, 0, 1) == 1:
                    # First move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # First move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, new_x)
                    create_h_tunnel(prev_x, new_x, prev_y)

            # add some contents to this room, such as monsters
            place_objects(new_room)

            # Finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

            if SHOW_ROOM_NUMBERS and MAX_ROOMS <= 30:
                # optional: print "room number" to see how the map drawing worked
                #          we may have more than ten rooms, so print 'A' for the first room, 'B' for the next...
                room_no = Object(new_x, new_y, chr(64 + num_rooms), 'room number', tcod.white, always_visible=True)
                objects.insert(0, room_no)  # draw early, so monsters are drawn on top

    # Create staris at the centre of the last room
    stairs = Object(new_x, new_y, '>', 'stairs', tcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back() # so it's drawn below creatures


def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def create_v_tunnel(y1, y2, x):
    global map
    # vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def inventory_menu(header):
    # Show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item


def menu(header, options, width):
    global key, mouse
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more than 26 options.')

    # Calculate total height for the header (after auto-wrap) and one line per option
    header_height = tcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    # Create an off-screen console that represents the menu's window
    window = tcod.console_new(width, height)

    # Print the header, with auto-wrap
    tcod.console_set_default_foreground(window, tcod.white)
    tcod.console_print_rect_ex(window, 0, 0, width, height, tcod.BKGND_NONE, tcod.LEFT, header)

    # Print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        tcod.console_print_ex(window, 0, y, tcod.BKGND_NONE, tcod.LEFT, text)
        y += 1
        letter_index +=1

    # Blit the contents of "window" to the root console
    x = SCREEN_WIDTH//2 - width//2
    y = SCREEN_HEIGHT//2 - height//2
    tcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    # Compute x and y offsets to convert console position to menu position
    x_offset = x # x is the Left edge of the menu
    y_offset = y + header_height # Subtract the height of the header from the top edge of the menu

    while True:
        # Present the root console to the player and check for input
        tcod.console_flush()
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS|tcod.EVENT_MOUSE, key, mouse)

        if mouse.lbutton_pressed:
            (menu_x, menu_y) = (mouse.cx - x_offset, mouse.cy - y_offset)
            # Check if click is within the menu and a choice
            if menu_x >= 0 and menu_x < width and menu_y <= 0 and menu_y < height - header_height:
                return menu_y

        if mouse.rbutton_pressed or key.vk == tcod.KEY_ESCAPE:
            return None # cancel if the player right-clicked or pressed Esc

        if key.vk == tcod.KEY_ENTER and key.lalt:
            # (special case) Alt+Enter: toggle full-screen
            tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

        # Convert the ASCII code to an index; if it corresponds to an option, return it
        index = key.c - ord('a')
        if index >= 0 and index < len(options): return index
        # If they pressed a letter that is not an option, return none
        if index >= 0 and index <= 26: return None


def render_bar(x, y, total_width, name, value, maximum, bar_colour, back_colour):
    # Render a bar (HP, exp., etc). First calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)

    # Render the background first
    tcod.console_set_default_background(panel, back_colour)
    tcod.console_rect(panel, x, y, total_width, 1, False, tcod.BKGND_SCREEN)

    # Now render the bar on top
    tcod.console_set_default_background(panel, bar_colour)
    if bar_width > 0:
        tcod.console_rect(panel, x, y, bar_width, 1, False, tcod.BKGND_SCREEN)

    # Finally centre text with the values
    tcod.console_set_default_foreground(panel, tcod.white)
    tcod.console_print_ex(panel, x + total_width // 2, y, tcod.BKGND_NONE, tcod.CENTER,
                          name + ': ' + str(value) + '/' + str(maximum))


def render_all():
    global colour_dark_wall, colour_light_wall
    global colour_dark_ground, colour_light_ground
    global fov_map, fov_recompute, dungeon_level

    if fov_recompute:
        # Recompute FOV if needed (the player moved or something)
        fov_recompute = False
        tcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        # Go through all tiles and set background colour according to FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = tcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    # if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        if wall:
                            if TRADITIONAL_LOOK:
                                tcod.console_put_char_ex(con, x, y, '#', tcod.white, colour_dark_wall)
                            else:
                                tcod.console_set_char_background(con, x, y, colour_dark_wall, tcod.BKGND_SET)
                        else:
                            if TRADITIONAL_LOOK:
                                tcod.console_put_char_ex(con, x, y, '.', tcod.white, colour_dark_ground)
                            else:
                                tcod.console_set_char_background(con, x, y, colour_dark_ground, tcod.BKGND_SET)
                else:
                    if wall:
                        if TRADITIONAL_LOOK:
                            tcod.console_put_char_ex(con, x, y, '#', tcod.white, colour_light_wall)
                        else:
                            tcod.console_set_char_background(con, x, y, colour_light_wall, tcod.BKGND_SET)
                    else:
                        if TRADITIONAL_LOOK:
                            tcod.console_put_char_ex(con, x, y, '.', tcod.white, colour_light_ground)
                        else:
                            tcod.console_set_char_background(con, x, y, colour_light_ground, tcod.BKGND_SET)
                    # since it's visible, explore it
                    map[x][y].explored = True

    # Draw all objects in the list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()

    # Prepare to render the GUI panel
    tcod.console_set_default_background(panel, tcod.black)
    tcod.console_clear(panel)

    # Print the game messages, one line at a time
    y = 1
    for(line, colour) in game_msgs:
        tcod.console_set_default_foreground(panel, colour)
        tcod.console_print_ex(panel, MSG_X, y, tcod.BKGND_NONE, tcod.LEFT, line)
        y += 1

    # Show the player's stats and dungeon level
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, tcod.light_red, tcod.darker_red)
    tcod.console_print_ex(panel, 1, 3, tcod.BKGND_NONE, tcod.LEFT, 'Dungeon level ' + str(dungeon_level))

    # Display the names of objects under the mouse
    tcod.console_set_default_foreground(panel, tcod.light_grey)
    tcod.console_print_ex(panel, 1, 0, tcod.BKGND_NONE, tcod.LEFT, get_names_under_mouse())

    # Blit the contents of panel to the root console
    tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

    # Blit the contents of con to the root console
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)


#def get_key_event(turn_based = None):
#    if turn_based:
#        # Turn-based gameplay; wait for a keystroke
#        key = tcod.console_wait_for_keypress(True)
#    else:
#        # Real-time gameplay; don't wait for a player's keystoke
#        key = tcod.console_check_for_keypress()
#    return key


def player_move_or_attack(dx, dy):
    global fov_recompute

    # The coordinates the player is moving to or attacking
    x = player.x + dx
    y = player.y + dy

    # Try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break
    # Attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


def add_message(new_msg, colour=tcod.white):
    # Split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # If buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        # Add the new line as a tuple, with the text and the colour
        game_msgs.append((line, colour))


def get_names_under_mouse():
    global mouse

    # Return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    # Create a list with the names of all objects at the mouse's coordinated and in FOV
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and tcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names) # Join the names, separated by commas
    return names.capitalize()


def handle_keys():
    global fov_recompute
    global game_state
    global key

    #key = get_key_event(TURN_BASED)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle full screen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    elif key.vk == tcod.KEY_ESCAPE:
        return 'exit' # exit game

    if game_state == 'playing':
        #movement keys
        if key.vk == tcod.KEY_UP or key.vk == tcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == tcod.KEY_DOWN or key.vk == tcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == tcod.KEY_LEFT or key.vk == tcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == tcod.KEY_RIGHT or key.vk == tcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == tcod.KEY_HOME or key.vk == tcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == tcod.KEY_PAGEUP or key.vk == tcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == tcod.KEY_END or key.vk == tcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == tcod.KEY_PAGEDOWN or key.vk == tcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == tcod.KEY_KP5:
            pass  # Do nothing ie wait for the monster to come to you

        else:
            # Test for other keys
            key_char = chr(key.c)

            if key_char == ',':
                # Pick up an item
                for object in objects: # Look for item in the player's tile
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break

            if key_char == 'i':
                # Show the inventory
                chosen_item = inventory_menu('Press the key next to an item to use it, of any other key to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()

            if key_char == 'd':
                # Show the inventory; if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            if key.shift and key_char == 'c':
                # Show character info
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                       '\nNext level: ' + str(level_up_xp) + '\n\nMax HP: ' + str(player.fighter.max_hp) +
                       '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

            if key.shift and key_char == '.':
                # Go down the stairs, if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            if key_char == '.':
                return  # Do nothing ie wait for the monster to come to you

            return 'didnt-take-turn'


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    # Create the FOV map, according to the generated map
    fov_map = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    tcod.console_clear(con)  # Unexplored areas start black (which is the default background color)


def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    dungeon_level = 1

    # Create object representing the player
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)
    inventory = []
    player.level = 1

    # Generate map
    make_map()
    initialize_fov()

    game_state = 'playing'
    game_msgs = []

    # Welcome message
    add_message('Welcome stranger. Get ready to kick some imperialist butt!', tcod.grey)


def initialize_game():
    global fov_recompute, fov_map

    # Set up font
    font_path = 'arial10x10.png'
    font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD
    tcod.console_set_custom_font(font_path, font_flags)

    # Initialise screen
    window_title = 'Python 3 tutorial'
    tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, window_title, FULLSCREEN)

    # set FPS
    tcod.sys_set_fps(LIMIT_FPS)


def play_game():
    global key, mouse

    exit_game = False
    player_action = None

    while not tcod.console_is_window_closed() and not exit_game:
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)
        render_all()

        tcod.console_flush()
        check_level_up()

        # Erase all objects at their old locations before they move
        for object in objects:
            object.clear()

        # handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()


def msgbox(text, width=50):
    menu(text, [], width) # Use menu as a sort of 'message box'


def main_menu():
    img = tcod.image_load('menu_background.png')

    while not tcod.console_is_window_closed():
        # Show the background image, at twice the regular console resolution
        tcod.image_blit_2x(img, 0, 0, 0)

        # Show the game's title and some credits
        tcod.console_set_default_foreground(0, tcod.light_yellow)
        tcod.console_print_ex(0, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 4, tcod.BKGND_NONE, tcod.CENTER, 'FASCIST EXTERMINATORS')
        tcod.console_print_ex(0, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 2, tcod.BKGND_NONE, tcod.CENTER, 'By fejoa')

        # Show options and wait for the player's choice
        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0: # New game
            new_game()
            play_game()
        elif choice == 1: # Load last game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2: # Quit
            break


mouse = tcod.Mouse()
key = tcod.Key()


def main():

    initialize_game()

    main_menu()


main()
