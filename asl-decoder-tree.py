#!/usr/bin/env python3

""" asl-decoder-tree.py

Recover mask/match pairs for encodings in `arch_decode.asl` (produced with
[`alastairreid/mra_tools`](https://github.com/alastairreid/mra_tools)). 

Most of this code is derived from [`alehed/aslutils`](https://github.com/alehed/aslutils), 
specifically [`parse_asl_file.py`](https://github.com/alehed/aslutils/blob/master/aslutils/parse_asl_file.py).

"""

import re
import copy
import json
DECODE_RE       = r"__decode ([a-zA-Z]\w*)"
FIELD_RE        = r"__field ([a-zA-Z]\w*) (\d+) \+: (\d+)"

# This regex for case statements may be slightly wrong?
CASE_EMPTY_RE   = r"case \(\) of"
CASE_RE         = r"case \(((?:(\d+) \+: (\d+)|[a-zA-Z]\w*|(?:\w*|:)+)(?:, (?:(\d+) \+: (\d+)|[a-zA-Z]\w*|(?:\w*|:)+))*)\) of"

WHEN_EMPTY_RE   = r"when \(\) =>"
WHEN_VALS_RE    = r"when \(((?:_|!?'[01x]+'|'[01x]+' to '[01x]+')(?:, (?:_|!?'[01x]+'|'[01x]+' to '[01x]+'))*)\) =>"

ENCODING_RE     = r"__encoding ([a-zA-Z]\w*)"

def bitmask(start, length): 
    """ Given the starting bit index and length, return a bitmask """
    return ((1 << length) - 1) << start

def value_from_match(bitstr):
    """ Given some field bitstring in a 'when' statement, return the value.
    """
    return int(bitstr.replace("x", "0"), 2)

def mask_from_match(bitstr):
    """ Given some field bitstring in a 'when' statement, return the submask.
    """
    if "x" not in bitstr: 
        return int(bitstr.replace("0", "1"))
    else:
        return int(bitstr.replace("0", "1").replace("x", "0"), 2)



class AslNode:
    def __init__(self, data: str):
        self.data = data
        self.children = []
    def has_children(self) -> bool:
        return len(self.children) != 0 


class AslFile:
    def __init__(self, filename):
        self.filename = filename
        self.tree = AslFile.preprocess(filename)

    def preprocess(filename):
        """ This is from `mra_tools`, `parse_asl_file.py`.
        Convert lines into a tree 
        """
        decode_asl_file = open(filename, "r")
        lines = decode_asl_file.readlines()
        processed_lines = []
        for line in lines:
            assert int(line.find(line.lstrip())) % 4 == 0
            asl_indents = int(line.find(line.lstrip()) / 4)
            comment_start = line.find("//")
            if comment_start != -1:
                line = line[:comment_start]
            line = line.strip(" \t\n")
            if line != "":
                processed_lines += [(asl_indents, line)]

        tree = []
        current_stack = []
        for line in processed_lines:
            asl_indents = line[0]
            #node = ([], line[1])
            node = AslNode(line[1])
            if asl_indents == 0:
                tree += [node]
                current_stack = [node]
            else:
                while len(current_stack) > asl_indents:
                    current_stack = current_stack[:-1]
                current_stack[-1].children.append(node)
                current_stack += [node]
        return tree

class FieldDecl():
    def __str__(self):
        return "FieldDecl({}, {}, {})".format(self.name, self.start, self.length)
    def __init__(self, name, start, length):
        self.name = name
        self.start = int(start)
        self.length = int(length)

    def mask(self):
        return bitmask(self.start, self.length)

class CaseDecl():
    def __str__(self):
        return "CaseDecl(fields={})".format(self.fields)
    def __init__(self, fields, field_decls: list[FieldDecl]):
        self.fields = fields
        self.field_decls = field_decls


class WhenDecl():
    def __str__(self):
        return "WhenDecl(vals={}, terminal={})".format(self.vals, self.terminal)

    def __init__(self, vals, terminal):
        self.vals = vals
        self.terminal = terminal

class EncodingTree:
    def __init__(self, case_stack, when_stack, data):
        self.case_stack = case_stack
        self.when_stack = when_stack
        self.data = data


class AslVisitor:
    def __init__(self):
        self.encodings = []
        self.case_stack = []
        self.when_stack = []

        # local to 'when' context
        self.field_stack = []

    def walk(self, node: AslNode, idt=0):
        sp = " "*idt

        if node.data.startswith("__decode"): 
            for child in node.children:
                self.walk(child, idt=idt+1)

        elif node.data.startswith("__field"): 
            assert not node.has_children()
            m = re.fullmatch(FIELD_RE, node.data)
            f = m.groups()
            decl = FieldDecl(f[0], f[1], f[2])
            self.field_stack.append(decl)
            #print(sp, decl)

        elif node.data.startswith("case"): 
            assert node.has_children()
            empty_m = re.fullmatch(CASE_EMPTY_RE, node.data)
            fields = []
                
            if empty_m:
                fields = []
            else:
                m = re.fullmatch(CASE_RE, node.data)
                fields = m.groups()[0].split(", ")

            case = CaseDecl(fields, copy.deepcopy(self.field_stack))
            #print(sp, "case ", fields)

            self.case_stack.append(case)

            for child in node.children:
                self.walk(child, idt=idt+1)

            self.case_stack.pop()


        elif node.data.startswith("when"): 
            empty_m = re.match(WHEN_EMPTY_RE, node.data)
            vals_m = re.match(WHEN_VALS_RE, node.data)
            if empty_m:
                vals = []
                terminal = node.data[empty_m.end():]
            elif vals_m:
                vals = vals_m.groups()[0].split(", ")
                terminal = node.data[vals_m.end():]

            when = WhenDecl(vals, terminal)
            #print(sp, "when ", vals, terminal)

            self.when_stack.append(when)

            if not node.has_children():
                enc = EncodingTree(
                    copy.deepcopy(self.case_stack),
                    copy.deepcopy(self.when_stack),
                    terminal
                )
                self.encodings.append(enc)
                #print(sp, "TERMINAL when ", vals, terminal)


            for child in node.children:
                self.walk(child, idt=idt+1)

            self.when_stack.pop()
            self.field_stack = []

        else:
            print(f"Unexpected input: {node.data}")
            exit(-1)

class Case():
    def __init__(self, decl: CaseDecl):
        self.fields = []
        for f in decl.fields: 
            self.fields.append(CaseField(f, decl.field_decls))

class CaseField():
    def __str__(self):
        return "CaseField(s={}, kind={}, mask={:08x})".format(
                self.s, self.kind, self.mask
        )

    def resolve_field(s, decls: list[FieldDecl]):
        for d in decls:
            if d.name == s: 
                return d
        raise Exception("no field match for '{}'".format(s))


    def __init__(self, s, field_decls: list[FieldDecl]):
        self.s = s
        self.kind = None
        self.name = None
        self.start = None
        self.len = 0
        self.mask = 0
        self.child_masks = []

        # Reference to previously declared field
        if re.fullmatch(r"[a-zA-z]\w*", s):
            f = CaseField.resolve_field(s, field_decls)
            self.mask = f.mask()
            self.start = f.start
            self.len = f.length
            self.kind = "named"
            self.name = s

        # Literal match 
        elif re.fullmatch(r"\d+ \+: \d+", s):
            self.kind = "literal"
            sub = s.split("+:")
            self.mask = bitmask(int(sub[0]), int(sub[1]))
            self.start = int(sub[0])
            self.len = int(sub[1])

        # Concatenate some previously declared fields
        elif re.fullmatch(r"[a-zA-z]\w*(:[a-zA-Z]\w*)*", s):
            self.kind = "concat"
            names = s.split(":")
            start_indicies = []
            for name in names:
                f = CaseField.resolve_field(name, field_decls)
                self.child_masks.append(f)
                self.mask |= f.mask()
                self.len += f.length
                start_indicies.append(f.start)
            self.start = max(start_indicies)
        else:
            print(f"unmatched case field {s}")
            exit()

class When():
    def __init__(self, decl: WhenDecl, current_case: Case):
        self.fields = []
        assert len(decl.vals) == len(current_case.fields)
        for val, field in zip(decl.vals, current_case.fields):
            self.fields.append(WhenField(val, field))

class WhenField():
    def __str__(self):
        if self.mask:
            mask = "{:08x}".format(self.mask)
        else:
            mask = "none"
        if self.empty:
            val = "none"
        else:
            val = "{:08x}".format(self.value)

        return "WhenField(s={}, val={}, mask={})".format(self.s, val, mask)

    """ Representation of one field in a when statement """
    def __init__(self, s, field):
        self.s = s
        self.negate = None
        self.empty = None
        self.mask = None
        self.value = None
        if s == "_": 
            self.empty = True
            return

        m = re.match(r"(!)?'([0|1|x]*)'", s)
        if m.groups()[0] != None:
            self.negate = True

        self.mask = mask_from_match(m.groups()[1])
        if self.mask != None:
            self.mask <<= field.start

        self.value = value_from_match(m.groups()[1]) << field.start
 
class Encoding:
    def __str__(self):
        return "{:08x} {:08x} {}".format(self.mask, self.val, self.name)
    def __init__(self, name, mask, val):
        namestr = name.strip().replace("__encoding", "").replace(" ", "")
        namestr = namestr.lstrip("A64_")

        self.name = namestr
        self.mask = mask
        self.val = val

class EncodingDb:
    def __init__(self):
        self.encodings = []
    def stats(self):
        stats = {}
        for enc in self.encodings:
            s = enc.name.split("_")
            n = "_".join(s[0:1])
            if n in stats:
                stats[n] += 1
            else:
                stats[n] = 1
        return stats

    def add(self, enc: Encoding):
        self.encodings.append(enc)

    def dump(self):
        for enc in db.encodings:
            print("(0x{:08x}, 0x{:08x}, \"{}\"),".format(
                enc.mask, enc.val, enc.name.lstrip().rstrip().replace("__encoding", "")
            ))


if __name__ == "__main__":
    db = EncodingDb()

    f = AslFile("./arch_decode.asl")
    v = AslVisitor()
    v.walk(f.tree[0])

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

        db.add(Encoding(enc.data, constraint_mask, constraint_val))

    #print("// Stats: {}".format(json.dumps(db.stats(), indent=1)))

    db.dump()


