import os
import IPython

from dfbrowse.gui_debug import *

class IPythonCompleter(object):
    def __init__(self, hint):
        self.session = IPython.core.getipython.get_ipython()
        self.hint = hint
    def complete(self, prefix, completion_data):
        try:
            safe, prefix = prefix.rsplit(' ', 1)
            safe += ' '
        except:
            safe = ''
        try:
            print('trying to complete', prefix, safe, completion_data)
            completed, options = self.session.complete(prefix)
            self.hint('options: ' + ' '.join(str(opt) for opt in options))
            common_prefix = os.path.commonprefix(options)
            print('pre', prefix, 'comp', completed, 'cp', common_prefix)
            if len(common_prefix) > len(completed):
                return safe + common_prefix
            else:
                return completed
        except Exception as e:
            print('failed to complete')
            print(e)
            return prefix

def execute_ipython_command(string):
    session = IPython.core.getipython.get_ipython()
    session.run_cell(string, silent=True, store_history=False)
    session.execution_count += 1
    session.history_manager.store_inputs(session.execution_count,
                                         string)
    return True
