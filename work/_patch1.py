import io

p = r'C:\research\samilpo\work\smc2ir.py'
t = io.open(p, encoding='utf-8').read()

old_start = t.index('# Standard guitar tuning for the six strings')
old_end = t.index('def kind_from_surfix')
old = t[old_start:old_end]
assert 'root_from_fret_info' in old and 'shape_from_fret_info' in old, 'unexpected block'
t = t[:old_start] + t[old_end:]

anchor = 'from probe_smc import walk_msgs'
assert anchor in t, 'walk_msgs import not found'
imp = ('\nfrom fret import (OPEN_STRING_MIDI, STEP_BY_PC, ALTER_BY_PC,\n'
       '                  root_from_fret_info, shape_from_fret_info, spelling_of)')
t = t.replace(anchor, anchor + imp, 1)

io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
print('patched smc2ir.py')
print('root_from_fret_info defs now:', t.count('def root_from_fret_info'))
