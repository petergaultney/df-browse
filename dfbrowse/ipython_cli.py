from pathlib import Path

from IPython.core.magic import Magics, line_magic, magics_class
from IPython.core import getipython

import pandas as pd

from .dataframe_browser import MultipleDataframeBrowser


def _parse_and_file_load(browser, load_func, line: str):
    parts = line.split()
    if not parts:
        raise ValueError('Must provide a file path.')

    path = parts[0]
    if not Path(path).exists():
        raise ValueError(f'File does not exist: {path}')

    name = parts[1] if len(parts) > 1 else None
    df = load_func(path)
    browser.add_df(df, name=name)
    return name


@magics_class
class IpythonCli(Magics):

    def __init__(self, shell):
        super(IpythonCli, self).__init__(shell)
        self.browser = MultipleDataframeBrowser(ipython_session=getipython.get_ipython())
        print('try %pq or %csv, or use %show my_df')

    @line_magic
    def get_browser(self, _):
        """Embed the browser in your globals so you can access it directly."""
        globals()['browser'] = self.browser
        return self.browser

    @line_magic
    def fg(self, name):
        self.browser.browse(name.strip() or None)

    @line_magic
    def show(self, name):
        name = name.strip()
        df = get_ipython().ev(name)
        self.browser[name] = df
        self.browser.browse(name)

    @line_magic
    def pq(self, line):
        """Loads a parquet file into the browser"""
        self.browser.browse(_parse_and_file_load(self.browser, pd.read_parquet, line))

    @line_magic
    def csv(self, line):
        """Loads a csv file into the browser"""
        self.browser.browse(_parse_and_file_load(self.browser, pd.read_csv, line))


def load_ipython_extension(ipython):
    """Load the extension in IPython."""
    ipython.register_magics(IpythonCli)
