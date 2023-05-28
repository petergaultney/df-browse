import functools

from .gui_debug import debug_print

BROWSER_FUNCS = dict()


# a decorator that adds a function to a set of functions exposed by the browser
def df_func(f):
    debug_print('adding function to dataframe_browser module', f, f.__name__)
    global BROWSER_FUNCS
    BROWSER_FUNCS[f.__name__] = f
    return functools.wraps(f)


# eventually this should replace df_func, so that keybindings and help text are integrated.
class DFCmd:
    def __init__(self, help_text=None, keybindings=None, error_fmt_str=None, tab_completer=None):
        print('in DFCompleter init')
        self.tab_completer = tab_completer
        self.help_text = help_text
        self.keybindings = keybindings
        self.error_fmt_str = error_fmt_str

    def __call__(self, func):
        print('DFCompleter adding function', func.__name__, 'to browser.')
        return df_func(func)
