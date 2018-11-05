#!/usr/bin/env python
import libtcodpy as tcod

FULLSCREEN = False
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20
TURN_BASED = True

def initialize_game():
    global player_x, player_y
    player_x = SCREEN_WIDTH // 2
    player_y = SCREEN_HEIGHT // 2

    # Set up font
    font_path = 'arial10x10.png'
    font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD
    tcod.console_set_custom_font(font_path, font_flags)

    # Initialise screen
    window_title = 'Python 3 tutorial'
    tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, window_title, FULLSCREEN)

    # set FPS
    tcod.sys_set_fps(LIMIT_FPS)

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
        player_y = player_y - 1

    elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        player_y = player_y + 1

    elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        player_x = player_x - 1

    elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        player_x = player_x + 1

def main():
    initialize_game()

    exit_game = False

    while not tcod.console_is_window_closed() and not exit_game:
        tcod.console_set_default_foreground(0, tcod.white)
        tcod.console_put_char(0, player_x, player_y, '@', tcod.BKGND_NONE)
        tcod.console_flush()
        tcod.console_put_char(0, player_x, player_y, ' ', tcod.BKGND_NONE)

        # handle keys and exit game if needed
        exit_game = handle_keys()


main()
