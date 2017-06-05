# this converts a string column into a datetime column
# if a column cannot be found, it is simply skipped
def convert_df_date_cols(df, date_cols):
    for col in date_cols:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            # this column can't be found
            pass # maybe log an error?

# KEN: this function filters by date range.
def df_filter_date_range(df, date_col, date_start=None, date_end=None):
    if date_start:
        # here we simply ask for all rows where the date_col value is >= the provided date_start
        df = df[ df[date_col] >= date_start ]
    if date_end:
        # and the same for date_end
        df = df[ df[date_col] <= date_end ]

    # IMPORTANT:
    # in both of those filter statements, we assigned the result back to the original
    # variable name in order to continue to narrow our set, since the filter
    # operation does not happen in-place, but instead returns a filtered 'view' of the dataframe.
    return df

import operator as op
import types
import numpy as np

comparison_ops_dict = {
    # '+' : op.add,
    # '-' : op.sub,
    # '*' : op.mul,
    # '/' : op.div,
    # '%' : op.mod,
    # '^' : op.xor,
    '<' : op.lt,
    '>' : op.gt,
    '<=' : op.le,
    '>=' : op.ge,
    '==' : op.eq,
    '!=' : op.ne,
    '=~' : [op.contains],
    '!~' : [op.contains, op.not_],
    }

def operator_lookup(operator):
    if isinstance(operator, (types.FunctionType, types.BuiltinFunctionType)):
        return operator # already an operator
    else:
        return comparison_ops_dict[operator]

# all sorts of things can make this except.
# the caller should be aware that invalid queries will be violently rejected.
def where(df, col_name, operator, val):
    col = df[col_name]
    operator = operator_lookup(operator)
    
    if op.contains in operator and col.dtype.type == np.object_:
        # this is a special case, because op.contains does not work with Series
        if op.not_ in operator:
            df = df[~col.str.contains(val, na=False)]
        else:
            df = df[col.str.contains(val, na=False)]
        return df
    
    try:
        # try converting the operator to the type of the column
        return df[operator(col, col.dtype.type(val))]
    except:
        # if that doesn't work, fail over to naive comparison
        return df[operator(col, val)]

    
