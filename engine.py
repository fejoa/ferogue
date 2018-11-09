#!/usr/bin/env python
import libtcodpy as tcod
import math
import textwrap

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

MAX_ROOM_MONSTERS = 3

con = tcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = tcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
mouse = tcod.Mouse()
key = tcod.Key()

colour_dark_wall = tcod.Color(0, 30, 0)
colour_dark_ground = tcod.Color(20, 60, 20)
colour_light_wall = tcod.Color(130, 110, 50)
colour_light_ground = tcod.Color(200, 180, 50)


class Fighter:
    # Combat-related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
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

    def attack(self, target):
        # A simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            # Make the target take some damage
            add_message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', tcod.grey)
            target.fighter.take_damage(damage)
        else:
            add_message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect.', tcod.grey)


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
    def __init__(self, x, y, char, name, colour, blocks=False, fighter=None, ai=None):
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.colour = colour
        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

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

    def move(self, dx, dy):
        # move by the given amount, if the destination is not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def draw(self):
        if tcod.map_is_in_fov(fov_map, self.x, self.y):
            # set the colour and then draw the character that represents this oject at its position
            tcod.console_set_default_foreground(con, self.colour)
            tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        if TRADITIONAL_LOOK:
            tcod.console_put_char_ex(con, self.x, self.y, '.', tcod.white, colour_dark_ground)
        else:
            tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)


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
    add_message(monster.name.capitalize() + ' dies screaming.', tcod.grey)
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

    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False


def place_objects(room):
    # Choose random number of monsters
    num_monsters = tcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        # Choose random spot for this monster
        x = tcod.random_get_int(0, room.x1, room.x2)
        y = tcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x, y):
            if tcod.random_get_int(0, 0, 100) < 80:
                # 80% chance to create fascist
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'f', 'fascist', tcod.desaturated_fuchsia, blocks=True, fighter=fighter_component,ai=ai_component)
            else:
                # 20% chance to create bourgeois
                fighter_component = Fighter(hp=16, defense=1, power=4)
                ai_component = BasicMonster()
                monster = Object(x, y, 'B', 'bourgeois', tcod.darker_fuchsia, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)


def create_room(room):
    global map
    # Go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def make_map():
    global map, player

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
                room_no = Object(new_x, new_y, chr(64 + num_rooms), 'room number', tcod.white)
                objects.insert(0, room_no)  # draw early, so monsters are drawn on top


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
    global fov_map, colour_dark_wall, colour_light_wall
    global colour_dark_ground, colour_light_ground
    global fov_recompute

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

    # Show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, tcod.light_red, tcod.darker_red)

    # Blit the contents of panel to the root console
    tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

    # Blit the contents of con to the root console
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)


def get_key_event(turn_based = None):
    if turn_based:
        # Turn-based gameplay; wait for a keystroke
        key = tcod.console_wait_for_keypress(True)
    else:
        # Real-time gameplay; don't wait for a player's keystoke
        key = tcod.console_check_for_keypress()
    return key


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


def handle_keys():
    global fov_recompute
    global game_state

    key = get_key_event(TURN_BASED)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle full screen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    elif key.vk == tcod.KEY_ESCAPE:
        return 'exit' # exit game

    if game_state == 'playing':
        # movement keys
        if tcod.console_is_key_pressed(tcod.KEY_UP):
            player_move_or_attack(0, -1)

        elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
            player_move_or_attack(0, 1)

        elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
            player_move_or_attack(-1, 0)

        elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
            player_move_or_attack(1, 0)

        else:
            return 'didnt-take-turn'


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

    make_map()

    # Create the FOV map, according to the generated map
    fov_map = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    fov_recompute = True


fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)
objects = [player]


game_state = 'playing'
game_msgs = []


def main():
    initialize_game()
    exit_game = False
    player_action = None

    # Welcome message
    add_message('Welcome stranger. Get ready to kick some imperialist butt!', tcod.grey)

    while not tcod.console_is_window_closed() and not exit_game:
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS|tcod.EVENT_MOUSE, key, mouse)
        render_all()

        tcod.console_flush()

        # Erase all objects at their old locations before they move
        for object in objects:
            object.clear()

        # handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            break

        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()


main()
