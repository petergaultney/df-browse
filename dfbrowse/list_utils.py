# list utility functions

def insert_item_if_not_present(lst, item, index):
    if item in lst and lst[index] == item:
        return lst # done. no new list, b/c no change happened.
    new_lst = lst[:] # make new list, b/c we're making a change
    if item in lst:
        cur_idx = new_lst.index(item)
        new_lst.insert(index, new_lst.pop(cur_idx))
    else:
        new_lst.insert(index, item)
    return new_lst

def find_and_remove_list_item(lst, item):
    try:
        return remove_list_index(lst, lst.index(item))
    except:
        return lst

def remove_list_index(lst, index):
    try:
        new_lst = lst[:]
        del new_lst[index]
        return new_lst
    except:
        return lst

def shift_list_item(lst, idx, to_right):
    if idx < len(lst) and idx >= 0:
        new_idx = idx + to_right
        if new_idx < len(lst) and new_idx >= 0 and idx != new_idx:
            item = lst[idx]
            new_lst = lst[:]
            del new_lst[idx]
            new_lst.insert(new_idx, item)
            return new_lst
    return lst # no change
