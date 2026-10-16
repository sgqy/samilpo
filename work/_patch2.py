import io

p = r'C:\research\samilpo\work\smc2ir.py'
t = io.open(p, encoding='utf-8').read()

# 1) Record each melody measure's authoritative length on the emitter so the
#    accompaniment can share exactly the same barline positions.
old = """    audit = {
        'measures': 0, 'measures_not_filled': 0,"""
new = """    timeline = []                                   # (start, length) per measure
    audit = {
        'measures': 0, 'measures_not_filled': 0,"""
assert old in t
t = t.replace(old, new, 1)

# 2) Capture the length right after each measure record is built in convert_group.
old2 = """        mrec = {
            'kind': 'measure', 'part': pid, 'n': mi + 1,
            'tpm': tpm, 'time': """
new2 = """        if timeline is not None and pid == 'P1':
            scale = timeline
        mrec = {
            'kind': 'measure', 'part': pid, 'n': mi + 1,
            'tpm': tpm, 'time': """
assert old2 in t
t = t.replace(old2, new2, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
print('ok')
