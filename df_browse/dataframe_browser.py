#!/usr/bin/env python
from collections import defaultdict
import os
import sys
import copy
import functools

import pandas as pd
import numpy as np


import df_browse.urwid_table_browser as urwid_table_browser
import df_browse.dataframe_browser_functions

from df_browse.list_utils import *
from df_browse.chunk_search_utils import *
from df_browse.gui_debug import *
from .func_core import BROWSER_FUNCS

_global_urwid_browser_frame = None


def browse(df, name=None):
    print('Creating a browser...  call fg() on this object to open it.')
    mb = MultipleDataframeBrowser()
    mb.browse(mb.add_df(df, name))


def browse_dir(directory_of_csvs, ipython_session=None):
    try:
        import IPython
        ipython_session = IPython.core.getipython.get_ipython()
        print(ipython_session)
    except:
        print('*** failed to get ipython global session')
        pass
    mdb = MultipleDataframeBrowser(ipython_session=ipython_session)
    dataframes_and_names = list()
    for fn in os.listdir(directory_of_csvs):
        df = pd.read_csv(directory_of_csvs + os.sep + fn, index_col=False)
        name = fn[:-4]
        mdb.add_df(df, name)
    return mdb.browse()


class InnerObjects(object):
    pass


class MultipleDataframeBrowser(object):
    _settable_class_attributes = ['_MultipleDataframeBrowser__inner',
                                  'active_browser_name']

    """Create one of these to start browsing pandas Dataframes in a curses-style terminal interface."""
    def __init__(self, *dfs, table_browser_frame=None, ipython_session=None):
        global _global_urwid_browser_frame
        if not table_browser_frame:
            if not _global_urwid_browser_frame:
                _global_urwid_browser_frame = urwid_table_browser.TableBrowserUrwidLoopFrame()
            table_browser_frame = _global_urwid_browser_frame
        self.__inner = InnerObjects()
        self.__inner.urwid_frame = table_browser_frame
        self.__inner.browsers = dict()
        self.__inner.active_browser_name = None
        self.__inner.ipython_session = ipython_session
        for df in dfs:
            self.add_df(df)

    def add_df(self, df, name=None) -> str:
        """Direct interface to adding a dataframe. Returns name.

        Preferably provide your own name here, but if you don't, we'll assign one...
        """
        assert df is not None
        name = self._make_unique_name(name)
        print('wrapping dataframe in new table browser with name', name)
        self.__inner.browsers[name] = DataframeTableBrowser(df)
        self.__inner.browsers[name].add_change_callback(self.__inner.urwid_frame.table_view.update_view)
        if not self.__inner.active_browser_name:
            self.__inner.active_browser_name = name
        return name

    def _make_unique_name(self, name):
        if name is None:
            name = ''
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
        if key in MultipleDataframeBrowser._settable_class_attributes:
            super().__setattr__(key, value)
        else:
            self[key] = value

    def __setitem__(self, key, value):
        if key in self.__inner.browsers:
            self.__inner.browsers[self.active_browser_name]._change_df(value)
        else:
            self.add_df(value, name=key)

    def get_browser(self, name):
        return self.__inner.browsers[name]

    @property
    def active_browser(self):
        return self.__inner.browsers[self.__inner.active_browser_name] if self.__inner.active_browser_name else None

    def _set_active_browser(self, name):
        if name in self.__inner.browsers:
            self.__inner.active_browser_name = name
        else:
            print('Cannot set the active browser name to the name of a browser that doesn\'t exist.')
        return self

    @property
    def active_browser_name(self):
        return self.__inner.active_browser_name
    @active_browser_name.setter
    def active_browser_name(self, browser_name):
        self._set_active_browser(browser_name)
    @property
    def all_browser_names(self):
        return list(self.__inner.browsers.keys())

    def browse(self, name: str = ''):
        """This actually brings up the interface. Can be re-entered after it exits and returns."""
        if name:
            self._set_active_browser(name)

        self.__inner.urwid_frame.start(self)
        return self # for the ultimate chain, that returns itself so it can be started again.

    @property
    def fg(self):
        """Alias for browse"""
        return self.browse()


class DataframeBrowserHistory(object):
    # This object's members should never be modified.
    def __init__(self, df, browse_columns):
        self.df = df
        self.browse_columns = browse_columns


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

    A content accessor, indexed by column name and row index. Where either is not provided, the current
    selected column and row should be the default.

    A length, corresponding to the number of rows in the underlying table.

    A top row parameter, informing a UI which row should be the topmost visible row in the UI.

    Per column (identified by name), the following should be made available:
        the column header. This may or may not be settable.
        the column width. This must be settable, but a reasonable default value should be generated for each column.
        strings 'lines()' representing a displayable view of each row of the column. They:
            must be the exact length of the column width;
            must be pre-aligned/padded for display;
            should not necessarily contain the full content of the cell - they are for display purposes only.

    An undo history for both the browse columns and the table itself.
    Though the history may keep track of these changes internally as separate items,
    from the point of view of an external observer they are a single undo stack and cannot be undone separately.
    The browser may choose to support any amount of 'undos', from 0 to effectively infinite,
    but must provide the interface even if it does not support undo.

    A redo history, comprised of actions that were undone without any intervening 'undoable'
    table modifications having been performed. Like 'undo', the interface must be provided, but
    the actual functionality need not necessarily be implemented.

    A call_browser_func method that will take a string and a set of keyword arguments, will resolve
    that name to a function (this may be implementation-dependent), may optionally enhance the set of
    keyword arguments based on its internal logic, and will then call that function with the set of provided
    and added keyword arguments. The function's effect will be implementation dependent, but a given
    browser implementation should define a contract that it will honor for all of its browser functions.

    A browser_func_names property listing the browser functions that the browser knows about, for the purpose
    of advertising them to a user. This may or may not be an exhaustive list of the functions that
    the browser can actually resolve by name.

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

    # TODO separate out code that is a generic browser vs the dataframe-specific code.
    # TODO support displaying index as column. could use -1 as special value to indicate index in place of column name

    # Browser interface methods and properties....
    @property
    def browse_columns(self):
        """The list of columns currently being viewed, in their viewing order."""
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

    def content(self, column_name=None, row_index=None):
        column_name = column_name if column_name else self.selected_column
        row_index = row_index if row_index is not None else self.selected_row
        return self.df.iloc[row_index, self.df.columns.get_loc(column_name)]

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

    def _msg_cbs(self, table_changed=True):
        for cb in self.change_cbs:
            cb(self, table_changed)

    def call_browser_func(self, function_name, **kwargs):
        print('looking up browser function by name', function_name)
        global BROWSER_FUNCS
        if function_name in BROWSER_FUNCS:
            func = BROWSER_FUNCS[function_name]
        else:
            try: # TODO not sure if any of this really works.
                this_module = sys.modules[__name__]
                func = getattr(this_module, function_name)
            except:
                func = globals().get(function_name)
        if func is None:
            msg = 'Failed to find DF function {}'.format(function_name)
            debug_print(msg)
            raise Exception(msg)
        else:
            print('found browser function', func)
            self._call_df_func(func, **kwargs)

    @property
    def browser_func_names(self):
        global BROWSER_FUNCS
        return list(BROWSER_FUNCS.keys())

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

    def _call_df_func(self, func, **kwargs):
        assert func is not None
        new_df = func(self.df,
                      c=self._real_column_index,
                      r=self.selected_row,
                      cn=self.selected_column,
                      bcols=self.browse_columns,
                      **kwargs)
        if new_df is not None:
            self._change_df(new_df)


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
    def __len__(self):
        return len(self.df)
    @property
    def top_row(self):
        assert self._top_row >= 0 and self._top_row < len(self)
        return self._top_row
    @property
    def selected_row(self):
        assert self._selected_row >= self.top_row and self._selected_row <= self.top_row + self.view_height
        return self._selected_row
    @selected_row.setter
    def selected_row(self, new_row):
        """Sets the selected row. Row index must be valid for the backing table.

        Automatically adjusts the internal _top_row in order to keep the selected_row within the view_height."""
        assert new_row >= 0 and new_row < len(self)
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

    def change_column_width(self, column_name, n):
        self._column_cache[column_name].change_width(n)

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
            sliceable = DataframeColumnSliceToStringList(self.get_src_df(), self.column_name, self.justify)
            return search_sliceable_by_yielded_chunks_for_str(sliceable, search_string, end_of_cache_search, down, case_insensitive)


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
