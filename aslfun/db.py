
import json

class Encoding:
    """ Representing a particular instruction encoding """
    def __str__(self):
        return "{:08x} {:08x} {}".format(self.mask, self.val, self.name)
    def __init__(self, name, field_decls, mask, val):
        namestr = name.strip().replace("__encoding", "").replace(" ", "")
        namestr = namestr.lstrip("A64_")

        self.name = namestr
        self.mask = mask
        self.val = val
        self.field_decls = field_decls

class EncodingDb:
    """ Representing a set of instruction encodings """
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

    def dump_uniq_by_pair(self):
        d = {}
        for enc in self.encodings:
            if (enc.mask, enc.val) in d:
                d[(enc.mask, enc.val)].append(enc)
            else:
                d[(enc.mask, enc.val)] = [ enc ]

        for ((mask, val), encs) in d.items():
            if len(encs) <= 1: continue
            print("{:08x} {:08x}".format(mask, val))
            for e in encs:
                print("   {}".format(e.name))

    def dump_json(self):
        res = []
        for enc in self.encodings:
            res.append({"name": enc.name, "mask": enc.mask, "val": enc.val})
        print(json.dumps(res))

    def dump_arr(self):
        for enc in self.encodings:
            fields = [
                "(\"{}\", {}, {})".format(x.name,x.start,x.length)
                for x in enc.field_decls
            ]
            field_arr = "[ {} ]".format(
                ", ".join(fields)
            )
            #print(field_arr)

            print("(0x{:08x}, 0x{:08x}, \"{}\"),".format(
                enc.mask, 
                enc.val, 
                enc.name.lstrip().rstrip().replace("__encoding", ""),
            ))


    def dump(self):
        for enc in self.encodings:
            print("0x{:08x} 0x{:08x} {}".format(
                enc.mask, 
                enc.val, 
                enc.name.lstrip().rstrip().replace("__encoding", ""),
            ))


