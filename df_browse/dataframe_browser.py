#!/usr/bin/env python
from collections import defaultdict
import os
import sys
import copy
import pandas as pd
import numpy as np

import df_browse.urwid_table_browser as urwid_table_browser

from df_browse.list_utils import *
from df_browse.chunk_search_utils import *

from df_browse.gui_debug import *

_global_urwid_browser_frame = None

# a decorator
def browser_func(f):
    this_module = sys.modules[__name__]
    print('adding function to dataframe_browser module', f, this_module, f.__name__)
    # print(this_module.__dict__.keys())
    setattr(this_module, f.__name__, f)
    # print(this_module.__dict__.keys())
    # globals()[f.__name__] = f


def browse(df, name=None):
    return MultipleDataframeBrowser().add_df(df, name).browse


def browse_dir(directory_of_csvs):
    mdb = MultipleDataframeBrowser()
    dataframes_and_names = list()
    for fn in os.listdir(directory_of_csvs):
        df = pd.read_csv(directory_of_csvs + os.sep + fn, index_col=False)
        name = fn[:-4]
        mdb.add_df(df, name)
    return mdb.browse()


class InnerObjects(object):
    pass


class MultipleDataframeBrowser(object):
    """Create one of these to start browsing pandas Dataframes in a curses-style terminal interface."""
    def __init__(self, *dfs, table_browser_frame=None):
        global _global_urwid_browser_frame
        if not table_browser_frame:
            if not _global_urwid_browser_frame:
                _global_urwid_browser_frame = urwid_table_browser.TableBrowserUrwidLoopFrame()
            table_browser_frame = _global_urwid_browser_frame
        self.__inner = InnerObjects()
        self.__inner.urwid_frame = table_browser_frame
        self.__inner.browsers = dict()
        self.__inner.active_browser_name = None
        for df in dfs:
            self.add_df(df)

    def add_df(self, df, name=None):
        """Direct interface to adding a dataframe.

        Preferably provide your own name here, but if you don't, we'll assign one..."""
        assert df is not None
        name = self._make_unique_name(name)
        print('wrapping dataframe in new table browser with name', name)
        self.__inner.browsers[name] = DataframeTableBrowser(df)
        self.__inner.browsers[name].add_change_callback(self.__inner.urwid_frame.table_view.update_view)
        if not self.__inner.active_browser_name:
            self.__inner.active_browser_name = name
        return self # for call chaining

    def _make_unique_name(self, name=''):
        name = name.strip()
        name = name if name else 'df'
        test_name = name if name != 'df' else 'df_0'
        i = 0
        while test_name in self.__inner.browsers:
            test_name = name + '_' + str(i)
            i += 1
        return test_name

    def rename_browser(self, current_name, new_name):
        """Give the named browser a different name.

        Will fail if the name is empty, or if it already exists in the Multibrowser."""
        new_name = new_name.strip()
        assert current_name and new_name
        if new_name not in self.__inner.browsers and current_name != new_name:
            browser = self.__inner.browsers.pop(current_name)
            self.__inner.browsers[new_name] = browser
            if self.__inner.active_browser_name == current_name:
                self.__inner.active_browser_name = new_name
            return True
        return False

    def rename_active_browser(self, new_name):
        """Give the active browser a different name."""
        return self.rename_browser(self.__inner.active_browser_name, new_name)

    def copy_browser(self, name, new_name=None):
        if name not in self.__inner.browsers:
            return False
        new_name = new_name if new_name else name + '_copy'
        new_name = self._make_unique_name(new_name)
        self.__inner.browsers[new_name] = copy.deepcopy(self.__inner.browsers[name])
        return True

    def open_new_browser(self, **kwargs):
        pass

    def __getitem__(self, df_name):
        """This returns the actual backing dataframe."""
        return self.__inner.browsers[df_name].df

    def __getattr__(self, df_name):
        """This returns the actual backing dataframe."""
        return self.__inner.browsers[df_name].df

    def __dir__(self):
        """Tab completion of the dataframes for IPython"""
        keys = list(self.__inner.browsers.keys())
        keys += list(dir(type(self)))
        keys += list(self.__dict__.keys())
        return keys

    def __setattr__(self, key, value):
        if key == '_MultipleDataframeBrowser__inner':
            super().__setattr__(key, value)
        else:
            self[key] = value

    def __setitem__(self, key, value):
        if key in self.__inner.browsers:
            self.__inner.browsers[self.active_browser_name]._change_df(value)
        else:
            self.add_df(key, value)

    def get_browser(self, name):
        return self.__inner.browsers[name]

    @property
    def active_browser(self):
        return self.__inner.browsers[self.__inner.active_browser_name] if self.__inner.active_browser_name else None

    def set_active_browser(self, name):
        self.__inner.active_browser_name = name
        return self

    @property
    def active_browser_name(self):
        return self.__inner.active_browser_name
    @property
    def all_browser_names(self):
        return list(self.__inner.browsers.keys())

    def browse(self):
        """This actually brings up the interface. Can be re-entered after it exits and returns."""
        self.__inner.urwid_frame.start(self)
        return self # for the ultimate chain, that returns itself so it can be started again.

    @property
    def fg(self):
        """Alias for browse"""
        return self.browse()


class DataframeBrowserHistory(object):
    def __init__(self, df, browse_columns):
        self.df = df
        self.browse_columns = browse_columns

# the DataframeTableBrowser implements an interface of sorts that
# the Urwid table browser uses to display a table.
# It maintains history and implements the API necessary for viewing a dataframe as a table.
# TODO provide separate callbacks for when the dataframe itself has changed
# vs when the column order/set has changed.
#
# Please note that this class will not behave well if you have multiple columns with the same
# column name.
class DataframeTableBrowser(object):
    """Implements the table browser contract for a single pandas Dataframe.

    The basic conceit of a table browser is something that can provide the following set of functionality:

    An underlying table (columns x rows), which can be identified by column names (strings)
    and row indices (integers).

    An ordered list of 'browse columns', which are string names that will uniquely identify
    a column within the underlying table. These columns, in the order provided, are what a UI
    should display. This list should be modifiable as well as readable.

    A list of all columns in the underlying table, including those not currently present in the set
    of browse columns. The order of these columns is not to be relied upon for any particular use.

    A selected column and row. These may be used by a UI to display highlights, and may also be used
    externally to determine the user's intent when using certain other functionality, such as search,
    column shifting, etc.
    These selections may or may not be considered as part of the undo history, depending on implementation.

    A length, corresponding to the number of rows in the underlying table.

    An undo history for both the browse columns and the table itself.
    Though the history may keep track of these changes internally as separate items,
    from the point of view of an external observer they are a single undo stack and cannot be undone separately.
    The browser may choose to support any amount of 'undos', from 0 to effectively infinite,
    but must provide the interface even if it does not support undo.

    A redo history, comprised of actions that were undone without any intervening 'undoable'
    table modifications having been performed. Like 'undo', the interface must be provided, but
    the actual functionality need not necessarily be implemented.

    """
    def __init__(self, df):
        self.history = [DataframeBrowserHistory(df, list(df.columns))]
        self.change_cbs = list()
        self._future = list()
        self.view = DataframeRowView(lambda: self.df)
        self._selected_column_index = 0 # TODO change this to be name-based.
        self.add_change_callback(self.view._df_changed)

    def __deepcopy__(self, memodict):
        dfb = DataframeTableBrowser(self.original_df)
        dfb.history = self.df_hist[:]
        dfb._future = self._future[:]
        dfb.change_cbs += [cb for cb in self.change_cbs if cb is not self.view._df_changed]
        dfb._selected_column_index = self._selected_column_index
        return dfb

    # TODO Join
    # TODO support displaying index as column. could use -1 as special value to indicate index in place of column name
    # TODO write out to file.

    # Browser interface methods and properties....
    @property
    def browse_columns(self):
        """The set of columns currently being viewed, in their viewing order."""
        return self.history[-1].browse_columns
    @browse_columns.setter
    def browse_columns(self, new_browse_columns):
        """Set the list of columns currently being viewed.

        Will raise an exception if any of the column names are not valid in the backing table."""
        self._change_browse_cols(new_browse_columns)
    @property
    def selected_row(self):
        """The index of the selected row."""
        return self.view.selected_row
    @selected_row.setter
    def selected_row(self, new_row):
        old_row = self.view.selected_row
        self.view.selected_row = new_row
        if self.selected_row != old_row:
            self._msg_cbs(table_changed=False) # TODO clean this all up
    @property
    def selected_column(self):
        """The name of the selected column."""
        return self.browse_columns[self._selected_column_index]
    @selected_column.setter
    def selected_column(self, new_focus_col):
        """Sets the selected column, either by integer index in browse_columns, or a string name.

        If the index or column name cannot be found in browse_columns, this will raise an exception.

        Attempting to set this to an empty list will result in nothing being done.
        """
        new_focus_col = new_focus_col if isinstance(new_focus_col, int) else self.browse_columns.index(new_focus_col)
        assert new_focus_col < len(self.browse_columns) and new_focus_col >= 0
        self._selected_column_index = new_focus_col
    @property
    def all_columns(self):
        return list(self.original_df.columns)

    def __len__(self):
        return len(self.df)

    def undo(self, n=1):
        """Reverses the most recent change to the browser - either the column ordering or a change to the underlying table itself."""
        if len(self.history) == 1:
            return
        table_changed = False
        while n > 0 and len(self.history) > 1:
            print('undo', n)
            self._future.append(self.history.pop())
            table_changed = table_changed or self._future[-1].df is not self.history[-1].df
            n -= 1
        assert len(self.history) > 0
        self._msg_cbs(table_changed)

    def redo(self, n=1):
        if len(self._future) == 0:
            return
        table_changed = False
        while n > 0 and len(self._future) > 0:
            print('redo', n)
            self.history.append(self._future.pop())
            table_changed = table_changed or self.history[-2].df is not self.history[-1].df
            n -= 1
        self._msg_cbs(table_changed)

    def search_column(self, column, search_string, down=True, skip_current=False):
        """Searches a column (identified by its name) for a given search string.

        This is delegated to the view because it maintains a convenient string cache."""
        found = self.view.search(column, search_string, down, skip_current)
        if found:
            self._msg_cbs(table_changed=True)
        return found

    def add_change_callback(self, cb):
        if cb not in self.change_cbs:
            self.change_cbs.append(cb)

    def call_browser_func(self, function_name, **kwargs):
        print('looking up browser function by name', function_name)
        this_module = sys.modules[__name__]
        func = getattr(this_module, function_name)
        print('found browser function', func)
        new_df = func(self.df,
                      c=self._real_column_index,
                      r=self.selected_row,
                      cn=self.selected_column,
                      **kwargs)
        if new_df is not None:
            self._change_df(new_df)

    # All properties and methods following are NOT part of the browser interface
    @property
    def df(self):
        return self.history[-1].df

    @property
    def original_df(self):
        return self.history[0].df

    # internal methods and properties
    @property
    def _real_column_index(self):
        """The actual index of the selected column in the backing dataframe."""
        self.df.columns.get_loc(self.selected_column)

    def _cap_selected_column_index(self, new_cols):
        if self._selected_column_index >= len(new_cols):
            print('changing selected column to be valid: ', len(new_cols) - 1)
            self._selected_column_index = len(new_cols) - 1

    def _change_browse_cols(self, new_cols):
        if self.browse_columns != new_cols and len(new_cols) > 0:
            for col in new_cols:
                if col not in self.all_columns:
                    raise Exception('Column {} not found in backing dataframe.'.format(col))
            print('changing browse columns')
            self._cap_selected_column_index(new_cols)
            self.history.append(DataframeBrowserHistory(self.history[-1].df, new_cols))
            self._future.clear() # can't keep future once we're making user-specified changes.
            self._msg_cbs(table_changed=False)
            return True
        return False

    def _change_df(self, new_df):
        assert isinstance(new_df, type(self.df))
        print('changing dataframe...')
        new_cols = list()
        for col in new_df.columns:
            if col not in self.browse_columns:
                new_cols.append(col)
        missing_cols = list()
        for col in self.browse_columns:
            if col not in new_df.columns:
                missing_cols.append(col)
        if len(new_cols) > 0 or len(missing_cols) > 0:
            browse_columns = [col for col in self.history[-1].browse_columns if col not in missing_cols]
            browse_columns += new_cols
            self._cap_selected_column_index(browse_columns)
            print('using new browse columns', browse_columns)
            self.history.append(DataframeBrowserHistory(new_df, browse_columns))
        else:
            self.history.append(DataframeBrowserHistory(new_df, self.history[-1].browse_columns))
        self._future.clear()
        self._msg_cbs(table_changed=True)

    def _msg_cbs(self, table_changed=True):
        for cb in self.change_cbs:
            cb(self, table_changed)


def _get_function_by_name(_class, function_name):
    try:
        # prefer class member functions
        return getattr(_class, function_name)
    except AttributeError:
        pass
    # look in globals
    possibles = globals().copy()
    # possibles.update(locals())
    return possibles.get(function_name)

class defaultdict_of_DataframeColumnSegmentCache(defaultdict):
    def __init__(self, get_df):
        self.get_df = get_df
    def __missing__(self, column_name):
        assert column_name is not None
        cc = DataframeColumnSegmentCache(lambda : self.get_df(), column_name)
        self[column_name] = cc
        return cc

# Note that DataframeTableBrowser is responsible for the columns of the dataframe and the dataframe itself
# whereas this class is responsible for the view into the rows.
# This decision is based on the fact that scrolling up and down through a dataset
# is not considered to be a useful 'undo' operation, since it is immediately reversible,
# whereas column operations (re-order, hide, etc) are reversible with extra work (they require typing column names)
# A counterpoint to this is 'jumping' through the rows - some users might find it handy to be able
# to return to their previous row position after a jump. But as of now, it's hard to see
# what the right way of handling that would be.
# searches happen here, because we are simply iterating through the strings
# for the next match.
# TODO this should probably get merged into the browser, or else the DataframeTableBrowser should
# transparently redirect function calls to this object.
class DataframeRowView(object):
    DEFAULT_VIEW_HEIGHT = 100
    def __init__(self, get_df):
        self._get_df = get_df
        self._top_row = 0 # the top row in the dataframe that's in view
        self._selected_row = 0
        self._column_cache = defaultdict_of_DataframeColumnSegmentCache(lambda: self.df)
        self.view_height = DataframeRowView.DEFAULT_VIEW_HEIGHT
        self.scroll_margin_up = 10 # TODO these are very arbitrary and honestly it might be better
        self.scroll_margin_down = 30 # if they didn't exist inside this class at all.

    @property
    def df(self):
        return self._get_df()
    @property
    def top_row(self):
        return self._top_row
    @property
    def selected_relative(self):
        assert self.selected_row >= self.top_row and self.selected_row <= self.top_row + self.view_height
        return self.selected_row - self.top_row
    @property
    def selected_row(self):
        return self._selected_row
    @selected_row.setter
    def selected_row(self, new_row):
        """Sets the selected row. Row index must be valid for the backing table.

        Automatically adjusts the internal _top_row in order to keep the selected_row within the view_height."""
        assert new_row >= 0 and new_row < len(self.df)
        old_row = self._selected_row
        self._selected_row = new_row
        if new_row > old_row:
            while self._selected_row > self._top_row + self.scroll_margin_down:
                self._top_row += 1 # TODO this could be faster
        elif new_row < old_row: # scroll up
            while self._selected_row < self._top_row + self.scroll_margin_up and self._top_row > 0:
                self._top_row -= 1
        assert self._selected_row >= self._top_row and self._selected_row <= self._top_row + self.view_height

    def header(self, column_name):
        return self._column_cache[column_name].header
    def width(self, column_name):
        return self._column_cache[column_name].width
    def lines(self, column_name, top_row=None, bottom_row=None):
        top_row = top_row if top_row is not None else self._top_row
        bottom_row = bottom_row if bottom_row is not None else min(top_row + self.view_height, len(self.df))
        return self._column_cache[column_name].rows(top_row, bottom_row)
    def selected_row_content(self, column_name):
        return self.df.iloc[self.selected_row, self.df.columns.get_loc(column_name)]
    def change_column_width(self, column_name, n):
        self._column_cache[column_name].change_width(n)
    def justify(self, column_name):
        return self._column_cache[column_name].justify

    def search(self, column_name, search_string, down=True, skip_current=False, case_insensitive=False):
        """search downward or upward in the current column for a string match.
        Can exclude the current row in order to search 'farther' in the dataframe."""
        case_insensitive = case_insensitive if case_insensitive is not None else search_string.islower()
        starting_row = self.selected_row + int(skip_current) if down else self.selected_row - int(skip_current)
        df_index = self._column_cache[column_name].search_cache(search_string, starting_row, down, case_insensitive)
        if df_index is not None:
            self.selected_row = df_index
            return True
        return False

    def _df_changed(self, browser, table_changed):
        if table_changed:
            for col_name, cache in self._column_cache.items():
                cache.clear_cache()
            self.selected_row = max(0, min(self.selected_row, len(self.df) - 1))


class DataframeColumnSegmentCache(object):
    MIN_WIDTH = 2
    MAX_WIDTH = 50
    DEFAULT_CACHE_SIZE = 200
    def __init__(self, src_df_func, column_name, std_cache_size=200, min_cache_on_either_side=50):
        self.get_src_df = src_df_func
        self.column_name = column_name
        self.is_numeric = np.issubdtype(self.get_src_df()[self.column_name].dtype, np.number)
        self.native_width = None
        self.assigned_width = None
        self.top_of_cache = 0
        self.row_strings = list()
        self._min_cache_on_either_side = min_cache_on_either_side
        self._std_cache_size = std_cache_size
    def _update_native_width(self):
        self.native_width = max(len(self.column_name), DataframeColumnSegmentCache.MIN_WIDTH)
        for idx, s in enumerate(self.row_strings):
            self.native_width = min(DataframeColumnSegmentCache.MAX_WIDTH, max(self.native_width, len(s)))
            self.row_strings[idx] = s.strip()
            if not self.is_numeric and self.row_strings[idx] == 'NaN':
                self.row_strings[idx] = ''

    def change_width(self, n):
        if not self.assigned_width:
            if not self.native_width:
                self._update_native_width()
            self.assigned_width = self.native_width
        self.assigned_width += n
        self.assigned_width = max(DataframeColumnSegmentCache.MIN_WIDTH,
                                  min(DataframeColumnSegmentCache.MAX_WIDTH, self.assigned_width))
    @property
    def justify(self):
        return 'right' if self.is_numeric else 'left'
    @property
    def header(self):
        return self.column_name
    @property
    def width(self):
        return self.assigned_width if self.assigned_width else self.native_width
    @property
    def bottom_of_cache(self):
        return self.top_of_cache + len(self.row_strings)
    def rows(self, top_row, bottom_row):
        df = self.get_src_df()
        new_top_of_cache = max(top_row - self._min_cache_on_either_side, 0)
        new_bottom_of_cache = min(len(df), max(bottom_row + self._min_cache_on_either_side,
                                               new_top_of_cache + self._std_cache_size))
        new_cache = None
        if self.top_of_cache > top_row or self.bottom_of_cache < bottom_row:
            sliceable_df = DataframeColumnSliceToStringList(df, self.column_name, self.justify)
            new_cache = sliceable_df[new_top_of_cache:new_bottom_of_cache]
            assert len(new_cache) == new_bottom_of_cache - new_top_of_cache
            print('new cache from', new_top_of_cache, 'to', new_bottom_of_cache,
                  len(self.row_strings), len(new_cache))
            self.top_of_cache = new_top_of_cache
            self.row_strings = new_cache
            self._update_native_width()
        return self.row_strings[top_row-self.top_of_cache : bottom_row-self.top_of_cache]

    def clear_cache(self):
        self.top_of_cache = 0
        self.row_strings = list()

    def search_cache(self, search_string, starting_row, down, case_insensitive):
        """Returns absolute index where search_string was found; otherwise -1"""
        # TODO this code 100% works, but could it be cleaner?
        df = self.get_src_df()
        print('***** NEW SEARCH', self.column_name, search_string, starting_row, down, case_insensitive)
        starting_row_in_cache = starting_row - self.top_of_cache
        print('running search on current cache, starting at row ', starting_row_in_cache)
        row_idx = search_list_for_str(self.row_strings, search_string, starting_row_in_cache, down, case_insensitive)
        if row_idx is not None:
            print('found item at row_idx', row_idx + self.top_of_cache)
            return row_idx + self.top_of_cache
        else:
            print('failed local cache search - moving on to iterate through dataframe')
            # search by chunk through dataframe starting from current search position in cache
            end_of_cache_search = self.top_of_cache + len(self.row_strings) if down else self.top_of_cache
            df_sliceable = DataframeColumnSliceToStringList(df, self.column_name, self.justify)
            for chunk, chunk_start_idx in search_chunk_yielder(df_sliceable, end_of_cache_search, down):
                chunk_idx = search_list_for_str(chunk, search_string, 0 if down else len(chunk) - 1, down, case_insensitive)
                if chunk_idx is not None:
                    actual_idx = chunk_idx + chunk_start_idx
                    print('found', search_string, 'at chunk idx', chunk_idx, 'in chunk starting at', chunk_start_idx,
                          'which makes real idx', actual_idx, 'with result proof:', df.iloc[actual_idx,df.columns.get_loc(self.column_name)])
                    return actual_idx
                else:
                    print('not found in this chunk...')
            return None


class DataframeColumnSliceToStringList(object):
    def __init__(self, df, column, justify):
        self.df = df
        self.column = column
        self.justify = justify
    def __getitem__(self, val):
        return self.df.iloc[val].to_string(index=False, index_names=False, header=False,
                                           columns=[self.column], justify=self.justify).split('\n')
    def __len__(self):
        return len(self.df)


if __name__ == '__main__':
    import sys
    browse_dir(sys.argv[1])
