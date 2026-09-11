#!/usr/bin/env python3

""" dump-json-tree.py
Write the decoder tree to stdout in JSON format. 
"""

from aslfun.asl import *
from aslfun.db import *

db = EncodingDb()
f = AslFile("./arch_decode.asl")
v = AslTreeToJson()
tree = v.walk(f.tree[0])
print(json.dumps(tree, indent=2))
