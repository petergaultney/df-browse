# UI debug printing
import timeit

DEBUG = True
debug_filename = 'debug.log'

def debug_print(*args):
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
