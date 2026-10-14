"""Field-coverage calculator (single source of truth for coverage numbers).

Categories (byte-exact, mutually exclusive, exhaustive per structure):
    S  semantic    已确认文件语义（有代码或全量样本证据）
    I  inferred    证据较强但未完全证明
    N  nonsemantic 已确认无文件语义（保留/未初始化残留/派生/绘制缓存）
    U  unknown     长度已知、语义未知
    X  unmodelled  未建模（当前文档未覆盖的区域）

Structural coverage = (S + I + N) / total      bytes whose role is known
Semantic   coverage = (S + I) / total          bytes with a known meaning

Usage: python field_coverage.py            # print markdown tables
       python field_coverage.py --sizes    # also print measured variable sizes
"""
import struct, os, sys
from collections import Counter

SONGS = r'C:\Program Files (x86)\Samilpo 2.0\8000Songs'

# ----------------------------------------------------------------------------
# Structure definitions: (name, [(offset, size, cat, label, evidence)])
# ----------------------------------------------------------------------------
STRUCTS = []
def S(name, total, fields, note=''):
    STRUCTS.append((name, total, fields, note))

# --- file level -------------------------------------------------------------
S('SYMP 头块', 0x58C, [
    (0x000, 4, 'S', 'hdrLen 重复', 'exe FUN_00424670'),
    (0x004, 4, 'S', 'magic "SYMP"', 'strncmp'),
    (0x008, 2, 'S', 'version', '版本分派'),
    (0x00A, 0x40, 'I', '曲名 CStrZ（最长达 0x40）', '与 0x06 文本对照'),
    (0x04A, 0x542, 'X', '其余（基本为 0）', '未分析'),
], '曲名长度可变；表中按 0x40 上界计入')

S('SMC 块', 0x318, [
    (0x000, 4, 'S', 'magic "SMC\\0"', 'strcmp'),
    (0x004, 4, 'S', '长度 0x318', '常量'),
    (0x312, 2, 'S', '版本', '与 SYMP 一致'),
    (0x314, 4, 'S', 'fontLen', '字体表长度'),
    (0x006, 0x30C, 'X', '其余', '未分析'),
])

S('CSMCtrlTool 块', 0x478, [
    (0x000, 0x1E0, 'I', '8 × LOGFONTA（带间隔）', '大小 0x3C 与 GetNearestFontName 对照'),
    (0x1E0, 0x24, 'U', '?', ''),
    (0x204, 4, 'U', '?', ''),
    (0x208, 0x100, 'U', '字符串/路径?', ''),
    (0x308, 0x28, 'U', '10 × u32', ''),
    (0x330, 0x40, 'U', '?', ''),
    (0x370, 4, 'U', '2 × i16', ''),
    (0x374, 0x12, 'U', '?', ''),
    (0x386, 8, 'I', '4 × i16（钳制 [-99,99][-99,99][1,48][0,16]）', '钳制常数'),
    (0x38E, 0x1A, 'U', 'i16 序列', ''),
    (0x3A8, 8, 'I', 'POINT/SIZE', '尺寸与用途'),
    (0x3B0, 0x10, 'I', 'RECT', '尺寸与用途'),
    (0x3C0, 0x48, 'U', '?', ''),
    (0x408, 0x3C, 'I', '第 9 个 LOGFONTA', '大小 0x3C'),
    (0x444, 0x1C, 'U', '?', ''),
    (0x460, 0x0E, 'I', 'velocity 表 9 字节 + 5 字节默认 0x28', '默认填充值'),
    (0x46E, 0x0A, 'U', '?', ''),
])

S('CSMFileInfo 块', 0x20, [
    (0x000, 0x20, 'U', '12 × i16 + 2 × u32', '读取位置已知，语义未定'),
], 'SetLogicPageInfo 提示为页面版式 [I]')

# --- object model -----------------------------------------------------------
S('ObjectCore（固定头）', 12, [
    (0x00, 1, 'S', 'childCount', 'Read/Write'),
    (0x01, 1, 'N', 'reserved（栈残留）', 'Write 未初始化；Read 不读'),
    (0x02, 2, 'S', 'f2 连音比例', 'CalcPlayTime MulDiv 用法'),
    (0x04, 2, 'S', 'headLen', 'Read/Write'),
    (0x06, 2, 'N', 'derivedLen = headLen+12', 'Write 派生；Read 跳过'),
    (0x08, 4, 'I', 'f8', '读写已知；消费者未全定'),
])

S('Child', 8, [
    (0x00, 4, 'S', 'key', 'GetKey 重映射'),
    (0x04, 1, 'S', 'role', 'AddMsg 写入；tie/slur 匹配'),
    (0x05, 3, 'U', 'pad[3]', ''),
])

S('MsgHdr', 0x2C, [
    (0x00, 1, 'S', 'type', 'Read/Write'),
    (0x01, 1, 'S', '括号标志 + 声部索引', 'DrawHead / DrawNote'),
    (0x02, 1, 'S', '缩放百分比', 'DrawNote SelectFont'),
    (0x03, 1, 'U', '?', ''),
    (0x04, 1, 'U', '?', ''),
    (0x05, 1, 'S', '符干状态(高4) + 附点(低4)', 'WhatIsAccidental / CalcPlayTime'),
    (0x06, 2, 'S', '符头类型 / 鼓组索引', 'SetNoteHeadType / SetParamFromMidiKey'),
    (0x08, 2, 'S', '类型相关索引', '绘制器查表'),
    (0x0A, 2, 'S', '标志位集合', 'GetPlayTime / SetTail'),
    (0x0C, 2, 'N', '绘制缓存（外接矩形）', 'DrawMsg 回写'),
    (0x0E, 2, 'N', '绘制缓存', '同上'),
    (0x10, 2, 'N', '绘制缓存', '同上'),
    (0x12, 2, 'N', '绘制缓存', '同上'),
    (0x14, 2, 'S', '起始时间（小节内 tick）', 'UpdateStartTime'),
    (0x16, 2, 'S', '相对 X 偏移', '各绘制器'),
    (0x18, 2, 'S', '音高 Y 偏移', '各绘制器'),
    (0x1A, 2, 'N', '外接矩形 L（缓存）', 'DrawMsg 回写'),
    (0x1C, 2, 'S', '外接矩形 R / 符干长度 / 长休止小节数', 'DrawLongrest'),
    (0x1E, 2, 'U', '?', ''),
    (0x20, 4, 'S', '端点引用键', 'tie/slur 重映射'),
    (0x24, 4, 'S', '本对象 key', 'GetKey'),
    (0x28, 4, 'I', '颜色/样式', 'DrawDynamic 用作 SetTextColor'),
])

# --- heads ------------------------------------------------------------------
S('音符 head（type 0x01）', 12, [
    (0x00, 1, 'S', 'MIDI key', 'GetMidiKey'),
    (0x01, 1, 'S', 'velocity', 'GetVelocity'),
    (0x02, 1, 'S', '常量 0x40', '652338/652338'),
    (0x03, 1, 'S', 'voice', '与 MsgHdr+0x01 一致'),
    (0x04, 4, 'S', '时值（tick）', 'GetRealNoteDur'),
    (0x08, 4, 'S', '起始时间', 'UpdateStartTime'),
])

S('歌词 head（type 0x19，16 字节前缀）', 16, [
    (0x00, 2, 'S', '字体索引', 'GetFontName'),
    (0x02, 1, 'S', '样式位', 'DrawMsg & 1/2/4'),
    (0x03, 1, 'N', '未初始化残留', '读写两侧一致'),
    (0x04, 2, 'S', '字号（0→13）', 'DrawMsg'),
    (0x06, 2, 'N', '未初始化残留', '同上'),
    (0x08, 4, 'S', '颜色 COLORREF', 'SetTextColor'),
    (0x0C, 1, 'S', '文本字节长度', 'MyDrawTextOutW'),
    (0x0D, 1, 'N', '未初始化残留', '同上'),
    (0x0E, 1, 'N', '未初始化残留', '同上'),
    (0x0F, 1, 'N', '未初始化残留', '同上'),
], '文本本体在 +0x10 起，长度 = head+0x0C')

S('FretInfo（type 0x46）', 16, [
    (0x00, 2, 'S', '基准品位 baseFret', 'FretInfoToLineString this[0x12]'),
    (0x02, 6, 'S', '6 弦品位', 'GetMidiKeyOfString / IsFretEmpty'),
    (0x08, 8, 'I', '4 组 (起始,结束) 对', 'FretInfoToLineString 遍历 4 对'),
])

S('RtmData 固定头', 0x10, [
    (0x00, 4, 'S', 'totalSize（含自身 4 字节）', '101/101 = 已消耗+4'),
    (0x04, 2, 'S', 'stride（恒 0x10）', '101/101'),
    (0x06, 2, 'U', '字段 A', ''),
    (0x08, 2, 'U', '字段 B', ''),
    (0x0A, 4, 'S', 'eventCount', 'Read/Write'),
    (0x0E, 2, 'S', 'eventSize（恒 0x10）', '101/101'),
])

S('RtmData 第二段头', 4, [
    (0x00, 2, 'S', 'count2', 'Read/Write'),
    (0x02, 2, 'S', 'size2（恒 6）', '101/101'),
])

# --- layout -----------------------------------------------------------------
S('StaffTail', 0x70, [
    (0x00, 0x20, 'S', '谱表名', 'CSMStaff::Read + DrawMsg'),
    (0x20, 1, 'I', '谱表序号', '单值字段'),
    (0x21, 1, 'S', '谱号类别', 'DrawHead / ChangeNoteDirection 判定'),
    (0x22, 1, 'U', '?', ''),
    (0x23, 0x20, 'S', '4 × 调号数组[8]', 'WhatIsAccidental'),
    (0x2B, 8, 'U', '间隔区', '未建模'),
    (0x4B, 1, 'U', '?', ''),
    (0x4C, 3, 'U', '?', ''),
    (0x4F, 5, 'U', '间隔区', '未建模'),
    (0x54, 2, 'U', '?', ''),
    (0x56, 0x16, 'U', '间隔区', '未建模'),
    (0x6C, 4, 'S', 'nMeas', 'CSMStaff::Read'),
], '调号数组 2/3/4 位于 +0x33/+0x3B/+0x43（本表按连续区间归并）')

S('MeasCore（固定头）', 12, [
    (0x00, 1, 'S', 'childCount', 'CSMMeas::Read'),
    (0x01, 1, 'N', '不读', ''),
    (0x02, 2, 'S', 'f2 → +0x1C', 'CSMMeas::Read'),
    (0x04, 2, 'S', 'headLen（i16）', 'CSMMeas::Read'),
    (0x06, 2, 'N', '不读（通用处为派生长度）', ''),
    (0x08, 4, 'S', 'f8 → +0x82 / +0x18', 'CSMMeas::Read'),
])

S('MeasTail', 0x60, [
    (0x00, 1, 'S', '拍号模式', 'CalcWholeCount 分支'),
    (0x01, 0x12, 'U', '间隔区', '未建模'),
    (0x13, 0x10, 'S', '拍号文本串', 'CString 构造'),
    (0x23, 0x10, 'U', '间隔区', '未建模'),
    (0x33, 0x10, 'I', '第二文本串', 'memcpy 0x10'),
    (0x43, 1, 'U', '?', ''),
    (0x44, 1, 'U', '?', ''),
    (0x45, 1, 'U', '?', ''),
    (0x46, 1, 'S', '调号类型（==8 无调号）', 'WhatIsAccidental'),
    (0x47, 1, 'U', '?', ''),
    (0x48, 1, 'U', '?', ''),
    (0x49, 1, 'U', '?', ''),
    (0x4A, 1, 'U', '?', ''),
    (0x4B, 1, 'U', '?', ''),
    (0x4C, 1, 'U', '?', ''),
    (0x4D, 1, 'U', '?', ''),
    (0x4E, 2, 'U', '?', ''),
    (0x50, 2, 'U', '?', ''),
    (0x52, 2, 'U', '?', ''),
    (0x54, 2, 'U', '间隔区', '未建模'),
    (0x56, 2, 'S', '拍号分子', 'CalcWholeCount'),
    (0x58, 2, 'S', '拍号分母', 'CalcWholeCount'),
    (0x5A, 1, 'S', '调号符号', 'WhatIsAccidental'),
    (0x5B, 1, 'U', '?', ''),
    (0x5C, 1, 'S', '调号个数', 'WhatIsAccidental'),
    (0x5D, 1, 'U', '?', ''),
    (0x5E, 2, 'S', '显示开关', 'doc+0x999 全局控制'),
])

S('PageHdr', 0x18, [
    (0x00, 2, 'S', 'nBlockA', 'CSMPage::Read'),
    (0x02, 2, 'S', 'nBlockB', 'CSMPage::Read'),
    (0x04, 2, 'S', 'nPageMsg', 'CSMPage::Read'),
    (0x06, 2, 'U', '?', ''),
    (0x08, 0x10, 'S', 'RECT', 'FUN_10071ee0'),
])

S('BlockHdr', 0x1C, [
    (0x00, 1, 'S', 'type（谱表组选择）', 'CSMBlock::Read'),
    (0x01, 1, 'S', 'nStaves', 'CSMBlock::Read'),
    (0x02, 2, 'S', 'f2（小节坐标数-1）', 'Read/Write _Size'),
    (0x04, 2, 'S', 'startMeas', 'CSMBlock::Read'),
    (0x06, 2, 'U', '?', ''),
    (0x08, 1, 'S', 'nPts', 'CSMBlock::Read'),
    (0x09, 3, 'U', '?', ''),
    (0x0C, 0x10, 'S', 'RECT', 'FUN_10071ee0'),
])

S('Block StaffRef', 5, [
    (0x00, 1, 'S', 'staffIdx', 'CSMBlock::Read/Write'),
    (0x01, 2, 'S', '→ +0xB4 数组', 'FUN_10003180'),
    (0x03, 2, 'I', '→ +0x7C 数组（默认 0xFFEC）', 'Read/Write'),
])

S('SystemHdr', 8, [
    (0x00, 2, 'S', 'nStaff1', 'CSMSystem::Read'),
    (0x02, 2, 'S', 'nStaff2', 'CSMSystem::Read'),
    (0x04, 4, 'S', 'wholeTick', 'CalcWholeCount'),
])

S('FontRecord（单条）', 3, [
    (0x00, 1, 'S', 'index', 'CFontDatas::LoadBuffer'),
    (0x01, 1, 'S', 'nameLen', '同上'),
    (0x02, 1, 'S', 'name 首字节（按最短计）', '889F 文本'),
], 'name 长度可变；本表按最小 3 字节计')


def tally(fields):
    c = Counter()
    for off, size, cat, label, ev in fields:
        c[cat] += size
    return c


def main():
    rows = []
    tS = tI = tN = tU = tX = 0
    for name, total, fields, note in STRUCTS:
        c = tally(fields)
        used = sum(c.values())
        s, i, n, u, x = c['S'], c['I'], c['N'], c['U'], c['X']
        if 'X' in c and used != total:
            # treat remainder as unmodelled for structures declared shorter
            x += total - used
        structural = (s + i + n) / total
        semantic = (s + i) / total
        rows.append((name, total, s, i, n, u, x, structural, semantic))
        tS += s; tI += i; tN += n; tU += u; tX += x

    print('| 结构 | 总字节 | S 语义 | I 推断 | N 无语义 | U 未知 | X 未建模 | 结构覆盖 | 语义覆盖 |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for (name, total, s, i, n, u, x, st, se) in rows:
        print('| %s | %d | %d | %d | %d | %d | %d | %.1f%% | %.1f%% |' % (
            name, total, s, i, n, u, x, st * 100, se * 100))
    tot = sum(r[1] for r in rows)
    print('| **合计** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** | **%.1f%%** | **%.1f%%** |' % (
        tot, tS, tI, tN, tU, tX,
        (tS + tI + tN) / tot * 100, (tS + tI) / tot * 100))
    print()
    print('类别合计： S=%d  I=%d  N=%d  U=%d  X=%d   （合计 %d 字节）' % (tS, tI, tN, tU, tX, tot))
    print('无语义占比： %.1f%%   未解释占比： %.1f%%' % (
        tN / tot * 100, (tU + tX) / tot * 100))

    # ---- layered summaries -------------------------------------------------
    BULK = {'SYMP 头块', 'SMC 块', 'CSMCtrlTool 块', 'CSMFileInfo 块'}
    CORE = {'ObjectCore（固定头）', 'Child', 'MsgHdr', '音符 head（type 0x01）',
            '歌词 head（type 0x19，16 字节前缀）', 'FretInfo（type 0x46）',
            'RtmData 固定头', 'RtmData 第二段头', 'MeasCore（固定头）',
            'SystemHdr', 'FontRecord（单条）', 'Block StaffRef'}
    LAYOUT = {'StaffTail', 'MeasTail', 'PageHdr', 'BlockHdr'}

    def summarize(title, names):
        s = i = n = u = x = t = 0
        for (nm, total, ss, ii, nn, uu, xx, _, _) in rows:
            if nm in names:
                s += ss; i += ii; n += nn; u += uu; x += xx; t += total
        if not t:
            return
        print()
        print('%s：总 %d 字节；S=%d I=%d N=%d U=%d X=%d' % (title, t, s, i, n, u, x))
        print('  结构覆盖 %.1f%%（S+I+N）；语义覆盖 %.1f%%（S+I）；未解释 %.1f%%（U+X）' % (
            (s + i + n) / t * 100, (s + i) / t * 100, (u + x) / t * 100))

    summarize('核心层（对象模型 + 消息头 + 各 head + 结构头）', CORE)
    summarize('布局层（Staff/Meas/Page/Block 的尾块与头）', LAYOUT)
    summarize('文件级大块（多为固定保留区）', BULK)
    summarize('全部', set(nm for (nm, *_rest) in rows))


if __name__ == '__main__':
    main()
