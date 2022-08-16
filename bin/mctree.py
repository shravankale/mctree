#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

script = Path(sys.argv[0]).absolute()
print("script: ",script)
thisscript = Path(__file__)
#thisscript = Path("/home/skale/projects/summer22/mctree/bin/mctree.py")
print("thisscript: ",thisscript)

sys.path.insert(0,str( (thisscript.parent.parent / 'src').absolute() ))
from mctree.__main__ import main

if errcode := main(argv=sys.argv):
    exit(errcode)
