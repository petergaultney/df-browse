# UI debug printing

import timeit
import traceback

DEBUG = True
debug_filename = 'debug.log'

def debug_print(*args):
    try:
        strs = [exception_to_string(args[0])]
    except Exception as e:
        strs = [str(x) for x in args]
    debug_file.write(' '.join(strs) + '\n')
    debug_file.flush()

def nondebug_print(*args):
    pass

if DEBUG:
    print('opening debug file!')
    debug_file = open('debug.log', 'w+')
    print = debug_print
else:
    print = nondebug_print

_start_times = list() # stack
def _st():
    global _start_times
    _start_times.append(timeit.default_timer())

def _end(name):
    global _start_times
    elapsed_time = timeit.default_timer() - _start_times.pop()
    if elapsed_time > 5:
        print('\n')
    print('{:20} {:10.2f} ms'.format(name, elapsed_time * 1000))


def exception_to_string(excp):
    stack = traceback.extract_stack()[:-3] + traceback.extract_tb(excp.__traceback__)  # add limit=??
    pretty = traceback.format_list(stack)
    return ''.join(pretty) + '\n  {} {}'.format(excp.__class__,excp)
