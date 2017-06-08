from df_browse.gui_debug import print

from df_browse.dataframe_browser import df_func

# keyword arguments provided to dataframe mutator functions include:
# args_str, cn, c, r (where cn is column name, c is column index, and r is row index)

@df_func
def eval_df(df, args_str, cn, c=0, r=0, **kwargs):
    return eval(args_str)

@df_func
def query(df, args_str, **kwargs):
    return df.query(args_str)

@df_func
def sort_ascending_on_columns(df, args_str, **kwargs):
    columns = [arg.strip() for arg in args_str.split(',')]
    return sort_on_columns(df, columns, ascending=True, **kwargs)

@df_func
def sort_descending_on_columns(df, args_str, **kwargs):
    columns = [arg.strip() for arg in args_str.split(',')]
    return sort_on_columns(df, columns, ascending=False, **kwargs)

@df_func
def sort_on_columns(df, columns, ascending=True, algorithm='mergesort', na_position=None, **kwargs):
    """args_str is expected to be a comma-separated list of column names"""
    print('sorting on columns', columns, ascending)
    na_position = na_position if na_position is not None else ('last' if ascending else 'first')
    return df.sort_values(columns, ascending=ascending, kind=algorithm, na_position=na_position)

@df_func
def str_match(df, args_str, cn, **kwargs):
    return df.loc[df[cn].str.match(args_str, na=False)]

@df_func
def str_contains(df, args_str, cn, **kwargs):
    return df.loc[df[cn].str.contains(args_str, na=False)]

@df_func
def test_add_drop(df, args_str, **kwargs):
    df['e'] = df['level_integer'] + 5
    return df.drop('last_name', axis=1)
