

def jump(browser, location, _1_based_indexing=True):
    """Location may be an integer row index, a column name, or a percentage of the browser's rows between 0.0 and 1.0"""
    if isinstance(location, int):
        browser.selected_row = location - 1 if _1_based_indexing else location
    elif isinstance(location, float):
        assert location >= 0.0 and location <= 1.0
        browser.selected_row = int(location * (len(browser) - 1))
    else: # assume it's a column name
        browser.selected_column = location

def scroll_rows(browser, n):
    """Safely caps to valid ranges."""
    new_row = max(0, min(browser.selected_row + n, len(browser) - 1))
    browser.selected_row = new_row
