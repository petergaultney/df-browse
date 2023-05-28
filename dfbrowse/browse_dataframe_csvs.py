#!/usr/bin/env python

import dfbrowse
import dfbrowse.dataframe_browser_functions

import IPython

if __name__ == '__main__':
    import sys
    browser = dfbrowse.browse_dir(sys.argv[1])
    print('')
    print('    ****** Thanks for using the dataframe browser! ******')
    print('    The browser has spawned an IPython shell that will allow you to interact freely')
    print('    with the dataframes you have been browsing. A local named "browser" has been created')
    print('    under which you will find all of the dataframes that were loaded into the browser at startup.')
    print('    To resume the browser, simply type "browser.fg" and press Enter.')
    print('    To exit the IPython shell that has been spawned and go back to your shell, press Ctrl-D')
    print('')
    IPython.embed()
