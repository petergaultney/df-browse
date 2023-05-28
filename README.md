# dfbrowse

Python library that provides spreadsheet-style browsing of a Pandas
dataframe within a terminal/curses environment.

It was borne out of my love for curses-style/modal interfaces, and a frustration with how
difficult it is to really navigate/browse/inspect a large dataframe
while you're operating on it within IPython.

![alt text](./.images/see-it.png)

## Installation

Right now, there's not a great way to install this except as a
standalone environment using `poetry`.

It may also be possible to install into an existing environment using
a from-source `pip install`.

## Getting started

dfbrowse is generally intended to be used _inside_ IPython. Start by
launching IPython, then import the IPython magics:

```
import dfbrowse.ipython_main
```

If you want to jump straight into browsing, load a parquet or CSV directly:

```
%csv ~/work/project1/employees.csv emp
%pq ~/work/project2/my_data.parquet data
```

If you've already loaded a dataframe, browse it like so:
```
import pandas as pd

emp = pd.read_parquet('~/work/project2/my_data.parquet')

%show emp
```

### Inside the browser

Once inside the browser, you can navigate with arrow keys and the mouse.

Press `?` to find out about some basic navigation commands.

There are many other commands that you can discover in `keybindings.py`.

There are even more commands that can be discovered by typing `/` and
then pressing TAB. These are pre-registered functions, such as
`str_match` and `query`, that perform some operation on a
dataframe. The returned dataframe will be rendered in the browser.

In theory it is possible to write and register your own dataframe
functions as well, but this is a topic for a much larger document and
I'm not sure how well it's working anyway. If you want to do complex
transforms on your dataframe, you're probably better off to drop back
into the IPython 'shell', do your work, and then jump back into the
browser with one of the options above.

### quitting and reentering

You can use `q` on your keyboard to go back to the shell/ipython session.

Re-enter the browser via `%show <df_name>`, or `%fg` to foreground the
most recent dataframe.
