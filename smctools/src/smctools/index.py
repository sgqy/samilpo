"""Index function — placeholder (占位).

Planned, not yet analyzed or implemented:

* ``convert``  read the install's own indexes (``IndexFiles/SamIlPo.idx``,
               ``Score.sci``, ``KcgInfo.kbd``) into an open, documented form.
* ``query``    look up scores through the converted index (title, singer, ...).

No format evidence has been collected for any of these files yet (they are the
program's own binary indexes, unrelated to the .cod text tables). This module
deliberately does nothing beyond announcing itself; exit code 2 so a caller
cannot mistake the stub for success.
"""

import sys


def run(args=None):
    print('smctools index: 占位 —— 索引转换与乐谱查询尚未实现', file=sys.stderr)
    print('  计划输入: <install>/IndexFiles/SamIlPo.idx, Score.sci, KcgInfo.kbd',
          file=sys.stderr)
    print('  计划能力: convert（索引转开放格式）/ query（按索引查乐谱）', file=sys.stderr)
    return 2
