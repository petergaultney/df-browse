import urwid
import sys, re, os

import df_browse.urwid_utils as urwid_utils
from df_browse.keybindings import keybs, cmd_hint

from df_browse.gui_debug import *

PAGE_SIZE = 20

# this stuff captures Ctrl-C
# ui = urwid.raw_display.RealTerminal()
# ui.tty_signal_keys('undefined', 'undefined', 'undefined', 'undefined',
#                    'undefined')

def _given(columns, width):
    return columns.options('given', width)

def generate_strings_segments_for_column(view, col_name, is_focus_col):
    column_strings = view.lines(col_name)
    selected_row = view.selected_relative
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
    # TODO remove table_browser, replace with view and is_focus_col_cb
    def __init__(self, table_browser, column_name):
        super().__init__([])
        self.table_browser = table_browser
        self.column_name = column_name
        self._focus_pile = 0
        self._create_pile()
        self.rebuild_from_view()
    def _create_pile(self, num_texts=5): # TODO this magic number is pretty dang hacky
        for i in range(num_texts):
            alignment = self.table_browser.browser.view.justify(self.column_name)
            self.contents.append((
                urwid.AttrMap(urwid.Text('', wrap='clip',
                                         align=alignment), 'def'),
                ('pack', None)))
    @property
    def is_focused(self):
        return self.table_browser.is_focus_column(self.column_name)
    def selectable(self):
        return True
    def rebuild_from_view(self):
        pile_strings = generate_strings_segments_for_column(
            self.table_browser.browser.view, self.column_name, self.is_focused)
        for idx, pile_str in enumerate(pile_strings):
            self.contents[idx][0].original_widget.set_text(pile_str)
        self._focus_pile = len(pile_strings) - 2
        self.reset_attribs()
    def _set_header_break(self):
        header = self.table_browser.browser.view.header(self.column_name)
        header += '\n...' if self.is_focused and self.table_browser.browser.view.top_row > 1 else '\n'
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
        self._set_command(command, **kwargs)
    def focus_removed(self):
        self._set_command('browsing')
        self.edit_text.set_caption('browsing... ')
        self.edit_text.setCompletionMethod()
    def give_away_focus(self):
        # this should call back to focus_removed
        self.edit_text.set_edit_text('')
        self.active_args = dict()
        self.browser_frame.focus_browser()
    def _set_command(self, command, **kwargs):
        self.active_command = command
        self.active_args = kwargs
        self.edit_text.set_caption(command + ': ')
        if self.active_command == 'query':
            self.edit_text.set_edit_text(self.active_args['column_name'])
            self.edit_text.set_edit_pos(len(self.edit_text.get_edit_text()) + 1)
        if 'completer' in self.active_args:
            self.edit_text.setCompletionMethod(self.active_args['completer'])
        if 'default_text' in self.active_args:
            self.edit_text.set_edit_text(self.active_args['default_text'])
            self.edit_text.set_edit_pos(len(self.edit_text.get_edit_text()))
        if self.active_command == None:
            # then we are typing in a custom command, so set up appropriately...
            self.edit_text.set_caption('command? ')
            self.edit_text.set_edit_text('')
            self.edit_text.setCompletionMethod(keybindings._commands.keys())

    def _search(self, search_str, down, skip_current):
        if 'search' in self.active_command:
            if down:
                self._set_command('search')
            else:
                self._set_command('search backward')
            self.browser_frame.table_view.search_current_col(search_str, down, skip_current)

    def _submit_command(self, cmd_str):
        print('handling input string', cmd_str)
        if self.active_command == 'query':
            self.browser_frame.table_view.browser.query(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'add':
            if self.browser_frame.table_view.insert_column(cmd_str):
                self.give_away_focus()
            else:
                self.browser_frame.hint(str(cmd_str) + ' column not found in table browser')
        elif self.active_command == 'name current table browser':
            self.browser_frame.table_view.name_current_browser(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'switch to table browser':
            self.browser_frame.table_view.switch_to_browser(cmd_str)
            self.give_away_focus()
        elif self.active_command == 'jump to row':
            location = float(cmd_str) if '.' in cmd_str else int(cmd_str)
            self.browser_frame.table_view.jump(location)
            self.give_away_focus()
        elif self.active_command == 'jump to column':
            self.browser_frame.table_view.jump(cmd_str)
            self.give_away_focus()
        elif self.active_command == None:
            # we've typed in a custom command!
            self.edit_text.set_caption(cmd_str)
        else:
            pass # do nothing - we don't know how to accept this input.

    def keypress(self, size, key):
        if key == 'enter':
            try:
                cmd_str = self.edit_text.get_edit_text().strip()
                self._submit_command(cmd_str)
            except Exception as e:
                print(e, self.active_command, cmd_str)
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
                elif self.active_command == 'search backward':
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

    @property
    def browser(self):
        return self.multibrowser.current_browser
    @property
    def active_browser_name(self):
        return self.multibrowser.current_browser_name
    @property
    def focus_column(self):
        return self._col_by_index(self.focus_pos)
    @property
    def focus_pos(self):
        return self.browser.focused_column_index
    def _col_by_index(self, idx):
        return self.browser.browse_columns[idx]
    def _col_idx_by_name(self, column_name):
        for idx, colname in enumerate(self.browser.browse_columns):
            if colname == column_name:
                return idx
        raise Exception('failed to find column idx with name ' + str(column_name))
    def is_focus_column(self, column_name):
        return column_name == self.focus_column

    def translate_urwid_colrow_to_browser_colrow(self, ucol, urow):
        col = self._get_leftmost_visible_column()
        next_col_start = self.browser.view.width(self.browser.browse_columns[col])
        while ucol > next_col_start:
            col += 1
            next_col_start += self.browser.view.width(self.browser.browse_columns[col]) + self._col_gap
        # self.set_col_focus(col)
        return col

    # TODO maybe move these into a container class that mirrors MultiDataframeBrowser
    def set_multibrowser(self, multibrowser):
        self.multibrowser = multibrowser
        self.update_view()

    def switch_to_browser(self, name):
        """Open an existing dataframe, or accept a new one."""
        print('switching to', name)
        self.multibrowser.set_current_browser(name)
        self.browser.add_change_callback(self.update_view)
        self.update_view()

    def name_current_browser(self, new_name):
        self.multibrowser.rename_current_browser(new_name)

    def update_view(self, browser=None):
        print('updating view')
        if len(self.browser.browse_columns) > 0:
            try:
                old_col = self.urwid_cols.focus_position
            except:
                old_col = 0
            del self.urwid_cols.contents[:]
            # TODO don't recreate these column piles - instead keep track of them
            # and re-order/refresh them as necessary, only creating new ones when brand new columns are shown
            for idx, col_name in enumerate(self.browser.browse_columns):
                pile = BrowserNamedColumnPile(self, col_name)
                column_width = self.browser.view.width(col_name)
                self.urwid_cols.contents.append((pile, _given(self.urwid_cols, column_width)))
            try:
                self.urwid_cols.focus_position = old_col
            except Exception as e:
                print('exception in update_view', e)
                self.urwid_frame.hint(str(e))
            self.update_modeline_text()

    def update_modeline_text(self):
        current_cell = str(self.browser.view.selected_row_content(
            self.browser.browse_columns[self.focus_pos]))
        self.urwid_frame.modeline.update_doc_attrs(self.multibrowser.current_browser_name,
                                                   len(self.browser.browse_columns),
                                                   len(self.browser),
                                                   self.browser.focused_column_index + 1,
                                                   self.browser.selected_row + 1,
                                                   current_cell)

    def scroll(self, num_rows):
        self.browser.view.scroll_rows(num_rows)
        self.update_view()

    def mouse_event(self, size, event, button, col, row, focus):
        self._size = size
        if event == 'mouse press':
            if button == 4.0:
                self.scroll(-1)
            elif button == 5.0:
                self.scroll(1)
            else:
                col = self.translate_urwid_colrow_to_browser_colrow(col, row)
                self.set_rowcol_focus(self._col_by_index(col), row - 2)
        return True

    def _get_leftmost_visible_column(self):
        # this isn't safe to call before the first keypress or mouse_event (when we receive size info)
        # hopefully that won't be an issue.
        cols = self.urwid_cols.column_widths(self._size)
        for idx, col in enumerate(cols):
            if col != 0:
                return idx
        return 0

    def _get_rightmost_visible_column(self):
        cols = self.urwid_cols.column_widths(self._size)
        start = self._get_leftmost_visible_column()
        for idx, col in enumerate(cols[start:]):
            if col == 0:
                return idx + start - 1
        return idx + start - 1

    def set_col_focus(self, col_num):
        # the only function allowed to directly modify urwid_cols.focus_position
        col_num = max(0, min(col_num, len(self.browser.browse_columns) - 1))
        try:
            current_focus_pos = self.focus_pos
            if current_focus_pos != col_num:
                if col_num > self._get_rightmost_visible_column():
                    self.urwid_cols.focus_position = col_num
                elif col_num < self._get_leftmost_visible_column():
                    while col_num < self._get_leftmost_visible_column():
                        self.urwid_cols.focus_position -= 1
                self.browser.focused_column_index = col_num
                self.urwid_cols.contents[current_focus_pos][0].reset_attribs()
                self.urwid_cols.contents[col_num][0].reset_attribs()
                self.update_modeline_text()
            return True
        except Exception as e:
            print('exception in set focus', e)
            return False

    def set_rowcol_focus(self, column_name, row):
        """Column name and relative row number."""
        print('trying to set focus to column "', column_name, '"')
        self.set_col_focus(self._col_idx_by_name(column_name))
        if row != self.browser.view.selected_relative:
            self.scroll(row - self.browser.view.selected_relative)

    def search_current_col(self, search_string, down=True, skip_current=False):
        if self.browser.search_column(self.focus_column, search_string, down, skip_current):
            self.update_view()
        else:
            # TODO could print help text saying the search failed.
            # TODO also, could potentially try wrapping the search just like emacs...
            pass

    def shift_col(self, shift_num):
        if self.browser.shift_column(self.focus_pos, shift_num):
            self.set_col_focus(self.browser.focused_column_index + shift_num)
            self.update_view() # TODO this incurs a double update penalty but is necessary because the focus_position can't change until we know that the shift column was actually doable/successful

    def jump_to_col(self, num):
        num = num if num >= 0 else 9 # weird special case for when the input was a '0' key
        num = min(num, len(self.browser.browse_columns) - 1)
        self.set_col_focus(num)

    def change_column_width(self, by_n):
        self.browser.view.change_column_width(self.focus_column, by_n)
        self.urwid_cols.contents[self.focus_pos] = (self.urwid_cols.contents[self.focus_pos][0],
                                                    _given(self.urwid_cols, self.browser.view.width(self.focus_column)))

    def insert_column(self, col_name, idx=None):
        try:
            if not idx or idx < 0 or idx > self.focus_pos:
                idx = self.focus_pos
        except Exception as e:
            print('exception in insert column', e)
            idx = 0
        return self.browser.insert_column(col_name, idx)

    def hide_current_col(self):
        return self.browser.hide_col_by_index(self.focus_pos)

    def _get_completer_with_hint(self, lst):
        return urwid_utils.ListCompleter(lst, self.urwid_frame.hint).complete

    def jump(self, location):
        return self.browser.jump(location)

    # BROWSE COMMANDS
    def keypress(self, size, key):
        self._size = size

        if key in keybs('merge'):
            pass
        elif key in keybs('hide column'):
            self.hide_current_col()
        elif key == 'f':
            pass # filter?
        elif key == 'i':
            self.urwid_frame.focus_minibuffer('add', completer=self._get_completer_with_hint(
                list(self.browser.all_columns)))
        elif key in keybs('browse right'):
            self.set_col_focus(self.focus_pos + 1)
        elif key in keybs('browse left'):
            self.set_col_focus(self.focus_pos - 1)
        elif key in keybs('browse down'):
            self.scroll(+1)
        elif key in keybs('browse up'):
            self.scroll(-1)
        elif key in keybs('undo'):
            self.browser.undo()
        elif key in keybs('quit'):
            raise urwid.ExitMainLoop()
        elif key in keybs('page up'):
            self.scroll(-PAGE_SIZE)
        elif key in keybs('page down'):
            self.scroll(PAGE_SIZE)
        elif key in keybs('help'):
            self.urwid_frame.modeline.show_basic_commands()
        elif key in keybs('shift column left'):
            self.shift_col(-1)
        elif key in keybs('shift column right'):
            self.shift_col(1)
        elif key in keybs('increase column width'):
            self.change_column_width(1)
        elif key in keybs('decrease column width'):
            self.change_column_width(-1)
        elif key in keybs('jump to last row'):
            self.browser.jump(1.0)
        elif key in keybs('jump to first row'):
            self.browser.jump(0.0)
        elif key in keybs('jump to numeric column'):
            self.jump_to_col(int(key) - 1) # 1-based indexing when using number keys
        elif key in keybs('jump to last column'):
            self.jump_to_col(len(self.browser.browse_columns) - 1)
        elif key in keybs('jump to first column'):
            self.jump_to_col(0)
        elif key in keybs('jump to row'):
            self.urwid_frame.focus_minibuffer('jump to row')
        elif key in keybs('jump to column'):
            self.urwid_frame.focus_minibuffer('jump to column', completer=self._get_completer_with_hint(
                self.browser.browse_columns))
        elif key in keybs('search down'):
            self.urwid_frame.focus_minibuffer('search')
        elif key in keybs('search up'):
            self.urwid_frame.focus_minibuffer('search backward')
        elif key in keybs('name current table browser'):
            self.urwid_frame.focus_minibuffer('name current table browser',
                                              default_text=self.multibrowser.current_browser_name)
        elif key in keybs('switch to table browser'):
            self.urwid_frame.focus_minibuffer('switch to table browser',
                                              completer=self._get_completer_with_hint(
                                                  self.multibrowser.all_browser_names))
        elif key in keybs('query'):
            self.urwid_frame.focus_minibuffer('query', column_name=self.focus_column)
        elif key in keybs('sort ascending'):
            self.browser.sort_on_columns([self.focus_column], ascending=True)
        elif key in keybs('sort descending'):
            self.browser.sort_on_columns([self.focus_column], ascending=False)
        else:
            self.urwid_frame.hint('got unknown keypress: ' + key)
            return None

def trace_keyp(size, key):
    if key == 'p':
        raise urwid.ExitMainLoop()
    else:
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
        loop = urwid.MainLoop(self.frame, palette, # input_filter=self.input,
                              unhandled_input=self.unhandled_input)
        self.table_view.set_multibrowser(multibrowser)
        loop.run()
    def focus_minibuffer(self, command, **kwargs):
        self.frame.focus_position = 'footer'
        self.minibuffer.focus_granted(command, **kwargs)
        self.modeline.show_command_options()
    def focus_browser(self):
        self.table_view.update_view()
        self.frame.focus_position = 'body'
        self.minibuffer.focus_removed()
    def keypress(self, size, key):
        raise urwid.ExitMainLoop('keypress in DFbrowser!')
    # def input(self, inpt, raw):
    #     print('ipt')
    #     return inpt
    def unhandled_input(self, key):
        if key == 'q' or key == 'Q':
            raise urwid.ExitMainLoop()
        elif key == 'ctrl c':
            self.modeline.set_text('got Ctrl-C')
        else:
            print('unhandled input ' + str(key))
    def hint(self, text):
        self.modeline.set_text(text)
