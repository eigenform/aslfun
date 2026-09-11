#!/usr/bin/env python3

""" dump-templates.py
Recover mask/match pairs for encodings in `arch_decode.asl`.
Writes entries to stdout as a space-separated tuple. 
"""

from aslfun.asl import *
from aslfun.db import *

db = EncodingDb()
f = AslFile("./arch_decode.asl")
v = AslVisitor()
v.walk(f.tree[0])

# Dump all of the discovered encodings
for enc in v.encodings:
    constraint_mask = 0x0000_0000
    constraint_val  = 0x0000_0000
    for (case_decl, when_decl) in zip(enc.case_stack, enc.when_stack):
        case = Case(case_decl)
        when = When(when_decl, case)
        for (case_field, when_field) in zip(case.fields, when.fields):
            if when_field.mask == None and when_field.value == None:
                continue
            #print(case_field, when_field)
            effective_mask = case_field.mask & when_field.mask
            constraint_mask |= effective_mask
            constraint_val  |= when_field.value

    # NOTE: Just ignore these for now...
    #if "sme" in enc.data: continue
    #if "sve" in enc.data: continue
    #if "UNPREDICTABLE" in enc.data: continue
    #if "UNALLOCATED" in enc.data: continue
    db.add(Encoding(enc.data, case.field_decls, constraint_mask, constraint_val))

db.dump()
#db.dump_uniq_by_pair()
#db.dump_json()


