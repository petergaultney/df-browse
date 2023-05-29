
class TBCmd(object):
    def __init__(self, function, tab_completer=None, help_text=None, keybindings=None, error_fmt_str=None):
        self.func = function
        self.tab_completer = tab_completer
    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)
    def complete(self, prefix, completion_data):
        return self.tab_completer(prefix, completion_data)
    def help(self):
        return self.help_text
    def keybindings(self):
        return self.keybindings
    def format_error(self, e, cmd_str, **kwargs):
        return error_fmt_str.format(cmd_str)

# supports multiple keybindings per command
_commands = { # these commands are specifically for use in the browser
    'cancel': ['esc', 'ctrl g'],
    'insert-column': ['i'],
    'hide-column': ['H'],
    'search': ['ctrl s', 'meta s'],  # ctrl s not working for... some reason?
    'search-backward': ['ctrl r', 'meta r'],
    'sort-ascending': ['s'],
    'sort-descending': ['S'],
    'browse-right': ['right', 'l'],
    'browse-left': ['left', 'h'],
    'browse-up': ['up', 'k'],
    'browse-down': ['down', 'j'],
    'undo': ['u', 'ctrl /'],
    'redo': ['U'],
    'quit': ['q'],
    'query': ['y'],
    'page-up': ['page up'],
    'page-down': ['page down'],
    'help': ['?'],
    'shift-column-left': [',', '<'],
    'shift-column-right': ['.', '>'],
    'increase-column-width': ['=', '+'],
    'decrease-column-width': ['-'],
    'jump-to-last-row': ['meta >'],
    'jump-to-first-row': ['meta <'],
    'jump-to-numeric-column': list('1234567890'),
    'jump-to-last-column': ['ctrl e'],
    'jump-to-first-column': ['ctrl a'],
    'rename-browser': ['n'],
    'switch-to-browser': ['b'],
    'jump-to-column': ['c'],
    'jump-to-row': ['r'],
    'command': ['/'],
    'ipython': ['p'],
}

_exception_hints = {
    'jump-to-column': 'Column "{}" not found in table browser.',
    'jump-to-row': 'Rows may only be indexed by integer or floating point number, and must not be out of range.',
    'insert-column': 'Column "{}" not found in table browser.',
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
                    raise ValueError('Attempting to shadow keybindings for ' + cmd)
    _commands[command] = keybindings

def keybs(command):
    return _commands[command][:] # so that you don't change the original list directly

def rev_keybs(key):
    # TODO set up reverse dict
    for cmd in _commands.keys():
        if key in _commands[cmd]:
            return cmd
    return None
