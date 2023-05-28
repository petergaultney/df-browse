import urwid
import sys
import os


# It appears that I found this here: https://wiki.goffi.org/wiki/Urwid-satext/en
class AdvancedEdit(urwid.Edit):
    """Edit box with some custom improvments
    new chars:
              - C-a: like 'home'
              - C-e: like 'end'
              - C-k: remove everything on the right of the cursor
              - C-w: remove the word on the back
    """

    def setCompletionMethod(self, callback=None):
        """Define method called when completion is asked
        @callback: method with 2 arguments:
                    - the text to complete
                    - if there was already a completion, a dict with
                        - 'completed':last completion
                        - 'completion_pos': cursor position where the completion starts
                        - 'position': last completion cursor position
                      this dict must be used (and can be filled) to find next completion)
                   and which return the full text completed"""
        assert callable(callback) or callback is None
        self.completion_cb = callback
        self.completion_data = dict()

    def keypress(self, size, key):
        if key == 'ctrl a':
            key = 'home'
        elif key == 'ctrl e':
            key = 'end'
        elif key == 'ctrl k':
            self._delete_highlighted()
            self.set_edit_text(self.edit_text[:self.edit_pos])
        elif key == 'ctrl w':
            before = self.edit_text[:self.edit_pos]
            pos = before.rstrip().rfind(" ")+1
            self.set_edit_text(before[:pos] + self.edit_text[self.edit_pos:])
            self.set_edit_pos(pos)
        elif key == 'tab':
            try:
                before = self.edit_text[:self.edit_pos]
                if self.completion_data:
                    if (not self.completion_data['completed']
                        or self.completion_data['position'] != self.edit_pos
                        or not before.endswith(self.completion_data['completed'])):
                        print('clearing completion data', self.completion_data)
                        self.completion_data.clear()
                    else:
                        print('setting before from completion data', before)
                        before = before[:-len(self.completion_data['completed'])]
                        print('set before to completion data', before)
                print('calling completer callback', self.completion_data)
                complet = self.completion_cb(before, self.completion_data)
                # full_text = before + complet
                self.completion_data['completed'] = complet[len(before):]
                # self.completion_data['completed'] = full_text
                print(self.completion_data, before)
                self.set_edit_text(complet+self.edit_text[self.edit_pos:])
                # self.set_edit_text(full_text)
                self.set_edit_pos(len(complet))
                self.completion_data['position'] = self.edit_pos
                return
            except AttributeError:
                #No completion method defined
                pass
        rval = super(AdvancedEdit, self).keypress(size, key)
        return rval



class ListCompleter:
    def __init__(self, words, hint=sys.stdout.write):
        self.words = sorted(words) # a list of words that are 'valid'
        self.hint = hint
    def complete(self, prefix, completion_data):
        try:
            start_idx = self.words.index(completion_data['last']) + 1
            if start_idx == len(self.words):
                start_idx = 0
        except (KeyError,ValueError):
            start_idx = 0

        options = [word if word.startswith(prefix) else None for word in self.words]
        options = [word for word in options if word is not None]

        if len(options) == 0:
            print('found no options', prefix)
            # search instead for words that *contain* the 'prefix', and if only one exists,
            options = [word for word in self.words if prefix in word]
            print('found these options', options)

        self.hint('options: ' + ' '.join(str(t) for t in options))

        common_prefix = os.path.commonprefix(options)
        if start_idx == 0:
            return common_prefix

        for idx in list(range(start_idx, len(self.words))) + list(range(0, start_idx)):
            if self.words[idx].lower().startswith(prefix):
                completion_data['last'] = self.words[idx]
                return self.words[idx]
        return prefix


def get_leftmost_visible_column(urwid_cols, current_size):
    cols = urwid_cols.column_widths(current_size)
    for idx, col in enumerate(cols):
        if col != 0:
            return idx
    return 0

def get_rightmost_visible_column(urwid_cols, current_size):
    cols = urwid_cols.column_widths(current_size)
    start = get_leftmost_visible_column(urwid_cols, current_size)
    for idx, col in enumerate(cols[start:]):
        if col == 0:
            return idx + start - 1
    return idx + start - 1

def translate_urwid_col_to_browser_col(urwid_cols, ucol, browser, col_gap, current_size):
    col = get_leftmost_visible_column(urwid_cols, current_size)
    next_col_start = browser.view.width(browser.browse_columns[col])
    while ucol > next_col_start:
        col += 1
        next_col_start += browser.view.width(browser.browse_columns[col]) + col_gap
    return col
