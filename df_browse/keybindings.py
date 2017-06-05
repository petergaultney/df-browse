# supports multiple keybindings per command
_commands = { # these commands are specifically for use in the browser
    'merge': ['m'],
    'hide column': ['H'],
    'search down': ['ctrl s'],
    'search up': ['ctrl r'],
    'sort ascending': ['s'],
    'sort descending': ['S'],
    'browse right': ['right', 'l'],
    'browse left': ['left', 'h'],
    'browse up': ['up', 'k'],
    'browse down': ['down', 'j'],
    'undo': ['u', 'ctrl /'],
    'quit': ['q'],
    'query': ['y'],
    'page up': ['page up'],
    'page down': ['page down'],
    'help': ['?'],
    'shift column left': [',', '<'],
    'shift column right': ['.', '>'],
    'increase column width': ['=', '+'],
    'decrease column width': ['-'],
    'jump to last row': ['meta >'],
    'jump to first row': ['meta <'],
    'jump to numeric column': list('1234567890'),
    'jump to last column': ['ctrl e'],
    'jump to first column': ['ctrl a'],
    'name current table browser': ['n'],
    'switch to table browser': ['b'],
    'jump to column': ['c'],
    'jump to row': ['r'],
}

_exception_hints = {
    'jump to column': 'Could not find column {}',
    'jump to row': 'Rows may only be indexed by integer or floating point number, and must not be out of range.',
}

# on startup, verify no duplicate keybindings for developer (my) sanity
__set_keybs = set()
for cmd, keybs in _commands.items():
    for keyb in keybs:
        if keyb in __set_keybs:
            print('Attempting to shadow keybinding ' + keyb + ' already in use.')
        __set_keybs.add(keyb)
del __set_keybs

def cmd_hint(cmd_str):
    if cmd_str in _exception_hints:
        return _exception_hints[cmd_str]
    else:
        return 'Command could not be executed.'

def set_keybindings_for_command(command, keybindings):
    """This helps avoid accidentally setting up keybindings that shadow each other"""
    global _commands
    # verify that it's not already in use...
    for cmd, keybs in _commands.items():
        if cmd != command:
            for keyb in keybs:
                if keyb in keybindings:
                    raise Exception('Attempting to shadow keybindings for ' + cmd)
    _commands[command] = keybindings

def keybs(command):
    return _commands[command][:] # so that you don't change the original list directly
