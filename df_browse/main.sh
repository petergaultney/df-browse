#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PYTHONSTARTUP=$SCRIPT_DIR/ipython_main.py ipython
