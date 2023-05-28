# chunk search utils

# from gui_debug import *

def not_at_end(lengthable, position, down):
    return position < len(lengthable) if down else position > 0


def get_next_chunk(sliceable, start_position, chunk_size, down):
    """includes start_position, of size chunk_size"""
    if not down:
        chunk_beg = max(0, start_position - chunk_size + 1)
        # print('yielding chunk upwards from ', chunk_beg, 'to', start_position + 1)
        return sliceable[chunk_beg:start_position + 1], chunk_beg
    else:
        chunk_end = min(len(sliceable), start_position+chunk_size)
        # print('yielding chunk downwards from', start_position, 'to', chunk_end)
        return sliceable[start_position:chunk_end], start_position


def search_chunk_yielder(sliceable, start_location, down=True, chunk_size=100):
    start_of_next_chunk = start_location
    while not_at_end(sliceable, start_of_next_chunk, down):
        yield get_next_chunk(sliceable, start_of_next_chunk, chunk_size, down)
        start_of_next_chunk = start_of_next_chunk + chunk_size if down else start_of_next_chunk - chunk_size
    raise StopIteration


def search_list_for_str(lst, search_string, starting_item, down, case_insensitive):
    """returns index into list representing string found, or None if not found"""
    search_string = search_string.lower() if case_insensitive else search_string
    search_slice_end = len(lst) if down else 0
    search_list = lst[starting_item:] if down else reversed(lst[:starting_item+1])
    # print('searching list of size', len(lst), 'down' if down else 'up', 'from', starting_item, 'to', search_slice_end, 'for:', search_string)
    for idx, s in enumerate(search_list):
        s = s.lower() if case_insensitive else s
        if s.find(search_string) != -1:
            # print('found! ', s, 'at', idx, 'starting from', starting_item, 'in list of len', len(lst), 'down?', down)
            return starting_item + idx if down else starting_item - idx
    return None


def search_sliceable_by_yielded_chunks_for_str(sliceable, search_string, starting_index, down, case_insensitive):
    """This is the main entry point for everything in this module."""
    for chunk, chunk_start_idx in search_chunk_yielder(sliceable, starting_index, down):
        found_at_chunk_idx = search_list_for_str(chunk, search_string, 0 if down else len(chunk) - 1, down, case_insensitive)
        if found_at_chunk_idx is not None:
            return found_at_chunk_idx + chunk_start_idx
    return None
