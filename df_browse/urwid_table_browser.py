import sys, re, os

import urwid

import df_browse
import df_browse.urwid_utils as urwid_utils
import df_browse.browser_utils as browser_utils

from df_browse.list_utils import *

from df_browse.keybindings import keybs, cmd_hint, rev_keybs

from df_browse.gui_debug import *

import df_browse.ipython_utils as ipython_utils

PAGE_SIZE = 20

# this stuff captures Ctrl-C
# ui = urwid.raw_display.RealTerminal()
# ui.tty_signal_keys('undefined', 'undefined', 'undefined', 'undefined',
#                    'undefined')

def _given(columns, width):
    return columns.options('given', width)

def generate_strings_segments_for_column(view, col_name, is_focus_col):
    column_strings = view.lines(col_name)
    selected_row = view.selected_row - view.top_row # the relative index of the selected row in the view
    pile_of_strs = list()
    pile_of_strs.append(view.header(col_name) +
                        '\n...' if view.top_row > 1 and is_focus_col else '\n')
    if selected_row > 0:
        pile_of_strs.append('\n'.join(column_strings[0:selected_row]))
    pile_of_strs.append(column_strings[selected_row])
    pile_of_strs.append('\n'.join(column_strings[selected_row + 1: len(column_strings)]))
    return pile_of_strs

def set_attrib_on_col_pile(pile, is_focus_col, focus_pile):
    for i in range(len(pile.contents)):
        if focus_pile == i:
            pile.contents[i][0].set_attr_map({None: 'active_element' if is_focus_col else 'active_row'})
        else:
            pile.contents[i][0].set_attr_map({None: 'active_col' if is_focus_col else 'def'})

class BrowserNamedColumnPile(urwid.Pile):
    def __init__(self, column_name, table_view, is_focus_col_cb):
        super().__init__([])
        self.column_name = column_name
        self.table_view = table_view
        self._is_focus_col_cb = is_focus_col_cb
        self._focus_pile = 0
        self._create_pile()
        self.rebuild_from_view()
    def _create_pile(self, num_texts=5): # TODO this magic number is pretty dang hacky
        for i in range(num_texts):
            self.contents.append((urwid.AttrMap(urwid.Text('', wrap='clip'), 'def'),
                                  ('pack', None)))
    @property
    def is_focused(self):
        return self._is_focus_col_cb(self.column_name)
    def selectable(self):
        return True
    def rebuild_from_view(self):
        pile_strings = generate_strings_segments_for_column(
            self.table_view, self.column_name, self.is_focused)
        for idx, pile_str in enumerate(pile_strings):
            self.contents[idx][0].original_widget.set_text(pile_str)
        self._focus_pile = len(pile_strings) - 2
        self.reset_attribs()
    def _set_header_break(self):
        header = self.table_view.header(self.column_name)
        header += '\n...' if self.is_focused and self.table_view.top_row > 1 else '\n'
        self.contents[0][0].original_widget.set_text(header)
    def reset_attribs(self):
        self._set_header_break()
        set_attrib_on_col_pile(self, self.is_focused, self._focus_pile)


class Modeline(urwid.WidgetWrap):
    doc_attrs = '{name} -- c{current_col}/{cols} - r{current_row}/{rows}({row_percent}%) -- {current_cell}'
    def __init__(self):
        self.text = urwid.Text('Welcome to the Dataframe browser!')
        urwid.WidgetWrap.__init__(self, self.text)
    def set_text(self, text):
        self.text.set_text(text)
    def update_doc_attrs(self, name, cols, rows, current_col, current_row, current_cell):
        self.text.set_text(Modeline.doc_attrs.format(
            name=name, cols=cols, rows=rows, current_col=current_col,
            current_row=current_row, row_percent=int(100*current_row/rows),
            current_cell=current_cell))
    def show_basic_commands(self):
        # help text
        self.set_text('(hjkl) browse; (H)ide col; (u)ndo; (+-) size col; (,.) move col; (ctrl-s)ea(r)ch col; (s)o(r)t')
    def show_command_options(self):
        self.set_text('type column name to add, then press enter. Press Esc to return to browsing.')


class Minibuffer(urwid.WidgetWrap):
    # TODO modify the minibuffer so it knows very little about the
    # browser_frame, but instead sends 'results' to the browser
    # via strings that the browser can that use to determine which functions,
    # if any, to call.
    # The advantage is reduced coupling that will further enhance the ability of the
    # UrwidBrowser to support back end browser implementations that don't necessarily
    # support 100% of the same functionality (i.e. maybe not supporting JOINs).
    def __init__(self, browser_frame):
        self.browser_frame = browser_frame
        self.edit_text = urwid_utils.AdvancedEdit(caption='browsing... ', multiline=False)
        urwid.WidgetWrap.__init__(self, self.edit_text)
        self.active_command = 'browsing'
        self.active_args = dict()
    def focus_granted(self, command, **kwargs):
        self.edit_text.set_edit_text('')
        self._set_command(command, **kwargs)
    def focus_removed(self):
        self._set_command('browsing')
        self.edit_text.set_edit_text('')
        self.edit_text.set_caption('browsing... ')
        self.edit_text.setCompletionMethod()
    def give_away_focus(self):
        self.edit_text.set_edit_text('')
        self.active_args = dict()
        self.browser_frame.focus_browser() # this should call back to focus_removed
    def _set_command(self, command, **kwargs):
        self.active_command = command
        self.active_args = kwargs
        # self.edit_text.set_edit_text('')
        if command:
            self.edit_text.set_caption(command + ': ')
        if 'completer' in self.active_args:
            self.edit_text.setCompletionMethod(self.active_args['completer'])
        if 'default_text' in self.active_args:
            self.edit_text.set_edit_text(self.active_args['default_text'])
            self.edit_text.set_edit_pos(len(self.edit_text.get_edit_text()) + 1)
        if self.active_command == None:
            # then we are typing in a custom command, so set up appropriately...
            self.edit_text.set_caption('browser function name: ')
            self.edit_text.set_edit_text('')
            self.edit_text.setCompletionMethod(urwid_utils.ListCompleter(
                self.browser_frame.table_view.browser.browser_func_names,
                self.browser_frame.hint).complete)
        elif self.active_command == 'ipython':
            print('prompting for code?')
            import IPython
            self.edit_text.setCompletionMethod(ipython_utils.IPythonCompleter(self.browser_frame.hint).complete)
            # code = IPython.core.getipython.get_ipython().prompt_for_code()
            print('prompted for code')

    def _search(self, search_str, down, skip_current):
        if 'search' in self.active_command:
            if down:
                self._set_command('search')
            else:
                self._set_command('search-backward')
            self.browser_frame.table_view.search_current_col(search_str, down, skip_current)

    def _submit_command(self, cmd_str):
        print('handling input string', cmd_str)
        if self.active_command == 'insert-column':
            self.browser_frame.table_view.insert_column(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'rename-browser':
            self.browser_frame.table_view.rename_active_browser(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'switch-to-browser':
            self.browser_frame.table_view.switch_to_browser(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'jump-to-row':
            location = float(cmd_str) if '.' in cmd_str else int(cmd_str)
            browser_utils.jump(self.browser_frame.table_view.browser, location)
            self.give_away_focus()
        elif self.active_command == 'jump-to-column':
            browser_utils.jump(self.browser_frame.table_view.browser, cmd_str)
            self.give_away_focus()
        elif self.active_command == None:
            # we've typed in the name of a custom function!
            print('setting up call to browser function ', cmd_str)
            self._set_command(cmd_str)
            # TODO support browser functions providing their own tab-completers
        elif self.active_command == 'ipython':
            print(cmd_str)
            ipython_utils.execute_ipython_command(cmd_str)
            self.give_away_focus()
        else: # this is where we call a custom browser function
            self.browser_frame.table_view.browser.call_browser_func(
                self.active_command, args_str=cmd_str)
            self.give_away_focus()

    def keypress(self, size, key):
        if key == 'enter':
            try:
                cmd_str = self.edit_text.get_edit_text().strip()
                print('cmd str is', cmd_str)
                self._submit_command(cmd_str)
                self.edit_text.set_edit_text('')
            except Exception as e:
                print('error trying to submit command: ', self.active_command, cmd_str)
                print(e)
                self.browser_frame.hint(cmd_hint(self.active_command).format(cmd_str))
        elif key == 'esc' or key == 'ctrl g':
            self.give_away_focus()
        elif key == 'ctrl c':
            # raise urwid.ExitMainLoop()
            self.give_away_focus()
        elif key == 'ctrl s':
            self._search(self.edit_text.get_edit_text(), True, True)
        elif key == 'ctrl r':
            self._search(self.edit_text.get_edit_text(), False, True)
        else: # active search - TODO maybe replace with 'active results' being fed directly to the command callback
            self.edit_text.keypress(size, key)
            if key != 'backspace':
                if self.active_command == 'search':
                    print('asking for forward search')
                    self._search(self.edit_text.get_edit_text(), True, False)
                elif self.active_command == 'search-backward':
                    print('asking for backward search')
                    self._search(self.edit_text.get_edit_text(), False, False)


class UrwidTableView(urwid.WidgetWrap):
    def __init__(self, urwid_frame, col_gap=2):
        self.urwid_frame = urwid_frame
        self._col_gap = col_gap
        self.urwid_cols = urwid.Columns([], dividechars=self._col_gap)
        super().__init__(self.urwid_cols)
        self._size = None

    # TODO display help in modeline or something, generated by defined commands/keybindings
    # TODO figure out how to get frame height so that we can feed that information to the browser

    @property
    def browser(self):
        return self.multibrowser.active_browser

    @property
    def _selected_col(self):
        return self.browser.selected_column
    @property
    def _selected_col_idx(self):
        return self.browser.browse_columns.index(self.browser.selected_column)

    def _col_by_index(self, idx):
        return self.browser.browse_columns[idx]
    def _col_idx_by_name(self, column_name):
        return self.browser.browse_columns.index(column_name)

    def _is_focus_column(self, column_name):
        return column_name == self.browser.selected_column

    # TODO maybe move these into a container class that mirrors MultiDataframeBrowser
    def set_multibrowser(self, multibrowser):
        self.multibrowser = multibrowser
        self.update_view()

    # TODO maybe move these into a container class that mirrors MultiDataframeBrowser
    def switch_to_browser(self, name):
        """Open an existing dataframe, or accept a new one."""
        print('switching to', name)
        self.multibrowser.active_browser_name = name
        self.browser.add_change_callback(self.update_view)
        self.update_view()

    # TODO maybe move these into a container class that mirrors MultiDataframeBrowser
    def rename_active_browser(self, new_name):
        self.multibrowser.rename_browser(self.multibrowser.active_browser_name, new_name)

    def update_view(self, browser=None, table_changed=True):
        print('updating view')
        try:
            old_col = self.urwid_cols.focus_position
        except:
            old_col = self._selected_col_idx
        del self.urwid_cols.contents[:]
        if len(self.browser.browse_columns) > 0:
            # TODO don't recreate these column piles - instead keep track of them
            # and re-order/refresh them as necessary, only creating new ones when brand new columns are shown
            for idx, col_name in enumerate(self.browser.browse_columns):
                pile = BrowserNamedColumnPile(col_name, self.browser.view, lambda colname: self._is_focus_column(colname))
                column_width = self.browser.view.width(col_name)
                self.urwid_cols.contents.append((pile, _given(self.urwid_cols, column_width)))
            try:
                self.urwid_cols.focus_position = min(old_col, len(self.urwid_cols.contents))
            except Exception as e:
                print('exception in update_view when trying to set columns focus_position', e)
                self.urwid_frame.hint(str(e))
            self.update_modeline_text()

    def update_modeline_text(self):
        current_cell = str(self.browser.content())
        self.urwid_frame.modeline.update_doc_attrs(self.multibrowser.active_browser_name,
                                                   len(self.browser.browse_columns),
                                                   len(self.browser),
                                                   self._selected_col_idx + 1,
                                                   self.browser.selected_row + 1,
                                                   current_cell)

    def scroll(self, num_rows):
        browser_utils.scroll_rows(self.browser, num_rows)

    def mouse_event(self, size, event, button, col, row, focus):
        self._size = size
        if event == 'mouse press':
            if button == 4.0:
                self.scroll(-1)
            elif button == 5.0:
                self.scroll(1)
            else:
                print('moving to row', row)
                col = urwid_utils.translate_urwid_col_to_browser_col(self.urwid_cols, col, self.browser,
                                                                     self._col_gap, self._size)
                self.set_rowcol_focus(self._col_by_index(col), row - 2)
        return True

    def set_col_focus(self, col_num):
        # the only function allowed to directly modify urwid_cols.focus_position
        col_num = max(0, min(col_num, len(self.browser.browse_columns) - 1))
        print(self.urwid_cols.focus_position)
        try:
            current_selected_col_idx = self._selected_col_idx
            if current_selected_col_idx != col_num:
                print('moving col focus from', current_selected_col_idx, col_num )
                if col_num > urwid_utils.get_rightmost_visible_column(self.urwid_cols, self._size):
                    print('going leftward far enough to change columns viewed')
                    self.urwid_cols.focus_position = col_num
                elif col_num < urwid_utils.get_leftmost_visible_column(self.urwid_cols, self._size):
                    print('going rightward far enough...')
                    while col_num < urwid_utils.get_leftmost_visible_column(self.urwid_cols, self._size):
                        self.urwid_cols.focus_position -= 1
                self.browser.selected_column = col_num
                self.urwid_cols.contents[current_selected_col_idx][0].reset_attribs()
                self.urwid_cols.contents[col_num][0].reset_attribs()
                self.update_modeline_text()
                print(self.urwid_cols.focus_position)

            return True
        except Exception as e:
            print('exception in set focus', e)
            return False

    def set_rowcol_focus(self, column_name, row):
        """Column name and relative row number."""
        print('trying to set focus to column "', column_name, '"')
        self.set_col_focus(self._col_idx_by_name(column_name))
        if row != self.browser.view.selected_row - self.browser.view.top_row:
            self.scroll(row - (self.browser.view.selected_row - self.browser.view.top_row))

    def search_current_col(self, search_string, down=True, skip_current=False):
        self.browser.search_column(self._selected_col, search_string, down, skip_current)
        # TODO could print help text saying the search failed.
        # TODO also, could potentially try wrapping the search just like emacs...

    def shift_selected_column(self, shift_num_to_right):
        self.browser.browse_columns = shift_list_item(self.browser.browse_columns,
                                                      self.browser.browse_columns.index(self.browser.selected_column),
                                                      shift_num_to_right)
        self.set_col_focus(self._selected_col_idx + shift_num_to_right)

    def jump_to_col(self, num):
        num = num if num >= 0 else 9 # weird special case for when the input was a '0' key
        num = min(num, len(self.browser.browse_columns) - 1)
        self.set_col_focus(num)

    def change_column_width(self, by_n):
        self.browser.view.change_column_width(self._selected_col, by_n)
        self.urwid_cols.contents[self._selected_col_idx] = (self.urwid_cols.contents[self._selected_col_idx][0],
                                                    _given(self.urwid_cols, self.browser.view.width(self._selected_col)))

    def insert_column(self, col_name, idx=None):
        try:
            if not idx or idx < 0 or idx > self._selected_col_idx:
                idx = self._selected_col_idx
        except Exception as e:
            print('exception in insert_column', e)
            idx = 0
        self.browser.browse_columns = insert_item_if_not_present(self.browser.browse_columns, col_name, idx)

    def _get_completer_with_hint(self, lst):
        return urwid_utils.ListCompleter(lst, self.urwid_frame.hint).complete

    # BROWSE COMMANDS
    def keypress(self, size, key):
        self._size = size

        # TODO this should go away in favor of a dynamic lookup
        # where the key is found in a full set of dynamically-populated keybindings
        # and then the associated function is called.
        # there might have to be a difference between the keybindings
        # registered as core functionality
        # vs the ones registered as browser functions.

        if key in keybs('browse-right'):
            self.set_col_focus(self._selected_col_idx + 1)
        elif key in keybs('browse-left'):
            self.set_col_focus(self._selected_col_idx - 1)
        elif key in keybs('browse-down'):
            self.scroll(+1)
        elif key in keybs('browse-up'):
            self.scroll(-1)
        elif key in keybs('undo'):
            self.browser.undo()
        elif key in keybs('redo'):
            self.browser.redo()
        elif key in keybs('quit'):
            raise urwid.ExitMainLoop()
        elif key in keybs('page-up'):
            self.scroll(-PAGE_SIZE)
        elif key in keybs('page-down'):
            self.scroll(PAGE_SIZE)
        elif key in keybs('help'):
            self.urwid_frame.modeline.show_basic_commands()
        elif key in keybs('hide-column'):
            self.browser.browse_columns = find_and_remove_list_item(self.browser.browse_columns, self._selected_col)
        elif key in keybs('shift-column-left'):
            self.shift_selected_column(-1)
        elif key in keybs('shift-column-right'):
            self.shift_selected_column(1)
        elif key in keybs('increase-column-width'):
            self.change_column_width(1)
        elif key in keybs('decrease-column-width'):
            self.change_column_width(-1)
        elif key in keybs('jump-to-last-row'):
            browser_utils.jump(self.browser, 1.0)
        elif key in keybs('jump-to-first-row'):
            browser_utils.jump(self.browser, 0.0)
        elif key in keybs('jump-to-numeric-column'):
            self.jump_to_col(int(key) - 1) # 1-based indexing when using number keys
        elif key in keybs('jump-to-last-column'):
            self.jump_to_col(len(self.browser.browse_columns) - 1)
        elif key in keybs('jump-to-first-column'):
            self.jump_to_col(0)
        elif key in keybs('jump-to-row'):
            self.urwid_frame.focus_minibuffer('jump-to-row')
        elif key in keybs('jump-to-column'):
            self.urwid_frame.focus_minibuffer('jump-to-column', completer=self._get_completer_with_hint(
                self.browser.browse_columns))
        elif key in keybs('insert-column'):
            self.urwid_frame.focus_minibuffer('insert-column', completer=self._get_completer_with_hint(
                list(self.browser.all_columns)))
        elif key in keybs('search'):
            self.urwid_frame.focus_minibuffer('search')
        elif key in keybs('search-backward'):
            self.urwid_frame.focus_minibuffer('search-backward')
        elif key in keybs('rename-browser'):
            self.urwid_frame.focus_minibuffer('rename-browser',
                                              default_text=self.multibrowser.active_browser_name)
        elif key in keybs('switch-to-browser'):
            self.urwid_frame.focus_minibuffer('switch-to-browser',
                                              completer=self._get_completer_with_hint(
                                                  self.multibrowser.all_browser_names))
        elif key in keybs('query'):
            self.urwid_frame.focus_minibuffer('query', default_text=self._selected_col)
        elif key in keybs('sort-ascending'):
            self.browser.call_browser_func('sort_on_columns', columns=[self.browser.selected_column], ascending=True)
        elif key in keybs('sort-descending'):
            self.browser.call_browser_func('sort_on_columns', columns=[self.browser.selected_column], ascending=False)
        elif key in keybs('command'):
            self.urwid_frame.focus_minibuffer(None)
        elif rev_keybs(key):
            cmd = rev_keybs(key)
            print('got command from keypress', key, cmd)
            self.urwid_frame.focus_minibuffer(cmd)
        else:
            self.urwid_frame.hint('got unknown keypress: ' + key)
            return None

palette = [
    ('active_col', 'light blue', 'black'),
    ('def', 'white', 'black'),
    ('modeline', 'black', 'light gray'),
    ('moving', 'light red', 'black'),
    ('active_row', 'dark red', 'black'),
    ('active_element', 'yellow', 'black'),
    ]


# there really only ever needs to be one of these instantiated at a given time,
# because it supports having arbitrary browser implementations
# assigned at any time
class TableBrowserUrwidLoopFrame:
    def __init__(self):
        self.modeline = Modeline()
        self.modeline.show_basic_commands()
        self.minibuffer = Minibuffer(self)
        self.table_view = UrwidTableView(self)
        self.inner_frame = urwid.Frame(urwid.Filler(self.table_view, valign='top'),
                                       footer=urwid.AttrMap(self.modeline, 'modeline'))
        self.frame = urwid.Frame(self.inner_frame, footer=self.minibuffer)
    def start(self, multibrowser):
        loop = urwid.MainLoop(self.frame, palette,
                              unhandled_input=self.unhandled_input)
        self.table_view.set_multibrowser(multibrowser)
        loop.run()
    def focus_minibuffer(self, command, **kwargs):
        self.frame.focus_position = 'footer'
        self.minibuffer.focus_granted(command, **kwargs)
    def focus_browser(self):
        self.table_view.update_view()
        self.frame.focus_position = 'body'
        self.minibuffer.focus_removed()
    def keypress(self, size, key):
        raise urwid.ExitMainLoop('keypress in DFbrowser!')
    def unhandled_input(self, key):
        if key == 'q' or key == 'Q':
            raise urwid.ExitMainLoop()
        elif key == 'ctrl c':
            self.modeline.set_text('got Ctrl-C')
        elif key == 'u':
            self.table_view.browser.undo()
            self.frame.focus_position = 'body'
        else:
            print('unhandled input ' + str(key))
    def hint(self, text):
        self.modeline.set_text(text)
