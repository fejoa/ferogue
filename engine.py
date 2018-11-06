#!/usr/bin/env python
import libtcodpy as tcod

FULLSCREEN = False
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 45
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

TURN_BASED = True
TRADITIONAL_LOOK = False
SHOW_ROOM_NUMBERS = False

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
colour_dark_wall = tcod.Color(0, 30, 0)
colour_dark_ground = tcod.Color(20, 60, 20)
colour_light_wall = tcod.Color(130, 110, 50)
colour_light_ground = tcod.Color(200, 180, 50)


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

            # Finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

            if SHOW_ROOM_NUMBERS and MAX_ROOMS <= 30:
                # optional: print "room number" to see how the map drawing worked
                #          we may have more than ten rooms, so print 'A' for the first room, 'B' for the next...
                room_no = Object(new_x, new_y, chr(64 + num_rooms), tcod.white)
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
    global fov_recompute

    key = get_key_event(TURN_BASED)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle full screen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    elif key.vk == tcod.KEY_ESCAPE:
        return True # exit game

    # movement keys
    if tcod.console_is_key_pressed(tcod.KEY_UP):
        player.move(0, -1)
        fov_recompute = True

    elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        player.move(0, 1)
        fov_recompute = True

    elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        player.move(-1, 0)
        fov_recompute = True

    elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        player.move(1, 0)
        fov_recompute = True


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
