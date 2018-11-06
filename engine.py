#!/usr/bin/env python
import libtcodpy as tcod

FULLSCREEN = False
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20
TURN_BASED = True
MAP_WIDTH = 80
MAP_HEIGHT = 45
TRADITIONAL_LOOK = False

con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
colour_dark_wall = tcod.Color(0, 30, 0)
colour_dark_ground = tcod.Color(20, 60, 20)


class Rect:
    # A rectangle on the map, used to characterise a room
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h


class Tile:
    # A tile of the map and its porperties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked

        # By default, if a tile is blocked, it also blocks sight
        block_sight = blocked if block_sight is None else None
        self.block_sight = block_sight


class Object:
    # This is a generic object: the player, a monster, an item, the toilet...
    # It's always represented by a character on the screen
    def __init__(self, x, y, char, colour):
        self.x = x
        self.y = y
        self.char = char
        self.colour = colour

    def move(self, dx, dy):
        # move by the given amount, if the destination is not blocked
        if not map[self.x + dx][self.y + dy].blocked:
            self.x += dx
            self.y += dy

    def draw(self):
        # set the colour and then draw the character that represents this oject at its position
        tcod.console_set_default_foreground(con, self.colour)
        tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        if TRADITIONAL_LOOK:
            tcod.console_put_char_ex(con, self.x, self.y, '.', tcod.white, colour_dark_ground)
        else:
            tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)


def create_room(room):
    global map
    # Go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def make_map():
    global map

    # Fill map with "blocked" tiles
    map = [
        [Tile(True) for y in range (MAP_HEIGHT)]
        for x in range(MAP_WIDTH)
    ]

    room1 = Rect(20, 15, 10, 15)
    room2 = Rect(50, 15, 10, 15)
    create_room(room1)
    create_room(room2)

    player.x = 25
    player.y = 23

    create_h_tunnel(25, 55, 23)


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


def render_all():
    global colour_light_wall
    global colour_light_ground

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            wall = map[x][y].block_sight
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

    # Draw all objects in the list
    for object in objects:
        object.draw()

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


def handle_keys():
    global player_x, player_y

    key = get_key_event(TURN_BASED)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle full screen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    elif key.vk == tcod.KEY_ESCAPE:
        return True # exit game

    # movement keys
    if tcod.console_is_key_pressed(tcod.KEY_UP):
        player.move(0, -1)

    elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        player.move(0, 1)

    elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        player.move(-1, 0)

    elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        player.move(1, 0)


def initialize_game():
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


player = Object(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, '@', tcod.white)
npc = Object(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2, '@', tcod.yellow)
objects = [npc, player]


def main():
    initialize_game()
    exit_game = False

    while not tcod.console_is_window_closed() and not exit_game:
        render_all()

        tcod.console_flush()

        # Erase all objects at their old locations before they move
        for object in objects:
            object.clear()

        # handle keys and exit game if needed
        exit_game = handle_keys()


main()
