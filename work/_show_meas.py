import io
import re

p = r'C:\research\samilpo\work\smc2ir.py'
t = io.open(p, encoding='utf-8').read()

# Find the measure record emission in convert_group.
i = t.index("content_end = {}")
print(t[i - 1200:i + 400])
