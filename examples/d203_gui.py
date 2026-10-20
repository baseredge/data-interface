#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""d203 Tkinter 实时盘口大屏与协议范例 (单文件完整实现)

功能特性：
1. 全档深度 (FullQueue)：
   - 买卖十档价格与在册总量；
   - 深入每一档位的挂单微观明细 (金额1, 金额2, ...)，大单(>=50万)金色高亮；
   - 支持一键“展开千档”，横向全屏观察多档明细；再次点击“恢复实时布局”。
2. 逐笔委托 (Entrust)：
   - 毫秒级还原每一笔订单申报与撤单变动；
   - 特色撤单高亮：全部撤单与部分撤单采用暗琥珀背景与亮橙色指示条重点提示；
   - 顶部汇总统计买入/卖出委托总量、委托笔数与撤单笔数；
   - 滚到底部自动触发历史序列回溯查询 (enable=2, startseq)。
3. 逐笔成交 (Trade)：
   - 交易所每一笔撮合成交明细，按到达时序精准判定主动买卖 (主买/主卖)；
   - 万手以上大成交量金色醒目显示；
   - 滚到底部自动翻页加载历史成交 (enable=1, 扩充 num)。
4. 主力成交 (MainTrade)：
   - 专门筛选机构、主力大额成交流水；
   - 滚到底部自动翻页加载历史记录。
5. 协议报文检查器 (JSON Inspector)：
   - 内置报文日志列表与 JSON 查看器；
   - 点击任意报文即可查看格式化 JSON 原文，方便二次开发与协议学习。

依赖环境：
    python -m pip install websocket-client

启动命令：
    python d203_gui.py
    python d203_gui.py --code SH600519
    python d203_gui.py --url ws://127.0.0.1:8080/d203 --code SZ000001
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore[assignment]


# ── 全局常量与配色方案 ─────────────────────────────────────────────────────────

DEFAULT_URL = "ws://127.0.0.1:8080/d203"
DEFAULT_CODE = "SH600519"
DEFAULT_PAGE_SIZE = 200
MAX_LOG_ITEMS = 500

# 界面主配色 (与 Go 版本 Walk 客户端及深色大屏完全对齐)
BG = "#0a0e17"            # 全局深色底色
TOP = "#111111"           # 顶部工具栏与标题背景
PANEL_BG = "#0d131f"      # 面板卡片底色
INPUT_BG = "#162032"      # 输入框背景
BORDER = "#1f293d"        # 边框与网格线
BORDER_LIGHT = "#2d3748"  # 浅色边框
TEXT = "#cccccc"          # 常规文字 (浅灰)
WHITE = "#f3f4f6"         # 亮白文字
MUTED = "#8892b0"         # 次要文字 (蓝灰)
DIM = "#526079"           # 弱化文字 (深灰)
RED = "#e94560"           # 买入 / 阳线 / 上涨 (红)
GREEN = "#38a141"         # 卖出 / 阴线 / 下跌 (绿)
GOLD = "#e9c445"          # 金额 / 高亮 / 主力 (金)
BLUE = "#3498db"          # 提示蓝
CYAN = "#34b7eb"          # 全部成交 (青)
LINK = "#6aaaff"          # 新增申报 / 链接蓝
SEL_BG = "#1a2a44"        # 列表选中背景

# 撤单特色指示配色
CANCEL_ROW_BG = "#241a10"   # 暗琥珀底色
CANCEL_ROW_BAR = "#ff8c32"  # 亮橙色左侧指示条
CANCEL_TEXT_GOLD = "#ffbe46" # 部分撤单温金
CANCEL_TEXT_ORANGE = "#ff8c32" # 全部撤单亮橙

FONT_MONO = ("Consolas", 9)
FONT_MONO_BOLD = ("Consolas", 9, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 10, "bold")
FONT_MAIN_TITLE = ("Microsoft YaHei UI", 11, "bold")
FONT_SUBTITLE = ("Microsoft YaHei UI", 9)
FONT_TINY = ("Microsoft YaHei UI", 8)
FONT_WATERMARK = ("Microsoft YaHei UI", 26, "bold")


# ── 数据格式化辅助函数 ─────────────────────────────────────────────────────────

def as_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def format_time(val: Any) -> str:
    """格式化时间：支持 HHMMSSmmm 与 HHMMSS。"""
    n = as_int(val)
    if n <= 0:
        return "--:--:--"
    s = str(n)
    if len(s) > 6:
        s = s.zfill(9)
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}.{s[6:9]}"
    s = s.zfill(6)
    return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"


def format_amount(amount: int | float) -> str:
    """将元转换为万元/亿元友好显示。"""
    if not amount:
        return "0万"
    amt = float(amount)
    wan = abs(amt) / 10000.0
    sign = "-" if amt < 0 else ""
    if wan >= 10000.0:
        return f"{sign}{wan / 10000.0:.2f}亿"
    elif wan >= 100.0:
        return f"{sign}{int(round(wan))}万"
    elif wan >= 1.0:
        return f"{sign}{wan:.1f}万"
    elif wan > 0.001:
        return f"{sign}{wan:.2f}万"
    return "0万"


def format_holo_amount(amount: int | float) -> str:
    """全息队列单笔排队金额显示 (保留一位小数)。"""
    if not amount:
        return "0.0万"
    wan = float(amount) / 10000.0
    if abs(wan) >= 10000.0:
        return f"{wan / 10000.0:.1f}亿"
    return f"{wan:.1f}万"


def order_mmp_text(mmp: int) -> str:
    """委托盘口位置说明字典。"""
    if mmp == 1: return "买1"
    if mmp == 2: return "买2"
    if mmp == 3: return "买3"
    if mmp == 4: return "涨停"
    if mmp == 5: return "卖1"
    if mmp == 6: return "卖2"
    if mmp == 7: return "卖3"
    if mmp == 8: return "跌停"
    if 14 <= mmp <= 20: return f"买{mmp - 10}"
    if 24 <= mmp <= 30: return f"卖{mmp - 20}"
    if mmp == 0: return ""
    return f"档{mmp}"


def volume_code_text(vc: int) -> str:
    """单据体量级别说明。"""
    if vc == 1: return "超大单"
    if vc == 2: return "大单"
    if vc == 3: return "中单"
    if vc == 4: return "小单"
    return "—"


def entrust_status_text(status: int) -> str:
    """逐笔委托状态文本（展示状态数字与中文描述）。"""
    mapping = {
        0: "新增申报",
        1: "挂单排队",
        2: "部分成交",
        3: "部分撤单",
        4: "全部撤单",
        5: "全部成交",
        10: "主动成交",
        11: "排队撮合",
        13: "撮合部撤",
        14: "撤单终结",
        15: "全部成交",
    }
    desc = mapping.get(status, "未知")
    return f"{status} ({desc})"


def entrust_status_color(status: int) -> str:
    """逐笔委托状态文字颜色。"""
    if status in (3, 13): return CANCEL_TEXT_GOLD
    if status in (4, 14): return CANCEL_TEXT_ORANGE
    if status == 2: return GOLD
    if status in (5, 10, 15): return CYAN
    if status == 0: return LINK
    if status in (1, 11): return TEXT
    return MUTED


def direction_label(dir_code: int) -> tuple[str, str]:
    """买卖方向 (0:买, 1:卖)。"""
    if dir_code == 0:
        return "买", RED
    elif dir_code in (1, 2):
        return "卖", GREEN
    return "—", MUTED


def active_function_text(fn: int) -> tuple[str, str]:
    """主动买卖标志 (0:主买/外盘, 1:主卖/内盘)。"""
    if fn == 0:
        return "主买", RED
    elif fn in (1, 2):
        return "主卖", GREEN
    return "—", MUTED


# ── 数据结构与列表合并逻辑 (保持严格倒序) ───────────────────────────────────────

class OrderItem:
    __slots__ = (
        "time", "sequence", "order_no", "price", "volume",
        "direction", "status", "order_mmp", "volume_code", "flags"
    )

    def __init__(self, d: dict[str, Any], divisor: float = 100.0) -> None:
        self.time = as_int(d.get("time"))
        self.sequence = as_int(d.get("seq") or d.get("sequence"))
        self.order_no = as_int(d.get("order_no") or d.get("orderNo"))
        raw_price = as_int(d.get("price"))
        self.price = raw_price / divisor if divisor > 0 else raw_price / 100.0
        self.volume = as_int(d.get("volume"))
        self.direction = as_int(d.get("direction"))
        self.status = as_int(d.get("status"))
        self.order_mmp = as_int(d.get("order_mmp") or d.get("orderMmp"))
        self.volume_code = as_int(d.get("volume_code") or d.get("volumeCode"))
        self.flags = as_int(d.get("flags"))

    def key(self) -> tuple[int, int, int]:
        return (self.order_no, self.time, self.sequence)


class TradeItem:
    __slots__ = (
        "time", "sequence", "trade_no", "price", "volume", "amount",
        "buy_no", "buy_volume", "sell_no", "sell_volume",
        "active_function", "volume_code"
    )

    def __init__(self, d: dict[str, Any], divisor: float = 100.0) -> None:
        self.time = as_int(d.get("time"))
        self.sequence = as_int(d.get("seq") or d.get("sequence"))
        self.trade_no = as_int(d.get("trade_no") or d.get("tradeNo"))
        raw_price = as_int(d.get("price"))
        self.price = raw_price / divisor if divisor > 0 else raw_price / 100.0
        self.volume = as_int(d.get("volume"))

        raw_amount = as_int(d.get("amount"))
        if raw_amount > 0:
            self.amount = raw_amount
        else:
            self.amount = int(round(self.price * self.volume))

        # 买卖双方明细
        buy_info = d.get("buy") if isinstance(d.get("buy"), dict) else {}
        sell_info = d.get("sell") if isinstance(d.get("sell"), dict) else {}
        self.buy_no = as_int(d.get("buy_no") or buy_info.get("orderNo"))
        self.buy_volume = as_int(d.get("buy_volume") or buy_info.get("volume"))
        self.sell_no = as_int(d.get("sell_no") or sell_info.get("orderNo"))
        self.sell_volume = as_int(d.get("sell_volume") or sell_info.get("volume"))

        self.active_function = as_int(d.get("active_flag", d.get("activeFunction", 0)))
        self.volume_code = as_int(d.get("volume_code") or d.get("volumeCode"))

    def key(self) -> tuple[int, int, int]:
        return (self.trade_no, self.time, self.sequence)


class MainTradeItem:
    __slots__ = ("time", "trade_no", "price", "volume", "amount", "active_function")

    def __init__(self, d: dict[str, Any], divisor: float = 100.0) -> None:
        self.time = as_int(d.get("time"))
        self.trade_no = as_int(d.get("trade_no") or d.get("tradeNo"))
        raw_price = as_int(d.get("price"))
        self.price = raw_price / divisor if divisor > 0 else raw_price / 100.0
        self.volume = as_int(d.get("volume"))
        self.amount = as_int(d.get("amount"))
        if self.amount <= 0:
            self.amount = int(round(self.price * self.volume))
        self.active_function = as_int(d.get("active_flag", d.get("activeFunction", 0)))

    def key(self) -> tuple[int, int]:
        return (self.trade_no, self.time)


class QueueOperation:
    __slots__ = ("order_no", "volume", "trade_volume", "status", "flags")

    def __init__(self, d: dict[str, Any]) -> None:
        self.order_no = as_int(d.get("order_no") or d.get("orderNo"))
        self.volume = as_int(d.get("volume"))
        self.trade_volume = as_int(d.get("trade_volume") or d.get("tradeVolume"))
        self.status = as_int(d.get("status"))
        self.flags = as_int(d.get("flags"))


class QueuePriceLevel:
    __slots__ = ("price", "price_raw", "sum_volume", "order_count", "is_full", "operations", "direction")

    def __init__(self, d: dict[str, Any], divisor: float = 100.0, fallback_dir: int = 0) -> None:
        self.price_raw = as_int(d.get("price"))
        self.price = self.price_raw / divisor if divisor > 0 else self.price_raw / 100.0
        self.sum_volume = as_int(d.get("volume", d.get("sum_volume", d.get("sumVolume", 0))))
        self.order_count = as_int(d.get("order_count", d.get("orderCount", 0)))
        self.is_full = bool(d.get("is_full", d.get("isFull", False)))
        self.direction = as_int(d.get("direction", fallback_dir))

        raw_ops = d.get("operations") if isinstance(d.get("operations"), list) else []
        self.operations = [QueueOperation(op) for op in raw_ops if isinstance(op, dict)]
        if self.sum_volume == 0 and self.operations:
            self.sum_volume = sum(op.volume for op in self.operations)
        if self.order_count == 0 and self.operations:
            self.order_count = len(self.operations)


def is_order_newer(a: OrderItem, b: OrderItem) -> bool:
    if a.time != b.time:
        return a.time > b.time
    if a.order_no != 0 and b.order_no != 0 and a.order_no != b.order_no:
        return a.order_no > b.order_no
    if a.sequence != b.sequence:
        return a.sequence > b.sequence
    return False


def merge_orders(current: list[OrderItem], incoming: list[OrderItem]) -> list[OrderItem]:
    if not incoming:
        return current

    # 1. 首帧初始化：服务端下发为升序 [最早...最新]，直接反转为界面倒序 [最新...最早]
    if not current:
        return list(reversed(incoming))

    oldest_in_current = current[-1]
    newest_in_incoming = incoming[-1]

    # 2. 历史翻页检测：当接收到的整个批次均早于当前列表最早记录时，判定为翻页加载更早历史，追加到尾部
    if is_order_newer(oldest_in_current, newest_in_incoming):
        seen_hist = {(it.order_no, it.time, it.sequence, it.status) for it in current}
        rev_hist = [
            it for it in reversed(incoming)
            if (it.order_no, it.time, it.sequence, it.status) not in seen_hist
        ]
        return current + rev_hist

    # 3. 实时增量推送：彻底去除任何拦截与过滤，服务端推来的每一笔委托变动/成交事件均全量推到表头
    rev_incoming = list(reversed(incoming))
    return rev_incoming + current


def is_trade_newer(a: TradeItem, b: TradeItem) -> bool:
    if a.time != b.time:
        return a.time > b.time
    if a.trade_no != 0 and b.trade_no != 0 and a.trade_no != b.trade_no:
        return a.trade_no > b.trade_no
    if a.sequence != b.sequence:
        return a.sequence > b.sequence
    return False


def merge_trades(current: list[TradeItem], incoming: list[TradeItem]) -> list[TradeItem]:
    if not incoming:
        return current
    seen = {item.key() for item in current}
    new_items = [item for item in incoming if item.key() not in seen]
    if not new_items:
        return current

    rev_new = list(reversed(new_items))
    if not current:
        return rev_new

    if is_trade_newer(rev_new[-1], current[0]):
        return rev_new + current
    elif is_trade_newer(current[-1], rev_new[0]):
        return current + rev_new

    combined = rev_new + current
    combined.sort(key=lambda x: (x.time, x.trade_no, x.sequence), reverse=True)
    return combined


def merge_main_trades(current: list[MainTradeItem], incoming: list[MainTradeItem]) -> list[MainTradeItem]:
    if not incoming:
        return current
    seen = {item.key() for item in current}
    new_items = [item for item in incoming if item.key() not in seen]
    if not new_items:
        return current

    new_items.sort(key=lambda x: (x.time, x.trade_no), reverse=True)
    if not current:
        return new_items

    if (new_items[-1].time, new_items[-1].trade_no) > (current[0].time, current[0].trade_no):
        return new_items + current
    elif (current[-1].time, current[-1].trade_no) > (new_items[0].time, new_items[0].trade_no):
        return current + new_items

    combined = new_items + current
    combined.sort(key=lambda x: (x.time, x.trade_no), reverse=True)
    return combined


def merge_queue_levels(
    existing: list[QueuePriceLevel],
    updates: list[QueuePriceLevel],
    is_buy: bool,
) -> list[QueuePriceLevel]:
    """合并全景队列的价位变动 (支持快照覆盖与增量更新)。"""
    by_price: dict[int, QueuePriceLevel] = {lvl.price_raw: lvl for lvl in existing}

    for upd in updates:
        raw_price = upd.price_raw
        if upd.is_full:
            # 全量快照直接替换
            upd.operations = [op for op in upd.operations if op.volume > 0]
            if upd.sum_volume > 0 or upd.operations:
                by_price[raw_price] = upd
            else:
                by_price.pop(raw_price, None)
            continue

        prev = by_price.get(raw_price)
        if prev is not None and not upd.operations and (upd.sum_volume == 0 or upd.order_count == 0):
            by_price.pop(raw_price, None)
            continue

        # 增量队列明细合并
        if prev is not None:
            op_map = {op.order_no: op for op in prev.operations if op.order_no}
            for op in upd.operations:
                if op.status in (1, 3) or op.volume == 0:
                    op_map.pop(op.order_no, None)
                else:
                    op_map[op.order_no] = op
            prev.operations = [op for op in op_map.values() if op.volume > 0]
            if upd.sum_volume > 0:
                prev.sum_volume = upd.sum_volume
            else:
                prev.sum_volume = sum(op.volume for op in prev.operations)
            if upd.order_count > 0:
                prev.order_count = upd.order_count
            else:
                prev.order_count = len(prev.operations)

            if prev.sum_volume == 0 and not prev.operations:
                by_price.pop(raw_price, None)
        else:
            upd.operations = [op for op in upd.operations if op.volume > 0]
            if upd.sum_volume > 0 or upd.operations:
                by_price[raw_price] = upd

    levels = list(by_price.values())
    # 买方价格降序 (买1在最顶层)，卖方价格升序 (卖1在最底层，渲染时倒序)
    levels.sort(key=lambda lvl: lvl.price_raw, reverse=is_buy)
    return levels


# ── 自定义高性能虚拟画布表格 (VirtualCanvasTable) ─────────────────────────────────

class TableColumnDef:
    __slots__ = ("title", "base_w", "min_w", "align")

    def __init__(self, title: str, base_w: int, min_w: int = 40, align: str = "center") -> None:
        self.title = title
        self.base_w = base_w
        self.min_w = min_w
        self.align = align  # "center", "left", "right"


class VirtualCanvasTable(tk.Frame):
    """高性能自绘制虚拟表格：仅绘制当前视口可见行，秒级处理数万条实时流水。"""

    # 类级别记录当前鼠标悬停或最后激活的虚拟表格实例
    active_table: VirtualCanvasTable | None = None

    def __init__(
        self,
        parent: tk.Widget,
        columns: list[TableColumnDef],
        empty_text: str = "等待数据...",
        watermark_text: str = "d203\ndata interface",
        row_height: int = 20,
        header_height: int = 22,
        frozen_columns: int = 0,
        enable_h_scroll: bool = False,
        show_h_scrollbar: bool = True,
        on_reach_bottom: Callable[[], None] | None = None,
        on_row_clicked: Callable[[int], None] | None = None,
        on_scroll_x: Callable[[int], None] | None = None,
        bg: str = BG,
    ) -> None:
        super().__init__(parent, bg=bg)
        self.columns = columns
        self.empty_text = empty_text
        self.watermark_text = watermark_text
        self.row_height = row_height
        self.header_height = header_height
        self.frozen_columns = frozen_columns
        self.enable_h_scroll = enable_h_scroll
        self.show_h_scrollbar = show_h_scrollbar
        self.on_reach_bottom = on_reach_bottom
        self.on_row_clicked = on_row_clicked
        self.on_scroll_x = on_scroll_x
        self.bg = bg

        self.total_rows = 0
        self.selected_index = -1
        self.col_widths: list[int] = [c.base_w for c in columns]
        self.draw_row_callback: Callable[[tk.Canvas, int, int, int, list[int], bool, int], None] | None = None

        self.scroll_y_row: int = 0
        self._last_bottom_reach_time: float = 0.0
        self.scroll_x_offset = 0
        self.max_scroll_x = 0

        # 鼠标拖拽平移状态
        self._drag_start_x: int | None = None
        self._drag_start_y: int | None = None
        self._drag_start_scroll_x = 0
        self._is_dragging = False

        self._build_widgets()

    def _build_widgets(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # 1. 表头画布
        self.header_canvas = tk.Canvas(
            self,
            height=self.header_height,
            bg=TOP,
            highlightthickness=0,
            bd=0,
        )
        self.header_canvas.grid(row=0, column=0, sticky="ew")

        # 2. 数据体画布与垂直滚动条 (开启 takefocus 以接收键盘导航事件)
        self.body_canvas = tk.Canvas(
            self,
            bg=self.bg,
            highlightthickness=0,
            bd=0,
            takefocus=True,
        )
        self.body_canvas.grid(row=1, column=0, sticky="nsew")

        self.v_scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self._on_v_scrollbar,
        )
        self.v_scrollbar.grid(row=1, column=1, sticky="ns")

        # 3. 水平滚动条 (仅在 enable_h_scroll 且超宽时动态 grid 到 row=2)
        self.h_scrollbar = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self._on_h_scrollbar,
        )

        # 绑定事件
        self._bind_events()

    def _bind_events(self) -> None:
        # 数据区事件
        self.body_canvas.bind("<Configure>", self._on_configure)
        self.body_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.body_canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.body_canvas.bind("<Button-4>", lambda _e: self._scroll_units(-3))
        self.body_canvas.bind("<Button-5>", lambda _e: self._scroll_units(3))
        self.body_canvas.bind("<Shift-Button-4>", lambda _e: self.scroll_by_x(-50))
        self.body_canvas.bind("<Shift-Button-5>", lambda _e: self.scroll_by_x(50))

        # 键盘滚动与导航支持 (PageUp / PageDown / 上下光标 / Home / End / 左右平移)
        self.body_canvas.bind("<Prior>", self._on_page_up)
        self.body_canvas.bind("<Next>", self._on_page_down)
        self.body_canvas.bind("<Up>", self._on_key_up)
        self.body_canvas.bind("<Down>", self._on_key_down)
        self.body_canvas.bind("<Home>", self._on_key_home)
        self.body_canvas.bind("<End>", self._on_key_end)
        self.body_canvas.bind("<Left>", self._on_key_left)
        self.body_canvas.bind("<Right>", self._on_key_right)

        # 鼠标进入时记录为活动表格，若未在输入框打字则自动获焦
        self.body_canvas.bind("<Enter>", self._on_mouse_enter)
        self.header_canvas.bind("<Enter>", self._on_mouse_enter)

        # 鼠标左键点击与横向拖动 (带位移阈值，区分点击与平移)
        self.body_canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.body_canvas.bind("<B1-Motion>", self._on_mouse_motion)
        self.body_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # 鼠标中键 / 右键平移拖动
        self.body_canvas.bind("<ButtonPress-2>", self._on_pan_down)
        self.body_canvas.bind("<B2-Motion>", self._on_pan_motion)
        self.body_canvas.bind("<ButtonRelease-2>", self._on_pan_up)
        self.body_canvas.bind("<ButtonPress-3>", self._on_pan_down)
        self.body_canvas.bind("<B3-Motion>", self._on_pan_motion)
        self.body_canvas.bind("<ButtonRelease-3>", self._on_pan_up)

        # 表头区事件 (同样支持横向拖拽与水平滚轮)
        self.header_canvas.bind("<Configure>", lambda _e: self._render_header())
        self.header_canvas.bind("<MouseWheel>", self._on_shift_mousewheel)
        self.header_canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.header_canvas.bind("<Shift-Button-4>", lambda _e: self.scroll_by_x(-50))
        self.header_canvas.bind("<Shift-Button-5>", lambda _e: self.scroll_by_x(50))

        self.header_canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.header_canvas.bind("<B1-Motion>", self._on_mouse_motion)
        self.header_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.header_canvas.bind("<ButtonPress-2>", self._on_pan_down)
        self.header_canvas.bind("<B2-Motion>", self._on_pan_motion)
        self.header_canvas.bind("<ButtonRelease-2>", self._on_pan_up)
        self.header_canvas.bind("<ButtonPress-3>", self._on_pan_down)
        self.header_canvas.bind("<B3-Motion>", self._on_pan_motion)
        self.header_canvas.bind("<ButtonRelease-3>", self._on_pan_up)

    def set_columns(self, columns: list[TableColumnDef]) -> None:
        self.columns = columns
        self.col_widths = [c.base_w for c in columns]
        self._recompute_widths()
        self._render_header()
        self.repaint()

    def set_total_rows(self, total: int) -> None:
        self.total_rows = total
        if total <= 0:
            self.scroll_y_row = 0
            self.selected_index = -1
        else:
            client_h = max(1, self.body_canvas.winfo_height())
            visible_rows = client_h // self.row_height
            max_scroll = max(0, total - visible_rows)
            if self.scroll_y_row > max_scroll:
                self.scroll_y_row = max_scroll
            if self.selected_index >= total:
                self.selected_index = total - 1
        self._update_scrollbar()
        self.repaint()

    def _trigger_reach_bottom(self) -> None:
        if not self.on_reach_bottom or self.total_rows <= 0:
            return
        now = time.time()
        if now - self._last_bottom_reach_time < 0.5:
            return
        self._last_bottom_reach_time = now
        self.on_reach_bottom()

    def set_selected_index(self, index: int) -> None:
        self.selected_index = index
        self.repaint()

    def _recompute_widths(self) -> None:
        avail_w = max(100, self.body_canvas.winfo_width())
        total_base = sum(c.base_w for c in self.columns)
        total_min = sum(c.min_w for c in self.columns)
        if total_base == 0:
            return

        frozen_w = sum(self.columns[i].base_w for i in range(min(self.frozen_columns, len(self.columns))))

        if not self.enable_h_scroll:
            self.scroll_x_offset = 0
            self.max_scroll_x = 0
            if avail_w >= total_base:
                extra = avail_w - total_base
                expandables = [i for i, c in enumerate(self.columns) if c.base_w >= 50]
                if not expandables:
                    expandables = list(range(len(self.columns)))
                per_col = extra // len(expandables)
                rem = extra % len(expandables)
                self.col_widths = [c.base_w for c in self.columns]
                for idx in expandables:
                    self.col_widths[idx] += per_col
                self.col_widths[expandables[-1]] += rem
            elif avail_w <= total_min:
                self.col_widths = [c.min_w for c in self.columns]
            else:
                # 响应式平滑缩放，介于 min_w 与 base_w 之间，保证所有列始终 100% 完整显示
                ratio = (avail_w - total_min) / float(total_base - total_min)
                used = 0
                self.col_widths = []
                for c in self.columns:
                    w = int(c.min_w + (c.base_w - c.min_w) * ratio)
                    self.col_widths.append(w)
                    used += w
                if self.col_widths:
                    self.col_widths[-1] += (avail_w - used)
        else:
            # 开启横向滚动模式
            if avail_w >= total_base:
                extra = avail_w - total_base
                expandables = [i for i, c in enumerate(self.columns) if c.base_w >= 50]
                if not expandables:
                    expandables = list(range(len(self.columns)))
                per_col = extra // len(expandables)
                rem = extra % len(expandables)
                self.col_widths = [c.base_w for c in self.columns]
                for idx in expandables:
                    self.col_widths[idx] += per_col
                self.col_widths[expandables[-1]] += rem
                self.scroll_x_offset = 0
                self.max_scroll_x = 0
            else:
                # 列超出视口，保持 base_w 宽度并开启平移
                self.col_widths = [c.base_w for c in self.columns]
                scrollable_w = total_base - frozen_w
                scrollable_visible_w = max(1, avail_w - frozen_w)
                self.max_scroll_x = max(0, scrollable_w - scrollable_visible_w)
                self.scroll_x_offset = max(0, min(self.scroll_x_offset, self.max_scroll_x))

        self._update_h_scrollbar()

    def scroll_to_x(self, x: int) -> None:
        if not self.enable_h_scroll:
            return
        new_x = max(0, min(self.max_scroll_x, x))
        if new_x != self.scroll_x_offset:
            self.scroll_x_offset = new_x
            self._update_h_scrollbar()
            self._render_header()
            self.repaint()
            if self.on_scroll_x:
                self.on_scroll_x(new_x)

    def scroll_by_x(self, delta: int) -> None:
        self.scroll_to_x(self.scroll_x_offset + delta)

    def _on_h_scrollbar(self, action: str, *args: Any) -> None:
        if not self.enable_h_scroll or self.max_scroll_x <= 0:
            return
        avail_w = max(100, self.body_canvas.winfo_width())
        frozen_w = sum(self.col_widths[:self.frozen_columns]) if self.frozen_columns > 0 else 0
        scrollable_visible_w = max(1, avail_w - frozen_w)
        scrollable_w = max(1, sum(self.col_widths[self.frozen_columns:]))

        if action == "moveto" and args:
            frac = float(args[0])
            target = int(frac * scrollable_w)
            self.scroll_to_x(target)
        elif action == "scroll" and len(args) >= 2:
            count = int(args[0])
            unit = args[1]
            if unit == "pages":
                step = max(50, scrollable_visible_w)
            else:
                step = 40
            self.scroll_by_x(count * step)

    def _update_h_scrollbar(self) -> None:
        if not self.enable_h_scroll or not self.show_h_scrollbar or self.max_scroll_x <= 0:
            self.h_scrollbar.grid_remove()
            return
        self.h_scrollbar.grid(row=2, column=0, sticky="ew")
        avail_w = max(100, self.body_canvas.winfo_width())
        frozen_w = sum(self.col_widths[:self.frozen_columns]) if self.frozen_columns > 0 else 0
        scrollable_visible_w = max(1, avail_w - frozen_w)
        scrollable_w = max(1, sum(self.col_widths[self.frozen_columns:]))

        first = self.scroll_x_offset / float(scrollable_w)
        last = min(1.0, (self.scroll_x_offset + scrollable_visible_w) / float(scrollable_w))
        self.h_scrollbar.set(first, last)

    def _on_mouse_down(self, event: tk.Event) -> None:
        VirtualCanvasTable.active_table = self
        try:
            self.body_canvas.focus_set()
        except Exception:
            pass
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_start_scroll_x = self.scroll_x_offset
        self._is_dragging = False

    def _on_mouse_motion(self, event: tk.Event) -> None:
        if self._drag_start_x is None:
            return
        dx = event.x_root - self._drag_start_x
        if not self._is_dragging:
            if self.enable_h_scroll and self.max_scroll_x > 0 and abs(dx) >= 3:
                self._is_dragging = True
                try:
                    self.body_canvas.configure(cursor="sb_h_double_arrow")
                    self.header_canvas.configure(cursor="sb_h_double_arrow")
                except Exception:
                    pass
        if self._is_dragging and self.enable_h_scroll and self.max_scroll_x > 0:
            target_x = self._drag_start_scroll_x - dx
            self.scroll_to_x(target_x)

    def _on_mouse_up(self, event: tk.Event) -> None:
        was_dragging = self._is_dragging
        self._drag_start_x = None
        self._drag_start_y = None
        self._is_dragging = False
        try:
            self.body_canvas.configure(cursor="")
            self.header_canvas.configure(cursor="")
        except Exception:
            pass

        if not was_dragging and event.widget == self.body_canvas:
            self._on_click(event)

    def _on_pan_down(self, event: tk.Event) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_scroll_x = self.scroll_x_offset
        self._is_dragging = True
        try:
            self.body_canvas.configure(cursor="fleur")
            self.header_canvas.configure(cursor="fleur")
        except Exception:
            pass

    def _on_pan_motion(self, event: tk.Event) -> None:
        if self._drag_start_x is None:
            return
        if self.enable_h_scroll and self.max_scroll_x > 0:
            dx = event.x_root - self._drag_start_x
            self.scroll_to_x(self._drag_start_scroll_x - dx)

    def _on_pan_up(self, _event: tk.Event) -> None:
        self._drag_start_x = None
        self._is_dragging = False
        try:
            self.body_canvas.configure(cursor="")
            self.header_canvas.configure(cursor="")
        except Exception:
            pass

    def _on_configure(self, _event: tk.Event) -> None:
        client_h = max(1, self.body_canvas.winfo_height())
        visible_rows = client_h // self.row_height
        max_scroll = max(0, self.total_rows - visible_rows)
        if self.scroll_y_row > max_scroll:
            self.scroll_y_row = max_scroll
        self._recompute_widths()
        self._update_scrollbar()
        self._render_header()
        self.repaint()

    def _on_mousewheel(self, event: tk.Event) -> None:
        state = getattr(event, "state", 0)
        # Windows / X11 Shift 键状态
        if (state & 0x0001) and self.enable_h_scroll and self.max_scroll_x > 0:
            delta = -1 * (as_int(getattr(event, "delta", 0)) // 120)
            if delta == 0:
                delta = -1 if getattr(event, "num", 0) == 4 else 1
            self.scroll_by_x(delta * 50)
            return

        delta = -1 * (as_int(getattr(event, "delta", 0)) // 120)
        if delta == 0:
            delta = -1 if getattr(event, "num", 0) == 4 else 1
        self._scroll_units(delta * 3)

    def _on_shift_mousewheel(self, event: tk.Event) -> None:
        if not self.enable_h_scroll or self.max_scroll_x <= 0:
            return
        delta = -1 * (as_int(getattr(event, "delta", 0)) // 120)
        if delta == 0:
            delta = -1 if getattr(event, "num", 0) == 4 else 1
        self.scroll_by_x(delta * 50)

    def _scroll_units(self, units: int) -> None:
        if self.total_rows <= 0:
            return
        client_h = max(1, self.body_canvas.winfo_height())
        visible_rows = client_h // self.row_height
        max_scroll = max(0, self.total_rows - visible_rows)

        if max_scroll <= 0:
            if units > 0:
                self._trigger_reach_bottom()
            return

        was_at_bottom = (self.scroll_y_row >= max_scroll)
        new_row = max(0, min(max_scroll, self.scroll_y_row + units))

        if new_row != self.scroll_y_row:
            self.scroll_y_row = new_row
            self._update_scrollbar()
            self.repaint()

        # 底部停顿感设计：
        # 1. 首次滑到底部，滚动精准停在最后一屏 (new_row == max_scroll)，有清晰的触底视觉停顿；
        # 2. 仅当已处于底部 (was_at_bottom) 且用户再次尝试向下滚动 (units > 0)，触发拉取更多历史；
        # 3. 500ms 防抖节流，避免高频滚轮连续请求。
        if units > 0 and was_at_bottom:
            self._trigger_reach_bottom()

    def _visible_rows_count(self) -> int:
        client_h = max(1, self.body_canvas.winfo_height())
        return max(1, client_h // self.row_height)

    def _on_mouse_enter(self, _event: tk.Event) -> None:
        VirtualCanvasTable.active_table = self
        try:
            cur_focus = self.focus_get()
            if not isinstance(cur_focus, (tk.Entry, ttk.Entry, tk.Text)):
                self.body_canvas.focus_set()
        except Exception:
            pass

    def _on_page_up(self, _event: tk.Event | None = None) -> str:
        vis = self._visible_rows_count()
        step = max(1, vis - 1)
        self._scroll_units(-step)
        return "break"

    def _on_page_down(self, _event: tk.Event | None = None) -> str:
        vis = self._visible_rows_count()
        step = max(1, vis - 1)
        self._scroll_units(step)
        return "break"

    def _on_key_up(self, _event: tk.Event | None = None) -> str:
        if self.selected_index > 0:
            self.selected_index -= 1
            if self.selected_index < self.scroll_y_row:
                self.scroll_y_row = self.selected_index
                self._update_scrollbar()
            self.repaint()
            if self.on_row_clicked:
                self.on_row_clicked(self.selected_index)
        else:
            self._scroll_units(-1)
        return "break"

    def _on_key_down(self, _event: tk.Event | None = None) -> str:
        vis = self._visible_rows_count()
        if 0 <= self.selected_index < self.total_rows - 1:
            self.selected_index += 1
            if self.selected_index >= self.scroll_y_row + vis:
                self.scroll_y_row = self.selected_index - vis + 1
                self._update_scrollbar()
            self.repaint()
            if self.on_row_clicked:
                self.on_row_clicked(self.selected_index)
        else:
            self._scroll_units(1)
        return "break"

    def _on_key_home(self, _event: tk.Event | None = None) -> str:
        if self.total_rows > 0:
            self.scroll_y_row = 0
            self._update_scrollbar()
            self.repaint()
        return "break"

    def _on_key_end(self, _event: tk.Event | None = None) -> str:
        if self.total_rows > 0:
            vis = self._visible_rows_count()
            max_scroll = max(0, self.total_rows - vis)
            self.scroll_y_row = max_scroll
            self._update_scrollbar()
            self.repaint()
        return "break"

    def _on_key_left(self, _event: tk.Event | None = None) -> str:
        if self.enable_h_scroll and self.max_scroll_x > 0:
            self.scroll_by_x(-50)
            return "break"
        return ""

    def _on_key_right(self, _event: tk.Event | None = None) -> str:
        if self.enable_h_scroll and self.max_scroll_x > 0:
            self.scroll_by_x(50)
            return "break"
        return ""

    def _on_v_scrollbar(self, action: str, *args: Any) -> None:
        if self.total_rows <= 0:
            return
        client_h = max(1, self.body_canvas.winfo_height())
        visible_rows = client_h // self.row_height
        max_scroll = max(0, self.total_rows - visible_rows)

        if action == "moveto" and args:
            if max_scroll <= 0:
                return
            was_at_bottom = (self.scroll_y_row >= max_scroll)
            frac = float(args[0])
            target_row = int(round(frac * self.total_rows))
            target_row = max(0, min(max_scroll, target_row))
            if target_row != self.scroll_y_row:
                self.scroll_y_row = target_row
                self._update_scrollbar()
                self.repaint()
            if target_row >= max_scroll and was_at_bottom:
                self._trigger_reach_bottom()
        elif action == "scroll" and len(args) >= 2:
            count = int(args[0])
            unit = args[1]
            if unit == "pages":
                self._scroll_units(count * max(1, visible_rows))
            else:
                self._scroll_units(count * 3)

    def _update_scrollbar(self) -> None:
        client_h = max(1, self.body_canvas.winfo_height())
        visible_rows = client_h / float(self.row_height)
        if self.total_rows <= visible_rows or self.total_rows <= 0:
            self.v_scrollbar.set(0.0, 1.0)
        else:
            first = self.scroll_y_row / float(self.total_rows)
            last = min(1.0, (self.scroll_y_row + visible_rows) / float(self.total_rows))
            self.v_scrollbar.set(first, last)

    def _on_click(self, event: tk.Event) -> None:
        VirtualCanvasTable.active_table = self
        try:
            self.body_canvas.focus_set()
        except Exception:
            pass
        click_y = event.y
        row_idx = self.scroll_y_row + (click_y // self.row_height)
        if 0 <= row_idx < self.total_rows:
            self.selected_index = row_idx
            self.repaint()
            if self.on_row_clicked:
                self.on_row_clicked(row_idx)

    def _render_header(self) -> None:
        canvas = self.header_canvas
        canvas.delete("all")
        width = max(100, canvas.winfo_width())
        canvas.create_rectangle(0, 0, width, self.header_height, fill=TOP, outline="")

        frozen_w = sum(self.col_widths[:self.frozen_columns]) if self.frozen_columns > 0 else 0

        # 滚动列表头
        cur_x = frozen_w - self.scroll_x_offset
        for i in range(self.frozen_columns, len(self.columns)):
            col = self.columns[i]
            w = self.col_widths[i]
            if cur_x + w > frozen_w and cur_x < width:
                self._draw_header_cell(canvas, col.title, cur_x, w, col.align)
            cur_x += w

        # 冻结列覆盖在最上层
        if self.frozen_columns > 0:
            cur_x = 0
            for i in range(self.frozen_columns):
                col = self.columns[i]
                w = self.col_widths[i]
                canvas.create_rectangle(cur_x, 0, cur_x + w, self.header_height, fill=TOP, outline="")
                self._draw_header_cell(canvas, col.title, cur_x, w, col.align)
                cur_x += w
            canvas.create_line(frozen_w, 0, frozen_w, self.header_height, fill=BORDER_LIGHT, width=1)

        canvas.create_line(0, self.header_height - 1, width, self.header_height - 1, fill=BORDER, width=1)

    def _draw_header_cell(self, canvas: tk.Canvas, title: str, x: int, width: int, align: str) -> None:
        if align == "center":
            tx = x + width // 2
            anchor = "center"
        elif align == "right":
            tx = x + width - 6
            anchor = "e"
        else:
            tx = x + 6
            anchor = "w"
        canvas.create_text(
            tx, self.header_height // 2,
            text=title, fill=MUTED, font=FONT_TINY, anchor=anchor
        )

    def repaint(self) -> None:
        canvas = self.body_canvas
        canvas.delete("all")
        client_w = max(100, canvas.winfo_width())
        client_h = max(100, canvas.winfo_height())

        if self.total_rows == 0:
            # 水印与等待提示
            canvas.create_text(
                client_w // 2, client_h // 2 - 12,
                text=self.watermark_text, fill="#131c2c",
                font=FONT_WATERMARK, justify="center"
            )
            canvas.create_text(
                client_w // 2, client_h // 2 + 18,
                text=self.empty_text, fill=DIM,
                font=FONT_SUBTITLE
            )
            return

        visible_count = (client_h // self.row_height) + 2
        start_row = self.scroll_y_row
        end_row = min(self.total_rows, start_row + visible_count)

        if not self.draw_row_callback:
            return

        for row_idx in range(start_row, end_row):
            y = (row_idx - start_row) * self.row_height
            is_selected = (row_idx == self.selected_index)
            self.draw_row_callback(
                canvas, row_idx, y, client_w, self.col_widths, is_selected, self.scroll_x_offset
            )
            # 行分割线
            canvas.create_line(0, y + self.row_height - 1, client_w, y + self.row_height - 1, fill=BORDER, width=1)


# ── 后台 WebSocket 客户端封装 (D203Client) ──────────────────────────────────────

class D203Client:
    """管理与本地 data_interface 的 WebSocket 长连接与指令收发。"""

    def __init__(self, url: str, event_queue: queue.Queue[tuple[str, Any]]) -> None:
        self.url = url
        self.events = event_queue
        self.stop_event = threading.Event()
        self.send_lock = threading.Lock()
        self.ws: Any = None
        self.connected = False
        self.worker_thread: threading.Thread | None = None

        self.current_code = ""
        self.active_subs: set[str] = set()

    def connect(self, code: str) -> None:
        self.stop_event.set()
        with self.send_lock:
            ws = self.ws
            self.ws = None
            self.connected = False
            self.active_subs.clear()
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        self.current_code = code.strip().upper()
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._run, daemon=True, name="D203-WS")
        self.worker_thread.start()

    def disconnect(self) -> None:
        self.stop_event.set()
        with self.send_lock:
            ws = self.ws
            self.ws = None
            self.connected = False
            self.active_subs.clear()
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        self._emit("state", ("closed", "已断开连接"))

    def send_command(self, payload: dict[str, Any]) -> bool:
        with self.send_lock:
            if not self.ws or not self.connected:
                return False
            try:
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                self.ws.send(data)
                return True
            except Exception as e:
                self._emit("error", (500, f"发送失败: {e}"))
                return False

    def subscribe_all(self, code: str) -> None:
        """订阅 D203 全部五类核心流。"""
        self.current_code = code.strip().upper()
        self.active_subs.clear()
        cmds = [
            {"type": "entrust", "code": self.current_code, "enable": 1, "num": DEFAULT_PAGE_SIZE},
            {"type": "trade", "code": self.current_code, "enable": 1, "num": DEFAULT_PAGE_SIZE},
            {"type": "fullqueue", "code": self.current_code, "enable": 1},
            {"type": "maintrade", "code": self.current_code, "enable": 1, "num": DEFAULT_PAGE_SIZE},
        ]
        for cmd in cmds:
            if self.send_command(cmd):
                self.active_subs.add(cmd["type"])
        self._emit("state", ("subscribed", f"已订阅 {self.current_code} 实时数据"))

    def request_entrust_history(self, cursor: int) -> None:
        self.send_command({
            "type": "entrust",
            "code": self.current_code,
            "enable": 2,
            "startseq": cursor,
            "num": DEFAULT_PAGE_SIZE,
        })

    def request_trade_history(self, target_num: int) -> None:
        self.send_command({
            "type": "trade",
            "code": self.current_code,
            "enable": 1,
            "num": target_num,
        })

    def request_main_trade_history(self, target_num: int) -> None:
        self.send_command({
            "type": "maintrade",
            "code": self.current_code,
            "enable": 1,
            "num": target_num,
        })

    def _emit(self, kind: str, payload: Any) -> None:
        try:
            self.events.put_nowait((kind, payload))
        except queue.Full:
            try:
                self.events.get_nowait()
                self.events.put_nowait((kind, payload))
            except Exception:
                pass

    def _run(self) -> None:
        if websocket is None:
            self._emit("error", (404, "请先执行: python -m pip install websocket-client"))
            self._emit("state", ("closed", "缺少 websocket-client"))
            return

        self._emit("state", ("connecting", f"正在连接 {self.url} ..."))
        try:
            ws = websocket.create_connection(self.url, timeout=5)
            ws.settimeout(1.0)
            with self.send_lock:
                self.ws = ws
                self.connected = True
            self._emit("state", ("connected", "已连接"))
            self.subscribe_all(self.current_code)

            while not self.stop_event.is_set():
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw:
                    break

                try:
                    envelope = json.loads(raw)
                except Exception as exc:
                    self._emit("error", (400, f"JSON解析失败: {exc}"))
                    continue

                if isinstance(envelope, dict):
                    self._emit("raw_msg", raw)
                    self._process_envelope(envelope)

        except Exception as exc:
            if not self.stop_event.is_set():
                self._emit("error", (503, f"连接异常: {exc}"))
        finally:
            with self.send_lock:
                if self.ws:
                    try:
                        self.ws.close()
                    except Exception:
                        pass
                self.ws = None
                self.connected = False
            self._emit("state", ("closed", "已断开"))

    def _process_envelope(self, envelope: dict[str, Any]) -> None:
        items = envelope.get("list")
        if not isinstance(items, list):
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "error":
                code = as_int(item.get("code", 400))
                msg = str(item.get("message", "接口返回错误"))
                self._emit("error", (code, msg))
            else:
                self._emit("item", item)


# ── 主界面应用 (D203App) ───────────────────────────────────────────────────────

class D203App:
    def __init__(self, root: tk.Tk, url: str = DEFAULT_URL, code: str = DEFAULT_CODE) -> None:
        self.root = root
        self.url = url
        self.code = code.strip().upper()

        self.root.title("d203 · 实时盘口大屏与协议范例")
        self.root.geometry("1680x920")
        self.root.minsize(1280, 720)
        self.root.configure(bg=BG)
        if sys.platform.startswith("win"):
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass

        # 线程通信队列
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=4096)
        self.client = D203Client(self.url, self.events)

        # 状态统计
        self.msg_count = 0
        self.last_msg_count = 0
        self.last_rate_time = time.time()
        self.queue_expanded = False
        self.current_view = "dashboard"  # "dashboard" 或 "inspector"

        # 业务数据模型
        self.entrust_orders: list[OrderItem] = []
        self.entrust_stats: dict[str, int] = {}
        self.entrust_total = 0
        self.entrust_loading = False
        self.entrust_exhausted = False

        self.trade_transactions: list[TradeItem] = []
        self.trade_loading = False
        self.trade_exhausted = False
        self.trade_current_num = DEFAULT_PAGE_SIZE

        self.main_trades: list[MainTradeItem] = []
        self.main_trade_loading = False
        self.main_trade_exhausted = False
        self.main_trade_current_num = DEFAULT_PAGE_SIZE

        self.full_queue_buys: list[QueuePriceLevel] = []
        self.full_queue_sells: list[QueuePriceLevel] = []
        self.full_queue_op_count = 0

        self.log_items: list[dict[str, Any]] = []

        # 脏标记刷新机制
        self.dirty_views: set[str] = set()

        # 构建界面
        self._build_topbar()
        self._build_main_views()

        # 启动定时轮询与刷新循环
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(20, self._poll_events)
        self.root.after(33, self._ui_refresh_loop)

        # 全局快捷键绑定 (PageUp / PageDown / Home / End)
        self.root.bind("<Prior>", self._on_global_page_up)
        self.root.bind("<Next>", self._on_global_page_down)
        self.root.bind("<Home>", self._on_global_home)
        self.root.bind("<End>", self._on_global_end)

        # 自动触发初次连接
        self.root.after(200, self.connect)

    def _get_target_table_for_key(self) -> VirtualCanvasTable | None:
        try:
            cur_focus = self.root.focus_get()
            if isinstance(cur_focus, (tk.Entry, ttk.Entry, tk.Text)):
                return None
        except Exception:
            pass
        if VirtualCanvasTable.active_table:
            return VirtualCanvasTable.active_table
        if hasattr(self, "entrust_table"):
            return self.entrust_table
        return None

    def _on_global_page_up(self, event: tk.Event) -> str:
        table = self._get_target_table_for_key()
        if table:
            return table._on_page_up(event)
        return ""

    def _on_global_page_down(self, event: tk.Event) -> str:
        table = self._get_target_table_for_key()
        if table:
            return table._on_page_down(event)
        return ""

    def _on_global_home(self, event: tk.Event) -> str:
        table = self._get_target_table_for_key()
        if table:
            return table._on_key_home(event)
        return ""

    def _on_global_end(self, event: tk.Event) -> str:
        table = self._get_target_table_for_key()
        if table:
            return table._on_key_end(event)
        return ""

    # ── 顶栏构建 ─────────────────────────────────────────────────────────────

    def _build_topbar(self) -> None:
        self.topbar = tk.Frame(self.root, bg=TOP, height=38)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        # 标题中性化品牌标识
        tk.Label(
            self.topbar, text="达塔接口  ·  d203", bg=TOP, fg=GOLD, font=FONT_MAIN_TITLE
        ).pack(side="left", padx=(10, 8))
        tk.Label(
            self.topbar, text="实时深度", bg=TOP, fg=GOLD, font=FONT_TITLE
        ).pack(side="left", padx=(0, 6))
        tk.Label(
            self.topbar, text="委托成交实时大屏", bg=TOP, fg=TEXT, font=FONT_SUBTITLE
        ).pack(side="left", padx=(0, 16))

        # 代码输入框
        tk.Label(self.topbar, text="代码:", bg=TOP, fg=MUTED, font=FONT_TINY).pack(side="left", padx=(0, 4))
        self.code_var = tk.StringVar(value=self.code)
        self.code_entry = tk.Entry(
            self.topbar, textvariable=self.code_var, width=10, bg=INPUT_BG, fg=WHITE,
            insertbackground=WHITE, relief="flat", highlightthickness=1,
            highlightbackground=BORDER_LIGHT, highlightcolor=LINK, font=FONT_MONO
        )
        self.code_entry.pack(side="left", padx=(0, 6), ipady=2)
        self.code_entry.bind("<Return>", lambda _e: self.connect())

        # 连接 / 断开按钮
        self.connect_btn = tk.Button(
            self.topbar, text="连接", command=self.connect, bg="#1a4a2e", activebackground="#2a6a3e",
            fg="#aaddaa", activeforeground=WHITE, relief="flat", bd=0, padx=12, pady=2, font=FONT_SUBTITLE
        )
        self.connect_btn.pack(side="left", padx=(0, 4))

        self.disconnect_btn = tk.Button(
            self.topbar, text="断开", command=self.disconnect, bg="#4a1a1a", activebackground="#6a2a2a",
            fg="#dd8888", activeforeground=WHITE, relief="flat", bd=0, padx=12, pady=2, font=FONT_SUBTITLE,
            state="disabled"
        )
        self.disconnect_btn.pack(side="left", padx=(0, 14))

        # 视图切换标签
        self.btn_view_dash = tk.Button(
            self.topbar, text="📊 实时大屏", command=lambda: self.switch_view("dashboard"),
            bg="#1e293b", activebackground="#334155", fg=GOLD, relief="flat", bd=0, padx=8, pady=2, font=FONT_TINY
        )
        self.btn_view_dash.pack(side="left", padx=(0, 4))

        self.btn_view_insp = tk.Button(
            self.topbar, text="🔍 报文检查", command=lambda: self.switch_view("inspector"),
            bg="#111827", activebackground="#334155", fg=MUTED, relief="flat", bd=0, padx=8, pady=2, font=FONT_TINY
        )
        self.btn_view_insp.pack(side="left", padx=(0, 16))

        # 状态提示
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = tk.Label(self.topbar, textvariable=self.status_var, bg=TOP, fg=MUTED, font=FONT_SUBTITLE)
        self.status_label.pack(side="left", padx=(0, 8))

        # 右侧统计信息
        stats_frame = tk.Frame(self.topbar, bg=TOP)
        stats_frame.pack(side="right", padx=(0, 10))

        self.subs_var = tk.StringVar(value="活动订阅: 0")
        tk.Label(stats_frame, textvariable=self.subs_var, bg=TOP, fg=LINK, font=FONT_TINY).pack(side="right", padx=(8, 0))

        self.rate_var = tk.StringVar(value="速率: 0 笔/秒")
        tk.Label(stats_frame, textvariable=self.rate_var, bg=TOP, fg=GOLD, font=FONT_TINY).pack(side="right", padx=(8, 0))

        self.msg_count_var = tk.StringVar(value="消息: 0")
        tk.Label(stats_frame, textvariable=self.msg_count_var, bg=TOP, fg=WHITE, font=FONT_TINY).pack(side="right", padx=(8, 0))

    # ── 主内容视口布局 ─────────────────────────────────────────────────────────

    def _build_main_views(self) -> None:
        self.content_container = tk.Frame(self.root, bg=BG)
        self.content_container.pack(side="top", fill="both", expand=True, padx=4, pady=4)

        # 视图 1: 实时盘口大屏 Dashboard
        self.dashboard_frame = tk.Frame(self.content_container, bg=BG)
        self.dashboard_frame.pack(side="top", fill="both", expand=True)

        # 视图 2: 协议报文检查器 Inspector
        self.inspector_frame = tk.Frame(self.content_container, bg=BG)

        self._build_dashboard_layout()
        self._build_inspector_layout()

    def _build_dashboard_layout(self) -> None:
        self.dashboard_frame.grid_rowconfigure(0, weight=1)
        self.dashboard_frame.grid_columnconfigure(0, weight=0, minsize=380)
        self.dashboard_frame.grid_columnconfigure(1, weight=1)

        # 左栏：全档深度 + 主力成交
        self.left_panel = tk.Frame(self.dashboard_frame, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        self.left_panel.grid_rowconfigure(1, weight=3)  # 全息卖盘
        self.left_panel.grid_rowconfigure(2, weight=3)  # 全息买盘
        self.left_panel.grid_rowconfigure(3, weight=2)  # 主力成交
        self.left_panel.grid_columnconfigure(0, weight=1)

        # 左栏头部与“展开千档”按钮
        queue_header = tk.Frame(self.left_panel, bg=TOP, height=28)
        queue_header.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        tk.Label(queue_header, text="全档深度", bg=TOP, fg=GOLD, font=FONT_TITLE).pack(side="left", padx=6)
        self.depth_stats_var = tk.StringVar(value="等待全档数据...")
        tk.Label(queue_header, textvariable=self.depth_stats_var, bg=TOP, fg=MUTED, font=FONT_TINY).pack(side="left", padx=4)

        self.expand_btn = tk.Button(
            queue_header, text="展开千档", command=self.toggle_queue_expanded,
            bg="#362c12", activebackground="#4e4018", fg=GOLD, activeforeground=WHITE,
            relief="flat", bd=0, padx=8, pady=1, font=FONT_TINY
        )
        self.expand_btn.pack(side="right", padx=6)

        # 全息卖盘
        self.asks_card = tk.Frame(self.left_panel, bg=PANEL_BG)
        self.asks_card.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))
        self.asks_card.grid_rowconfigure(1, weight=1)
        self.asks_card.grid_columnconfigure(0, weight=1)
        tk.Label(self.asks_card, text="全息队列 — 卖盘", bg=PANEL_BG, fg=GREEN, font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=6, pady=2)

        self.asks_table = VirtualCanvasTable(
            self.asks_card,
            columns=[
                TableColumnDef("档位", 46, 40, "center"),
                TableColumnDef("价位", 64, 56, "right"),
                TableColumnDef("总额", 76, 68, "right"),
                TableColumnDef("排队", 48, 42, "right"),
            ],
            empty_text="等待卖盘全档数据...",
            frozen_columns=4,
            enable_h_scroll=True,
        )
        self.asks_table.grid(row=1, column=0, sticky="nsew")
        self.asks_table.draw_row_callback = self._draw_ask_row

        # 全息买盘
        self.bids_card = tk.Frame(self.left_panel, bg=PANEL_BG)
        self.bids_card.grid(row=2, column=0, sticky="nsew", padx=2, pady=(0, 2))
        self.bids_card.grid_rowconfigure(1, weight=1)
        self.bids_card.grid_columnconfigure(0, weight=1)
        tk.Label(self.bids_card, text="全息队列 — 买盘", bg=PANEL_BG, fg=RED, font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=6, pady=2)

        self.bids_table = VirtualCanvasTable(
            self.bids_card,
            columns=[
                TableColumnDef("档位", 46, 40, "center"),
                TableColumnDef("价位", 64, 56, "right"),
                TableColumnDef("总额", 76, 68, "right"),
                TableColumnDef("排队", 48, 42, "right"),
            ],
            empty_text="等待买盘全档数据...",
            frozen_columns=4,
            enable_h_scroll=True,
            show_h_scrollbar=False,  # 共享卖盘底部的中间横向拉环，隐藏买盘下方多余拉环
        )
        self.bids_table.grid(row=1, column=0, sticky="nsew")
        self.bids_table.draw_row_callback = self._draw_bid_row

        # 买卖两盘全息队列横向拖动同步联动
        self._syncing_queue_scroll = False

        def _sync_asks_to_bids(offset: int) -> None:
            if not self._syncing_queue_scroll:
                self._syncing_queue_scroll = True
                self.bids_table.scroll_to_x(offset)
                self._syncing_queue_scroll = False

        def _sync_bids_to_asks(offset: int) -> None:
            if not self._syncing_queue_scroll:
                self._syncing_queue_scroll = True
                self.asks_table.scroll_to_x(offset)
                self._syncing_queue_scroll = False

        self.asks_table.on_scroll_x = _sync_asks_to_bids
        self.bids_table.on_scroll_x = _sync_bids_to_asks

        # 主力成交
        self.main_trade_card = tk.Frame(self.left_panel, bg=PANEL_BG)
        self.main_trade_card.grid(row=3, column=0, sticky="nsew", padx=2, pady=(0, 2))
        self.main_trade_card.grid_rowconfigure(1, weight=1)
        self.main_trade_card.grid_columnconfigure(0, weight=1)
        tk.Label(self.main_trade_card, text="主力成交", bg=PANEL_BG, fg=GOLD, font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=6, pady=2)

        self.main_trade_table = VirtualCanvasTable(
            self.main_trade_card,
            columns=[
                TableColumnDef("时间", 64, 58, "center"),
                TableColumnDef("成交号", 78, 68, "center"),
                TableColumnDef("成交价", 58, 52, "right"),
                TableColumnDef("成交量", 56, 50, "right"),
                TableColumnDef("成交额", 70, 62, "right"),
                TableColumnDef("主被动", 48, 42, "center"),
            ],
            empty_text="等待主力成交数据...",
            on_reach_bottom=self._request_main_trade_history,
        )
        self.main_trade_table.grid(row=1, column=0, sticky="nsew")
        self.main_trade_table.draw_row_callback = self._draw_main_trade_row

        # 右栏：逐笔委托与逐笔成交双流 (加宽逐笔成交，权重 5:8 确保全列显示)
        self.right_streams = tk.Frame(self.dashboard_frame, bg=BG)
        self.right_streams.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        self.right_streams.grid_rowconfigure(0, weight=1)
        self.right_streams.grid_columnconfigure(0, weight=5, minsize=520)  # 逐笔委托
        self.right_streams.grid_columnconfigure(1, weight=8, minsize=760)  # 逐笔成交 (加宽并优先分配空间)

        # 逐笔委托列
        self.entrust_card = tk.Frame(self.right_streams, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        self.entrust_card.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self.entrust_card.grid_rowconfigure(2, weight=1)
        self.entrust_card.grid_columnconfigure(0, weight=1)

        tk.Label(self.entrust_card, text="逐笔委托", bg=PANEL_BG, fg=WHITE, font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=6, pady=(3, 0))
        self.entrust_stats_var = tk.StringVar(value="买量: 0 | 卖量: 0 | 买单: 0 | 卖单: 0 | 买撤: 0 | 卖撤: 0 | 记录: 0笔")
        tk.Label(self.entrust_card, textvariable=self.entrust_stats_var, bg=PANEL_BG, fg=MUTED, font=FONT_TINY).grid(row=1, column=0, sticky="w", padx=6, pady=(0, 2))

        self.entrust_table = VirtualCanvasTable(
            self.entrust_card,
            columns=[
                TableColumnDef("时间", 64, 56, "center"),
                TableColumnDef("序号", 40, 34, "center"),
                TableColumnDef("委托单号", 76, 66, "center"),
                TableColumnDef("委托价", 54, 48, "right"),
                TableColumnDef("委托量", 50, 44, "right"),
                TableColumnDef("金额", 62, 54, "right"),
                TableColumnDef("方向", 38, 34, "center"),
                TableColumnDef("状态", 80, 68, "center"),
                TableColumnDef("委托档位", 52, 46, "center"),
                TableColumnDef("量档", 46, 40, "center"),
                TableColumnDef("标志", 38, 32, "center"),
            ],
            empty_text="等待逐笔委托数据...",
            on_reach_bottom=self._request_entrust_history,
        )
        self.entrust_table.grid(row=2, column=0, sticky="nsew")
        self.entrust_table.draw_row_callback = self._draw_entrust_row

        # 逐笔成交列 (加宽各列尺寸并设置紧凑 min_w，保证全列完整显示)
        self.trade_card = tk.Frame(self.right_streams, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        self.trade_card.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        self.trade_card.grid_rowconfigure(2, weight=1)
        self.trade_card.grid_columnconfigure(0, weight=1)

        tk.Label(self.trade_card, text="逐笔成交", bg=PANEL_BG, fg=WHITE, font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=6, pady=(3, 0))
        self.trade_stats_var = tk.StringVar(value="当前总记录: 0 笔 | 实时高频推送")
        tk.Label(self.trade_card, textvariable=self.trade_stats_var, bg=PANEL_BG, fg=MUTED, font=FONT_TINY).grid(row=1, column=0, sticky="w", padx=6, pady=(0, 2))

        self.trade_table = VirtualCanvasTable(
            self.trade_card,
            columns=[
                TableColumnDef("时间", 64, 56, "center"),
                TableColumnDef("序号", 40, 34, "center"),
                TableColumnDef("成交号", 74, 66, "center"),
                TableColumnDef("成交价", 54, 48, "right"),
                TableColumnDef("成交量", 52, 46, "right"),
                TableColumnDef("金额", 64, 56, "right"),
                TableColumnDef("买单号", 76, 66, "center"),
                TableColumnDef("买单量", 50, 44, "right"),
                TableColumnDef("卖单号", 76, 66, "center"),
                TableColumnDef("卖单量", 50, 44, "right"),
                TableColumnDef("主被动", 46, 40, "center"),
                TableColumnDef("量档", 46, 40, "center"),
            ],
            empty_text="等待逐笔成交数据...",
            on_reach_bottom=self._request_trade_history,
        )
        self.trade_table.grid(row=2, column=0, sticky="nsew")
        self.trade_table.draw_row_callback = self._draw_trade_row

    def _build_inspector_layout(self) -> None:
        self.inspector_frame.grid_rowconfigure(1, weight=1)
        self.inspector_frame.grid_columnconfigure(0, weight=1)
        self.inspector_frame.grid_columnconfigure(1, weight=1)

        # 顶栏控制
        insp_bar = tk.Frame(self.inspector_frame, bg=TOP, height=30)
        insp_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        tk.Label(insp_bar, text="D203 WebSocket 协议报文检查器 (L2 JSON Inspector)", bg=TOP, fg=GOLD, font=FONT_TITLE).pack(side="left", padx=8)

        tk.Button(
            insp_bar, text="清空日志", command=self._clear_logs,
            bg="#2d3748", activebackground="#4a5568", fg=WHITE, relief="flat", bd=0, padx=8, pady=1, font=FONT_TINY
        ).pack(side="right", padx=6)

        tk.Button(
            insp_bar, text="复制当前JSON", command=self._copy_json,
            bg="#2d3748", activebackground="#4a5568", fg=GOLD, relief="flat", bd=0, padx=8, pady=1, font=FONT_TINY
        ).pack(side="right", padx=6)

        # 左侧日志列表
        insp_left = tk.Frame(self.inspector_frame, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        insp_left.grid(row=1, column=0, sticky="nsew", padx=(0, 2))
        insp_left.grid_rowconfigure(0, weight=1)
        insp_left.grid_columnconfigure(0, weight=1)

        self.insp_table = VirtualCanvasTable(
            insp_left,
            columns=[
                TableColumnDef("#", 38, 30, "center"),
                TableColumnDef("时间", 75, 65, "center"),
                TableColumnDef("类型", 70, 55, "center"),
                TableColumnDef("代码", 70, 55, "center"),
                TableColumnDef("摘要内容", 260, 180, "left"),
            ],
            empty_text="等待接收协议消息...",
            on_row_clicked=self._on_insp_row_clicked,
        )
        self.insp_table.grid(row=0, column=0, sticky="nsew")
        self.insp_table.draw_row_callback = self._draw_insp_row

        # 右侧格式化 JSON 文本框
        insp_right = tk.Frame(self.inspector_frame, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        insp_right.grid(row=1, column=1, sticky="nsew", padx=(2, 0))
        insp_right.grid_rowconfigure(0, weight=1)
        insp_right.grid_columnconfigure(0, weight=1)

        self.json_text = tk.Text(
            insp_right, bg=BG, fg=TEXT, insertbackground=WHITE, relief="flat",
            font=("Consolas", 10), wrap="none", bd=0
        )
        self.json_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        json_scroll = ttk.Scrollbar(insp_right, orient="vertical", command=self.json_text.yview)
        json_scroll.grid(row=0, column=1, sticky="ns")
        self.json_text.configure(yscrollcommand=json_scroll.set)

    def switch_view(self, view: str) -> None:
        self.current_view = view
        if view == "dashboard":
            self.inspector_frame.pack_forget()
            self.dashboard_frame.pack(side="top", fill="both", expand=True)
            self.btn_view_dash.configure(bg="#1e293b", fg=GOLD)
            self.btn_view_insp.configure(bg="#111827", fg=MUTED)
        else:
            self.dashboard_frame.pack_forget()
            self.inspector_frame.pack(side="top", fill="both", expand=True)
            self.btn_view_dash.configure(bg="#111827", fg=MUTED)
            self.btn_view_insp.configure(bg="#1e293b", fg=GOLD)
            self.insp_table.repaint()

    def toggle_queue_expanded(self) -> None:
        self.queue_expanded = not self.queue_expanded
        self._last_target_ops = -1
        if self.queue_expanded:
            self.right_streams.grid_remove()
            self.dashboard_frame.grid_columnconfigure(0, weight=1, minsize=0)
            self.dashboard_frame.grid_columnconfigure(1, weight=0)
            self.expand_btn.configure(text="恢复实时布局")
        else:
            self.right_streams.grid()
            self.dashboard_frame.grid_columnconfigure(0, weight=0, minsize=380)
            self.dashboard_frame.grid_columnconfigure(1, weight=1)
            self.expand_btn.configure(text="展开千档")
            self.asks_table.scroll_to_x(0)
            self.bids_table.scroll_to_x(0)

        self.root.after_idle(self._recalculate_queue_columns)

    def _recalculate_queue_columns(self) -> None:
        # 统计两边深度最大单档排队数
        max_asks = max((len(lvl.operations) for lvl in self.full_queue_sells), default=0)
        max_bids = max((len(lvl.operations) for lvl in self.full_queue_buys), default=0)
        max_ops = max(max_asks, max_bids)

        if self.queue_expanded:
            # 展开千档模式：保证至少有充足的明细金额列 (至少 50 档) 可供横向拖拽与排队全景浏览
            target_ops = max(max_ops, 50)
            target_ops = ((target_ops + 4) // 5) * 5
        else:
            target_ops = max_ops

        # 避免无变化时频繁重建 columns 丢失或重置滚动位置
        if getattr(self, "_last_target_ops", -1) == target_ops and len(self.asks_table.columns) == 4 + target_ops:
            return
        self._last_target_ops = target_ops

        fixed_cols = [
            TableColumnDef("档位", 46, 40, "center"),
            TableColumnDef("价位", 64, 56, "right"),
            TableColumnDef("总额", 76, 68, "right"),
            TableColumnDef("排队", 48, 42, "right"),
        ]
        dyn_cols = [TableColumnDef(f"金额{i+1}", 68, 58, "right") for i in range(target_ops)]
        full_cols = fixed_cols + dyn_cols

        self.asks_table.set_columns(full_cols)
        self.bids_table.set_columns(full_cols)

    # ── 自定义单元格绘制逻辑 ───────────────────────────────────────────────────

    def _draw_cell_text(
        self, canvas: tk.Canvas, text: str, x: int, y: int, width: int,
        align: str, color: str
    ) -> None:
        if align == "center":
            tx = x + width // 2
            anchor = "center"
        elif align == "right":
            tx = x + width - 6
            anchor = "e"
        else:
            tx = x + 6
            anchor = "w"
        canvas.create_text(
            tx, y + 10,
            text=text, fill=color, font=FONT_MONO, anchor=anchor
        )

    def _draw_ask_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, scroll_x: int
    ) -> None:
        if row_idx >= len(self.full_queue_sells):
            return
        # 卖盘倒序展示：卖10在最上方，卖1在最下方
        real_idx = len(self.full_queue_sells) - 1 - row_idx
        level = self.full_queue_sells[real_idx]
        level_name = f"卖{real_idx + 1}"

        if is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.asks_table.row_height, fill=SEL_BG, outline="")

        frozen_w = sum(col_widths[:4])
        # 动态明细排队金额 (视口裁剪，超出视口不渲染以节省开销)
        cur_x = frozen_w - scroll_x
        for i in range(4, len(col_widths)):
            w = col_widths[i]
            if cur_x + w > frozen_w and cur_x < row_w:
                op_idx = i - 4
                if op_idx < len(level.operations):
                    op = level.operations[op_idx]
                    amt = int(round(level.price * op.volume))
                    color = GOLD if (amt >= 500000 or op.flags != 0) else TEXT
                    self._draw_cell_text(canvas, format_holo_amount(amt), cur_x, y, w, "right", color)
                else:
                    self._draw_cell_text(canvas, "—", cur_x, y, w, "right", DIM)
            cur_x += w

        # 冻结列 (档位, 价位, 总额, 排队)
        canvas.create_rectangle(0, y, frozen_w, y + self.asks_table.row_height, fill=SEL_BG if is_selected else PANEL_BG, outline="")
        cur_x = 0
        self._draw_cell_text(canvas, level_name, cur_x, y, col_widths[0], "center", GREEN)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, f"{level.price:.2f}", cur_x, y, col_widths[1], "right", GREEN)
        cur_x += col_widths[1]
        total_amt = int(round(level.price * level.sum_volume))
        self._draw_cell_text(canvas, format_holo_amount(total_amt), cur_x, y, col_widths[2], "right", GOLD)
        cur_x += col_widths[2]
        cnt_text = str(level.order_count if level.order_count > 0 else len(level.operations))
        self._draw_cell_text(canvas, cnt_text, cur_x, y, col_widths[3], "right", MUTED)
        # 冻结列右边缘分割线
        canvas.create_line(frozen_w, y, frozen_w, y + self.asks_table.row_height, fill=BORDER_LIGHT, width=1)

    def _draw_bid_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, scroll_x: int
    ) -> None:
        if row_idx >= len(self.full_queue_buys):
            return
        level = self.full_queue_buys[row_idx]
        level_name = f"买{row_idx + 1}"

        if is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.bids_table.row_height, fill=SEL_BG, outline="")

        frozen_w = sum(col_widths[:4])
        cur_x = frozen_w - scroll_x
        for i in range(4, len(col_widths)):
            w = col_widths[i]
            if cur_x + w > frozen_w and cur_x < row_w:
                op_idx = i - 4
                if op_idx < len(level.operations):
                    op = level.operations[op_idx]
                    amt = int(round(level.price * op.volume))
                    color = GOLD if (amt >= 500000 or op.flags != 0) else TEXT
                    self._draw_cell_text(canvas, format_holo_amount(amt), cur_x, y, w, "right", color)
                else:
                    self._draw_cell_text(canvas, "—", cur_x, y, w, "right", DIM)
            cur_x += w

        canvas.create_rectangle(0, y, frozen_w, y + self.bids_table.row_height, fill=SEL_BG if is_selected else PANEL_BG, outline="")
        cur_x = 0
        self._draw_cell_text(canvas, level_name, cur_x, y, col_widths[0], "center", RED)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, f"{level.price:.2f}", cur_x, y, col_widths[1], "right", RED)
        cur_x += col_widths[1]
        total_amt = int(round(level.price * level.sum_volume))
        self._draw_cell_text(canvas, format_holo_amount(total_amt), cur_x, y, col_widths[2], "right", GOLD)
        cur_x += col_widths[2]
        cnt_text = str(level.order_count if level.order_count > 0 else len(level.operations))
        self._draw_cell_text(canvas, cnt_text, cur_x, y, col_widths[3], "right", MUTED)
        # 冻结列右边缘分割线
        canvas.create_line(frozen_w, y, frozen_w, y + self.bids_table.row_height, fill=BORDER_LIGHT, width=1)

    def _draw_entrust_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, _scroll_x: int
    ) -> None:
        if row_idx >= len(self.entrust_orders):
            return
        row = self.entrust_orders[row_idx]
        is_cancel = row.status in (3, 4, 13, 14)

        # 撤单行暗琥珀背景与亮橙色指示边条
        if is_cancel and not is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.entrust_table.row_height, fill=CANCEL_ROW_BG, outline="")
            canvas.create_rectangle(0, y, 3, y + self.entrust_table.row_height, fill=CANCEL_ROW_BAR, outline="")
        elif is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.entrust_table.row_height, fill=SEL_BG, outline="")

        dir_text, dir_color = direction_label(row.direction)
        status_text = entrust_status_text(row.status)
        status_color = entrust_status_color(row.status)
        order_no_color = "#ebc382" if is_cancel else TEXT

        cur_x = 0
        self._draw_cell_text(canvas, format_time(row.time), cur_x, y, col_widths[0], "center", MUTED)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, str(row.sequence), cur_x, y, col_widths[1], "center", DIM)
        cur_x += col_widths[1]
        self._draw_cell_text(canvas, str(row.order_no), cur_x, y, col_widths[2], "center", order_no_color)
        cur_x += col_widths[2]
        self._draw_cell_text(canvas, f"{row.price:.2f}", cur_x, y, col_widths[3], "right", dir_color)
        cur_x += col_widths[3]
        self._draw_cell_text(canvas, str(row.volume), cur_x, y, col_widths[4], "right", TEXT)
        cur_x += col_widths[4]
        amt = int(round(row.price * row.volume))
        self._draw_cell_text(canvas, format_amount(amt), cur_x, y, col_widths[5], "right", GOLD)
        cur_x += col_widths[5]
        self._draw_cell_text(canvas, dir_text, cur_x, y, col_widths[6], "center", dir_color)
        cur_x += col_widths[6]
        self._draw_cell_text(canvas, status_text, cur_x, y, col_widths[7], "center", status_color)
        cur_x += col_widths[7]
        self._draw_cell_text(canvas, order_mmp_text(row.order_mmp), cur_x, y, col_widths[8], "center", TEXT)
        cur_x += col_widths[8]
        self._draw_cell_text(canvas, volume_code_text(row.volume_code), cur_x, y, col_widths[9], "center", MUTED)
        cur_x += col_widths[9]
        flags_text = str(row.flags) if row.flags != 0 else "—"
        self._draw_cell_text(canvas, flags_text, cur_x, y, col_widths[10], "center", DIM)

    def _draw_trade_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, _scroll_x: int
    ) -> None:
        if row_idx >= len(self.trade_transactions):
            return
        row = self.trade_transactions[row_idx]
        is_cancel = (row.price == 0 and row.volume > 0)

        if is_cancel and not is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.trade_table.row_height, fill=CANCEL_ROW_BG, outline="")
            canvas.create_rectangle(0, y, 3, y + self.trade_table.row_height, fill=CANCEL_ROW_BAR, outline="")
        elif is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.trade_table.row_height, fill=SEL_BG, outline="")

        act_text, act_color = active_function_text(row.active_function)
        vol_color = GOLD if row.volume >= 10000 else TEXT

        cur_x = 0
        self._draw_cell_text(canvas, format_time(row.time), cur_x, y, col_widths[0], "center", MUTED)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, str(row.sequence), cur_x, y, col_widths[1], "center", DIM)
        cur_x += col_widths[1]
        self._draw_cell_text(canvas, str(row.trade_no), cur_x, y, col_widths[2], "center", TEXT)
        cur_x += col_widths[2]
        self._draw_cell_text(canvas, f"{row.price:.2f}", cur_x, y, col_widths[3], "right", act_color)
        cur_x += col_widths[3]
        self._draw_cell_text(canvas, str(row.volume), cur_x, y, col_widths[4], "right", vol_color)
        cur_x += col_widths[4]
        self._draw_cell_text(canvas, format_amount(row.amount), cur_x, y, col_widths[5], "right", GOLD)
        cur_x += col_widths[5]
        self._draw_cell_text(canvas, str(row.buy_no), cur_x, y, col_widths[6], "center", RED)
        cur_x += col_widths[6]
        self._draw_cell_text(canvas, str(row.buy_volume), cur_x, y, col_widths[7], "right", RED)
        cur_x += col_widths[7]
        self._draw_cell_text(canvas, str(row.sell_no), cur_x, y, col_widths[8], "center", GREEN)
        cur_x += col_widths[8]
        self._draw_cell_text(canvas, str(row.sell_volume), cur_x, y, col_widths[9], "right", GREEN)
        cur_x += col_widths[9]
        self._draw_cell_text(canvas, act_text, cur_x, y, col_widths[10], "center", act_color)
        cur_x += col_widths[10]
        self._draw_cell_text(canvas, volume_code_text(row.volume_code), cur_x, y, col_widths[11], "center", MUTED)

    def _draw_main_trade_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, _scroll_x: int
    ) -> None:
        if row_idx >= len(self.main_trades):
            return
        row = self.main_trades[row_idx]
        if is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.main_trade_table.row_height, fill=SEL_BG, outline="")

        act_text, act_color = active_function_text(row.active_function)

        cur_x = 0
        self._draw_cell_text(canvas, format_time(row.time), cur_x, y, col_widths[0], "center", MUTED)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, str(row.trade_no), cur_x, y, col_widths[1], "center", TEXT)
        cur_x += col_widths[1]
        self._draw_cell_text(canvas, f"{row.price:.2f}", cur_x, y, col_widths[2], "right", act_color)
        cur_x += col_widths[2]
        self._draw_cell_text(canvas, str(row.volume), cur_x, y, col_widths[3], "right", TEXT)
        cur_x += col_widths[3]
        self._draw_cell_text(canvas, format_amount(row.amount), cur_x, y, col_widths[4], "right", GOLD)
        cur_x += col_widths[4]
        self._draw_cell_text(canvas, act_text, cur_x, y, col_widths[5], "center", act_color)

    def _draw_insp_row(
        self, canvas: tk.Canvas, row_idx: int, y: int, row_w: int,
        col_widths: list[int], is_selected: bool, _scroll_x: int
    ) -> None:
        if row_idx >= len(self.log_items):
            return
        item = self.log_items[row_idx]
        if is_selected:
            canvas.create_rectangle(0, y, row_w, y + self.insp_table.row_height, fill=SEL_BG, outline="")

        typ = item["type"]
        type_color = GOLD
        if typ == "error": type_color = RED
        elif typ == "trade": type_color = GREEN
        elif typ == "fullqueue": type_color = BLUE

        cur_x = 0
        self._draw_cell_text(canvas, str(item["index"]), cur_x, y, col_widths[0], "center", DIM)
        cur_x += col_widths[0]
        self._draw_cell_text(canvas, item["time_str"], cur_x, y, col_widths[1], "center", MUTED)
        cur_x += col_widths[1]
        self._draw_cell_text(canvas, typ, cur_x, y, col_widths[2], "center", type_color)
        cur_x += col_widths[2]
        self._draw_cell_text(canvas, item["code"], cur_x, y, col_widths[3], "center", TEXT)
        cur_x += col_widths[3]
        self._draw_cell_text(canvas, item["summary"], cur_x, y, col_widths[4], "left", WHITE)

    # ── 业务动作与事件处理 ─────────────────────────────────────────────────────

    def connect(self) -> None:
        new_code = self.code_var.get().strip().upper()
        if not new_code:
            new_code = DEFAULT_CODE
            self.code_var.set(new_code)
        self.code = new_code

        # 重置已有业务状态
        self.entrust_orders.clear()
        self.entrust_total = 0
        self.entrust_loading = False
        self.entrust_exhausted = False

        self.trade_transactions.clear()
        self.trade_loading = False
        self.trade_exhausted = False
        self.trade_current_num = DEFAULT_PAGE_SIZE

        self.main_trades.clear()
        self.main_trade_loading = False
        self.main_trade_exhausted = False
        self.main_trade_current_num = DEFAULT_PAGE_SIZE

        self.full_queue_buys.clear()
        self.full_queue_sells.clear()
        self._last_target_ops = -1
        self.asks_table.scroll_to_x(0)
        self.bids_table.scroll_to_x(0)

        self.asks_table.set_total_rows(0)
        self.bids_table.set_total_rows(0)
        self.main_trade_table.set_total_rows(0)
        self.entrust_table.set_total_rows(0)
        self.trade_table.set_total_rows(0)

        self.status_var.set("连接中...")
        self.status_label.configure(fg=GOLD)
        self.connect_btn.configure(state="disabled")
        self.disconnect_btn.configure(state="normal")

        self.client.connect(self.code)

    def disconnect(self) -> None:
        self.client.disconnect()
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.status_var.set("已断开")
        self.status_label.configure(fg=MUTED)
        self.subs_var.set("活动订阅: 0")
        self.rate_var.set("速率: 0 笔/秒")

    def _request_entrust_history(self) -> None:
        if self.entrust_loading or self.entrust_exhausted or not self.entrust_orders:
            return
        oldest = self.entrust_orders[-1]
        cursor = oldest.order_no if oldest.order_no > 0 else oldest.sequence
        if cursor <= 0:
            self.entrust_exhausted = True
            return

        self.entrust_loading = True
        self.client.request_entrust_history(cursor)

    def _request_trade_history(self) -> None:
        if self.trade_loading or self.trade_exhausted or not self.trade_transactions:
            return
        target = len(self.trade_transactions) + DEFAULT_PAGE_SIZE
        if target <= self.trade_current_num:
            target = self.trade_current_num + DEFAULT_PAGE_SIZE
        self.trade_current_num = target
        self.trade_loading = True
        self.client.request_trade_history(target)

    def _request_main_trade_history(self) -> None:
        if self.main_trade_loading or self.main_trade_exhausted or not self.main_trades:
            return
        target = len(self.main_trades) + DEFAULT_PAGE_SIZE
        if target <= self.main_trade_current_num:
            target = self.main_trade_current_num + DEFAULT_PAGE_SIZE
        self.main_trade_current_num = target
        self.main_trade_loading = True
        self.client.request_main_trade_history(target)

    def _poll_events(self) -> None:
        processed = 0
        while processed < 1000:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            processed += 1
            if kind == "state":
                state, msg = payload
                if state == "connected":
                    self.status_var.set("已连接，数据订阅中")
                    self.status_label.configure(fg=GREEN)
                    self.connect_btn.configure(state="disabled")
                    self.disconnect_btn.configure(state="normal")
                elif state == "connecting":
                    self.status_var.set(msg)
                    self.status_label.configure(fg=GOLD)
                    self.connect_btn.configure(state="disabled")
                    self.disconnect_btn.configure(state="normal")
                elif state == "closed":
                    self.status_var.set(msg)
                    self.status_label.configure(fg=MUTED)
                    self.connect_btn.configure(state="normal")
                    self.disconnect_btn.configure(state="disabled")
                    self.subs_var.set("活动订阅: 0")
                    self.rate_var.set("速率: 0 笔/秒")
            elif kind == "error":
                code, msg = payload
                self.status_var.set(f"错误 [{code}]: {msg}")
                self.status_label.configure(fg=RED)
                self.entrust_loading = False
                self.trade_loading = False
                self.main_trade_loading = False
                self._add_log_item("error", self.code, f"[{code}] {msg}", json.dumps({"code": code, "message": msg}))
            elif kind == "item":
                self._handle_item(payload)

        self.root.after(20, self._poll_events)

    def _handle_item(self, item: dict[str, Any]) -> None:
        self.msg_count += 1
        item_type = item.get("type")
        raw_code = str(item.get("code") or item.get("symbol") or self.code)

        # 检查是否携带内嵌 data 结构
        data = item.get("data") if isinstance(item.get("data"), dict) else item

        if item_type == "entrust":
            orders = [OrderItem(r) for r in data.get("rows", []) if isinstance(r, dict)]
            stats = data.get("statistics") if isinstance(data.get("statistics"), dict) else {}
            if stats:
                self.entrust_stats.update(stats)
            tot = as_int(data.get("total_num", data.get("totalNum", 0)))
            if tot > 0:
                self.entrust_total = tot

            prev_len = len(self.entrust_orders)
            self.entrust_orders = merge_orders(self.entrust_orders, orders)

            if self.entrust_loading:
                self.entrust_loading = False
                if len(self.entrust_orders) == prev_len or not orders:
                    self.entrust_exhausted = True

            self.dirty_views.add("entrust")
            summary = f"委托数据 {len(orders)} 笔 (现存 {len(self.entrust_orders)} 笔/总 {self.entrust_total})"
            self._add_log_item("entrust", raw_code, summary, json.dumps(item, ensure_ascii=False, indent=2))

        elif item_type == "trade":
            trades = [TradeItem(r) for r in data.get("rows", []) if isinstance(r, dict)]
            prev_len = len(self.trade_transactions)
            self.trade_transactions = merge_trades(self.trade_transactions, trades)

            if self.trade_loading:
                self.trade_loading = False
                if len(self.trade_transactions) == prev_len or not trades:
                    self.trade_exhausted = True

            self.dirty_views.add("trade")
            summary = f"成交数据 {len(trades)} 笔 (现存 {len(self.trade_transactions)} 笔)"
            self._add_log_item("trade", raw_code, summary, json.dumps(item, ensure_ascii=False, indent=2))

        elif item_type == "fullqueue":
            buys = [QueuePriceLevel(lvl, fallback_dir=0) for lvl in data.get("buy", []) if isinstance(lvl, dict)]
            sells = [QueuePriceLevel(lvl, fallback_dir=1) for lvl in data.get("sell", []) if isinstance(lvl, dict)]

            self.full_queue_buys = merge_queue_levels(self.full_queue_buys, buys, is_buy=True)
            self.full_queue_sells = merge_queue_levels(self.full_queue_sells, sells, is_buy=False)

            self.full_queue_op_count = sum(len(lvl.operations) for lvl in self.full_queue_buys) + \
                                       sum(len(lvl.operations) for lvl in self.full_queue_sells)

            self.dirty_views.add("fullqueue")
            summary = f"更新 {len(sells)}/{len(buys)} 档；当前买 {len(self.full_queue_buys)} / 卖 {len(self.full_queue_sells)} 档，共 {self.full_queue_op_count} 笔队列委托"
            self._add_log_item("fullqueue", raw_code, summary, json.dumps(item, ensure_ascii=False, indent=2))

        elif item_type == "maintrade":
            main_rows = [MainTradeItem(r) for r in data.get("rows", []) if isinstance(r, dict)]
            prev_len = len(self.main_trades)
            self.main_trades = merge_main_trades(self.main_trades, main_rows)

            if self.main_trade_loading:
                self.main_trade_loading = False
                if len(self.main_trades) == prev_len or not main_rows:
                    self.main_trade_exhausted = True

            self.dirty_views.add("maintrade")
            summary = f"主力成交 {len(main_rows)} 笔 (现存 {len(self.main_trades)} 笔)"
            self._add_log_item("maintrade", raw_code, summary, json.dumps(item, ensure_ascii=False, indent=2))

    def _add_log_item(self, typ: str, code: str, summary: str, raw_json: str) -> None:
        item = {
            "index": len(self.log_items) + 1,
            "time_str": time.strftime("%H:%M:%S"),
            "type": typ,
            "code": code,
            "summary": summary,
            "raw_json": raw_json,
        }
        self.log_items.insert(0, item)
        if len(self.log_items) > MAX_LOG_ITEMS:
            self.log_items.pop()
        self.dirty_views.add("inspector")

    def _ui_refresh_loop(self) -> None:
        # 1. 刷新速率与订阅统计
        now = time.time()
        elapsed = now - self.last_rate_time
        if elapsed >= 1.0:
            rate = (self.msg_count - self.last_msg_count) / elapsed
            self.rate_var.set(f"速率: {int(round(rate))} 笔/秒")
            self.msg_count_var.set(f"消息: {self.msg_count:,}")
            self.subs_var.set(f"活动订阅: {len(self.client.active_subs)}")
            self.last_msg_count = self.msg_count
            self.last_rate_time = now

        # 2. 按需重绘脏视图
        if "entrust" in self.dirty_views:
            buy_vol = self.entrust_stats.get("buy_volume", self.entrust_stats.get("buyVolume", 0))
            sell_vol = self.entrust_stats.get("sell_volume", self.entrust_stats.get("sellVolume", 0))
            buy_cnt = self.entrust_stats.get("buy_order_count", self.entrust_stats.get("buyOrderCount", 0))
            sell_cnt = self.entrust_stats.get("sell_order_count", self.entrust_stats.get("sellOrderCount", 0))
            buy_canc = self.entrust_stats.get("buy_cancel_count", self.entrust_stats.get("buyCancelCount", 0))
            sell_canc = self.entrust_stats.get("sell_cancel_count", self.entrust_stats.get("sellCancelCount", 0))
            self.entrust_stats_var.set(
                f"买量: {buy_vol:,} | 卖量: {sell_vol:,} | 买单: {buy_cnt} | 卖单: {sell_cnt} | "
                f"买撤: {buy_canc} | 卖撤: {sell_canc} | 现存: {len(self.entrust_orders)}笔"
            )
            self.entrust_table.set_total_rows(len(self.entrust_orders))

        if "trade" in self.dirty_views:
            self.trade_stats_var.set(f"当前总记录: {len(self.trade_transactions):,} 笔 | 实时高频推送")
            self.trade_table.set_total_rows(len(self.trade_transactions))

        if "fullqueue" in self.dirty_views:
            self.depth_stats_var.set(
                f"当前买 {len(self.full_queue_buys)} 档 / 卖 {len(self.full_queue_sells)} 档，"
                f"队列委托 {self.full_queue_op_count} 笔"
            )
            self._recalculate_queue_columns()
            self.asks_table.set_total_rows(len(self.full_queue_sells))
            self.bids_table.set_total_rows(len(self.full_queue_buys))

        if "maintrade" in self.dirty_views:
            self.main_trade_table.set_total_rows(len(self.main_trades))

        if "inspector" in self.dirty_views and self.current_view == "inspector":
            self.insp_table.set_total_rows(len(self.log_items))

        self.dirty_views.clear()
        self.root.after(33, self._ui_refresh_loop)

    def _on_insp_row_clicked(self, row_idx: int) -> None:
        if 0 <= row_idx < len(self.log_items):
            raw = self.log_items[row_idx]["raw_json"]
            self.json_text.delete("1.0", "end")
            self.json_text.insert("1.0", raw)

    def _clear_logs(self) -> None:
        self.log_items.clear()
        self.insp_table.set_total_rows(0)
        self.json_text.delete("1.0", "end")

    def _copy_json(self) -> None:
        content = self.json_text.get("1.0", "end").strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("提示", "JSON 报文已成功复制到剪贴板！")

    def _on_close(self) -> None:
        self.client.disconnect()
        self.root.destroy()


# ── 主入口 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="D203 WebSocket 实时盘口大屏客户端范例")
    parser.add_argument("--url", default=DEFAULT_URL, help="D203 服务端连接地址 (默认 ws://127.0.0.1:8080/d203)")
    parser.add_argument("--code", default=DEFAULT_CODE, help="默认股票代码 (如 SH600519)")
    args = parser.parse_args()

    root = tk.Tk()
    app = D203App(root, url=args.url, code=args.code)
    root.mainloop()


if __name__ == "__main__":
    main()
