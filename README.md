# df-browse
Python utility that provides spreadsheet-style browsing of a Pandas dataframe within a terminal/curses environment.

It was borne out of my love for Pandas, but my frustration with how difficult it is to really navigate/browse/inspect a large dataframe while you're operating on it within IPython.

### usage

df_browse is intended to be used in conjunction with Pandas.

If you have a dataframe lying around, I'm assuming it's called `df` in your IPython session.

    import df_browse
    browser = df_browse.browse(df, 'a name for my dataframe')
    browser() # this opens the browser

Once inside the browser, you can use `Q` on your keyboard to go back to the shell.

You can navigate with arrow keys and the mouse.

Press `?` to find out about other available commands.
