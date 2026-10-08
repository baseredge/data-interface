# D204 WebSocket 实时行情接口开发指南

> **核心亮点**：支持全市场“3秒千档全深度盘口”与“毫秒级逐笔流式推送”，独创免长连接的“单次即时查询（`once`）”，支持多标的批量混合指令下发与纯原生 JSON 直连解析。

---

## 1. 快速接入与前置条件

D204 是专为高频量化与精准盘口分析设计的次时代 WebSocket 接口。所有指令与数据均采用 **UTF-8 纯文本 JSON** 格式传输。

### 1.1 服务连接地址

```text
ws://127.0.0.1:<ProxyPort>/d204
```

- `<ProxyPort>` 为本机 `data_interface` 的代理端口（默认为 `8080`）；
- 默认连接 URL：`ws://127.0.0.1:8080/d204`；
- 连接前须确保本地客户端处于登录状态，且通用积分（`pointsBalance`）余额大于 0；
- D204 采用按需计量模式，建立连接或下发控制指令本身不产生额外扣减，仅按实际接收的下行数据流进行积分抵扣。

---

## 2. 标的代码与格式规范

D204 统一采用 **`6位代码.小写市场后缀`** 格式，股票、基金、指数与期权合约代码风格保持一致：

| 品种类型 | 示例代码 | 说明 |
| :--- | :--- | :--- |
| 沪市主板 / 科创板 | `600519.sh`、`688981.sh` | 6 位代码加 `.sh` 后缀 |
| 深市主板 / 创业板 | `000001.sz`、`300750.sz` | 6 位代码加 `.sz` 后缀 |
| 交易所指数 | `000001.sh`（上证指数）、`399001.sz`（深证成指） | 标准代码加小写市场后缀 |
| 期权衍生品 | `90008046.sz`、`10005001.sh` | 8 位期权合约代码加后缀 |

---

## 3. 两大工作模式详析

D204 提供两种截然不同的工作模式，开发者可按策略需求自由选用：

```text
┌────────────────────────────────────────────────────────┐
│                   D204 WebSocket 接口                   │
└───────────┬────────────────────────────────┬───────────┘
            │                                │
            ▼                                ▼
┌───────────────────────┐        ┌───────────────────────┐
│  模式一：单次查询 (once) │        │  模式二：流式推送 (push)│
│  - 随查随走，无需保持订阅 │        │  - 持续极速全推       │
│  - 综合十档快照 / 期权  │        │  - 全量千档盘口       │
│  - 包含分笔成交与委托队列│        │  - 实时逐笔成交/委托   │
│  - 游标历史逐笔回溯    │        │  - 批量指令数组下发   │
└───────────────────────┘        └───────────────────────┘
```

---

### 3.1 模式一：单次查询动作 (`once`)

**适用场景**：核心股票池盘中高频轮询、开盘前资产扫描、定时抓取十档指标、盘后复盘、按游标回溯历史逐笔。随查随走，无需维护长期的订阅状态。

#### 💡 高频请求支持与连接数配置建议（量化实盘必读）

- **支不支持一直请求？**
  - **完全支持！且原生支持高频连续请求**。同一个 WebSocket 连接没有单日或总请求次数的上限，只要本地客户端保持运行且通用积分充足，程序即可 7×24 小时不间断持续轮询。
  - **请求吞吐与响应延迟**：本地客户端内部维护了高效的长连接管道与会话缓存，请求直连本机无额外握手损耗。单根连接内置 10 毫秒级的极速微观调度，单连接实测吞吐可达 **80～100 次/秒**！
  - **高频场景推荐**：极为适合盘中高速轮询监控自己的核心股票池（例如循环查询 50～100 只自选股的十档盘口与最新成交，1～2 秒即可完成全池刷新一轮）。
- **建议连接几根？**
  - **单连接流水线模式（最推荐，简单高效）**：绝大多数策略推荐仅连接 **1 根** WebSocket。保持长连接不关闭，按需依次下发 `{"action":"once", ...}`，在同一个连接内即发即收，系统开销最小。
  - **多连接并发模式（多 Worker 并行）**：如果策略标的池较大（如 300+ 只标的），或者需要多线程/多进程独立工作，建议建立 **2～4 根** 并行 WebSocket 连接（每个 Worker 线程独享 1 根）。本地服务内部会为每个连接独立分配通道并共享凭证，多连接并发可轻松突破数百次/秒的高并发吞吐。
- **最佳高频实践**：
  - 发送节奏建议：单连接发送间隔建议保持 $\ge 10\text{ms}$（或采用“收到上一笔回包后立即发送下一笔”的流水线模式）。突发密集请求服务端会自动在本地队列中有序排队处理，不会丢包或拒绝。

#### 请求格式
```json
{"action":"once","type":"snapshot","symbol":"600519.sh"}
{"action":"once","type":"trade","symbol":"600519.sh","count":50}
{"action":"once","type":"entrust","symbol":"600519.sh","count":50,"cursor":"23030429"}
{"action":"once","type":"time"}
```

| 参数 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `action` | string | 是 | 固定为 `"once"` |
| `type` | string | 是 | 查询类型：`snapshot`（综合十档快照）、`trade`（单次逐笔成交）、`entrust`（单次逐笔委托）、`time`（服务器毫秒时间） |
| `symbol` | string | 是 | 标的代码（查询 `time` 时可省略） |
| `count` | int | 否 | 逐笔记录条数（范围 1～100，默认 50 条） |
| `cursor` | string | 否 | 翻页游标字符串。首次查询省略；后续传入上一次返回的 `next_cursor` 可向更早记录翻页 |

---

#### ⭐️ 重点：`snapshot` 综合十档快照完整响应结构

单次 `snapshot` 查询不仅包含标的基础量价与指标，还直接内嵌了**买卖十档盘口 (`bids`/`asks`)**、**最新分笔成交明细 (`recent_trades`)**、**买一卖一委托排队队列 (`order_queue`)**、**加权买卖均价与总量**以及**市场宽度/期权属性**：

```json
{
  "ts": 1790061785169,
  "list": [
    {
      "action": "once",
      "type": "snapshot",
      "symbol": "600519.sh",
      "code": 0,
      "name": "贵州茅台",
      "market": "sh",
      "stock_type": "1001",
      "datetime": 20260924145958,
      "trading_status": "N",
      "currency": "CNY",
      "sector": "ASH",
      "hsgt": "1",
      "listing_date": 20010827,
      "ipo_date": 20010827,
      "last_price": 1650000,
      "prev_close": 1640000,
      "open_price": 1645000,
      "high_price": 1668000,
      "low_price": 1641000,
      "limit_up": 1804000,
      "limit_down": 1476000,
      "change_rate": 0.61,
      "amplitude": 1.65,
      "volume": 3123935,
      "now_volume": 120,
      "amount": 5154492750,
      "vwap": 1650000,
      "turnover_rate": 0.25,
      "volume_ratio": 1.27,
      "trade_count": 48920,
      "total_shares": 1256197800,
      "circulating_shares": 1256197800,
      "pe": 28.54,
      "eps": 57.81,
      "roe": 32.15,
      "weibi": -12.45,
      "weicha": -1580,
      "total_bid_qty": 352000,
      "total_ask_qty": 452000,
      "bid1_price": 1649900,
      "bid1_qty": 2400,
      "ask1_price": 1650000,
      "ask1_qty": 3980,
      "weighted_avg_bid_price": 1645200,
      "weighted_avg_ask_price": 1654800,
      "weighted_avg_bid_qty": 352000,
      "weighted_avg_ask_qty": 452000,
      "ma5": 1642000,
      "ma10": 1638000,
      "ma20": 1625000,
      "volume_ma5": 3200000,
      "volume_ma10": 3100000,
      "volume_ma20": 2980000,
      "bids": [
        {"level": 1, "price": 1649900, "volume": 2400, "order_count": 8},
        {"level": 2, "price": 1649800, "volume": 5800, "order_count": 15},
        {"level": 3, "price": 1649500, "volume": 12000, "order_count": 22}
      ],
      "asks": [
        {"level": 1, "price": 1650000, "volume": 3980, "order_count": 11},
        {"level": 2, "price": 1650200, "volume": 7200, "order_count": 18},
        {"level": 3, "price": 1650500, "volume": 15000, "order_count": 31}
      ],
      "recent_trades": [
        {
          "trade_id": 982145,
          "time": 145958120,
          "price": 1650000,
          "volume": 200,
          "side": "B"
        },
        {
          "trade_id": 982146,
          "time": 145958250,
          "price": 1649900,
          "volume": 100,
          "side": "S"
        }
      ],
      "order_queue": {
        "bid1": [500, 200, 1000, 300, 400],
        "ask1": [800, 1200, 1500, 480]
      },
      "up_count": 2840,
      "same_count": 310,
      "down_count": 1950
    }
  ]
}
```

---

#### ⭐️ `snapshot` 字段完整数据字典与业务含义

##### 1. 基础属性与交易状态
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `name` | string | 证券简称（如 `"贵州茅台"`） |
| `symbol` | string | 请求标的代码（如 `"600519.sh"`） |
| `market` | string | 所属交易所市场（`"sh"` / `"sz"`） |
| `stock_type` | string | 证券类型标识（`"1001"` 普通股票等） |
| `datetime` | int | 纯净时间戳，格式 `YYYYMMDDHHMMSS` 原生整数（如 `20260924145958`） |
| `trading_status` | string | 交易状态代码（`"N"` 正常交易等） |
| `currency` | string | 币种（`"CNY"` 等） |
| `sector` | string | 板块分类 |
| `hsgt` | string | 互联互通标志（`"1"` 代表属于沪深股通/港股通标的） |
| `ah_symbol` | string | 关联的港股代码（若存在，如 `"01288.hk"`） |
| `listing_date` / `ipo_date` | int | 上市日期，格式 `YYYYMMDD` |
| `report_date` | int | 最近财报披露报告期 |

##### 2. 价格、量额与盘中表现
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `last_price` | int | **最新现价**（原生整型，保留完整精度，如 1650000 对应 1650.00 元） |
| `prev_close` | int | **昨收盘价** |
| `open_price` | int | 今日开盘价 |
| `high_price` / `low_price` | int | 今日最高价 / 今日最低价 |
| `limit_up` / `limit_down` | int | **今日涨停限价 / 今日跌停限价** |
| `change_rate` | float | 涨跌幅（单位：%） |
| `amplitude` | float | 振幅（单位：%） |
| `volume` | int | **本日累计成交总量（股）** |
| `now_volume` | int | 现手成交量（最新一笔成交股数） |
| `amount` | int/float | **本日累计成交总金额（元）** |
| `vwap` | int | 成交量加权平均价（均价，原生整型） |
| `turnover_rate` | float | 换手率（%） |
| `volume_ratio` | float | 量比 |
| `trade_count` | int | 本日累计成交总笔数 |
| `total_shares` / `circulating_shares` | int | 总股本（股） / 流通股本（股） |

##### 3. 财务指标与均线体系
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `pe` / `eps` / `roe` | float | 市盈率 / 每股收益（元） / 净资产收益率（%） |
| `ma5` / `ma10` / `ma20` | int | 5日、10日、20日价格均线（原生整数） |
| `volume_ma5` / `volume_ma10` / `volume_ma20` | int | 5日、10日、20日均量（股） |

##### 4. 盘口委买委卖与加权均价
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `weibi` | float | **委比（%）** |
| `weicha` | int | **委差（股）** |
| `total_bid_qty` / `total_ask_qty` | int | 当前委买挂单总量（股） / 委卖挂单总量（股） |
| `bid1_price` / `bid1_qty` | int | 买一申报价格 / 买一委托量（股） |
| `ask1_price` / `ask1_qty` | int | 卖一申报价格 / 卖一委托量（股） |
| `weighted_avg_bid_price` / `weighted_avg_ask_price` | int | **加权平均委买价格 / 加权平均委卖价格** |
| `weighted_avg_bid_qty` / `weighted_avg_ask_qty` | int | **加权平均委买总量 / 加权平均委卖总量** |

##### 5. 买卖十档盘口 (`bids` / `asks`)
买十档（`bids`）按价格从高到低排列，卖十档（`asks`）按价格从低到高排列：
- `level`：档位编号（1～10）；
- `price`：该档位挂单价格；
- `volume`：该档位排队总股数；
- `order_count`：该档位排队挂单总笔数。

##### 6. ⭐️ 分笔成交响应 (`recent_trades`)
快照中内嵌的最近撮合成交记录，每条记录包含：
- `trade_id`：成交流水号（存在时下发）；
- `time`：成交时间（`HHMMSS` 或毫秒级）；
- `price`：成交价格；
- `volume`：成交数量（股）；
- `side`：**主动买卖方向**：`"B"` = 外盘主买，`"S"` = 内盘主卖。

> ⏱️ **快照时间口径说明**：
> - 内层 `recent_trades[].time`：代表**交易所真实撮合事件时刻**，连续竞价与收盘集合竞价在 15:00:00 结束，因此最后一笔成交时间定格在 15:00:00。
> - 外层 `datetime`：代表**行情源中心网关的快照生成/广播时间戳**。盘后（15:00~17:00 清算结束前），上游行情节点在盘后固定价格交易与清算对账期间仍会定期广播最新的静态状态帧，因此盘后查询时外层 `datetime` 显示为网关刷新机器时间（如 16:27），内层成交数据依然保持 15:00 的最终收盘成交。

##### 7. ⭐️ 买一卖一排队委托队列 (`order_queue`)
提供最前沿盘口的微观排队分布：
- `bid1`：买一档排队明细数组，依订单挂入先后顺序记录的每笔委托股数（如 `[500, 200, 1000, ...]`）；
- `ask1`：卖一档排队明细数组，依订单挂入先后顺序记录的每笔委托股数。

##### 8. 市场宽度与期权属性（选配）
- `up_count` / `same_count` / `down_count`：全市场/该指数涵盖的上涨家数、平盘家数、下跌家数；
- `option_details`（仅期权合约输出）：包含 `contract_id`（合约代码）、`object_id`（标的证券代码）、`stock_unit`（合约单位）、`exercise_price`（行权价）、`start_date`（上市首日）、`del_date`（到期日）、`pre_interest`（昨持仓量）、`open_interest`（持仓量）。

---

### 3.2 模式二：实时流式推送 (`push` / `unpush`)

**适用场景**：实盘盯盘、千档盘口深度建模、高频委托撮合跟踪。

#### ⭐️ 推送类型与刷新频率（重点区分）

| 流式类型 (`type`) | 中文名称 | 推送频率 | 核心用途与特性 |
| :--- | :--- | :---: | :--- |
| **`thousand`** | **千档全深度盘口** | **3 秒** | 深度账簿全盘汇总，全量挂单档位按 **3 秒** 周期性快照/增量推送，适合微观挂单厚度、挂单撤减与冰山大单分析。 |
| **`trade`** | **实时逐笔成交** | **毫秒级** | 交易所真实撮合事件驱动，逐笔**毫秒级实时推流**，零人为缓冲延迟，用于主力大单扫盘跟踪。 |
| **`entrust`** | **实时逐笔委托** | **毫秒级** | 交易所挂单申报与撤单事件驱动，逐笔**毫秒级实时下发**，用于挂撤单生命周期分析。 |

#### 指令下发（支持单指令与批量指令数组）

##### 单指令下发
```json
{"action":"push","type":"thousand","symbol":"600519.sh"}
{"action":"unpush","type":"thousand","symbol":"600519.sh"}
{"action":"unpush","type":"all"}
```

##### 批量指令数组（推荐：一次性订阅多品种多类型）
```json
[
  {"action":"push","type":"thousand","symbol":"600519.sh"},
  {"action":"push","type":"trade","symbol":"600519.sh"},
  {"action":"push","type":"thousand","symbol":"000001.sz"},
  {"action":"unpush","type":"entrust","symbol":"000001.sz"}
]
```

---

## 4. 推送数据结构与字段详解

所有推送均通过 `{"ts": ..., "list": [ ... ]}` 批量分发。

### 4.1 千档全深度盘口 (`thousand`)

> ⏱️ **推送频率：3 秒一次**。全量千档深度包含大量微观挂单档位，数据量大，服务端按 **3 秒** 周期汇总推送快照/增量变动，适合宏观深度厚度建模与大单压盘测压。

```json
{
  "ts": 1790061785169,
  "list": [
    {
      "action": "push",
      "type": "thousand",
      "symbol": "600519.sh",
      "rows": [
        {
          "bids": [
            {"level": 1, "price": 1800100, "volume": 1200, "order_count": 5},
            {"level": 2, "price": 1800000, "volume": 5800, "order_count": 12}
          ],
          "asks": [
            {"level": 1, "price": 1800200, "volume": 800, "order_count": 3}
          ]
        }
      ]
    }
  ]
}
```

- `bids`：买盘档位，按价格由高到低严格排序；
- `asks`：卖盘档位，按价格由低到高严格排序；
- `level`：档位序号（1, 2, 3 ... 最大可达千档）；
- `price`：该档位原生整型价码；
- `volume`：该档位挂单总股数；
- `order_count`：该档位排队挂单总笔数。

### 4.2 实时逐笔成交 (`trade`)

> ⚡ **推送频率：毫秒级实时**。交易所撮合引擎每完成一笔真实撮合，立即以事件驱动**毫秒级**流式推送，零人为缓冲延迟。

```json
{
  "action": "push",
  "type": "trade",
  "symbol": "600519.sh",
  "rows": [
    {
      "time": 140957720,
      "trade_id": 123456,
      "trade_seq": 123456,
      "price": 1800100,
      "volume": 100,
      "amount": 180010,
      "side": "B",
      "trade_serial_no": 10993042,
      "buy_order_id": 123450,
      "sell_order_id": 123451,
      "buy_remain": 0,
      "sell_remain": 200
    }
  ]
}
```

- `side`：`"B"` = 买方主动吃单（外盘），`"S"` = 卖方主动砸单（内盘）；
- `buy_order_id` / `sell_order_id`：买卖双方交易所原始委托号；
- `buy_remain` / `sell_remain`：撮合后双方委托单的剩余挂单股数（剩余为 0 表示该笔委托完全成交）。

### 4.3 实时逐笔委托 (`entrust`) 申报推送

> ⚡ **推送频率：毫秒级实时**。交易所每接收一笔订单申报，立即以事件驱动**毫秒级**流式推送。（💡 **量化撤单提示**：若需要系统化买卖撤单明细与全景挂单追踪，建议优先选用 **D203 逐笔专属通道**）。

```json
{
  "action": "push",
  "type": "entrust",
  "symbol": "600519.sh",
  "rows": [
    {
      "time": 140957720,
      "order_id": 123456,
      "price": 1800100,
      "volume": 500,
      "side": "B",
      "order_type": "A"
    },
    {
      "time": 140958100,
      "order_id": 123456,
      "price": 1800100,
      "volume": 500,
      "side": "B",
      "order_type": "D"
    }
  ]
}
```

- `side`：`"B"` = 买入申报，`"S"` = 卖出申报；
- `order_type`：**订单动作类型**：
  - **`"A"`**：**新增申报（Add）**，正常进入委托簿排队（深沪两市统一映射）；
  - **`"D"`**：**撤单删除（Delete）**，交易者主动撤单，从委托簿中扣减移除（沪市原生专属）；
- `operation`：深市原生订单类别标识（`$` = 限价申报，`#` = 市价申报）。

> 💡 **深沪两市逐笔委托与撤单口径对照**：
> - **沪市（.sh）**：原生下发明确的动作类型（`order_type: "A"` 代表新增挂单申报，`"D"` 代表撤单删除）。
> - **深市（.sz）**：深交所原生逐笔委托流全部为**新增挂单申报**（系统统一对齐填充 `order_type: "A"`），订单类型细分在 `operation` 中（`$` 为限价，`#` 为市价）；深交所的撤单事件体现在**实时逐笔成交 (`trade`)** 流中（成交明细中标识为撤单执行）。

---

## 5. 错误代码速查

| code | 含义 | 解决指引 |
| :---: | :--- | :--- |
| `400` | 格式非法 / 参数缺失 | 检查 JSON 是否合法，确认包含 `action` 与 `symbol` |
| `405` | 尚未登录 | 本地启动 `data_interface` 并完成登录认证 |
| `407` | 积分不足 | 通用积分余额耗尽，充值或等待次日赠送额度刷新 |
| `502` | 查询数据解析异常 | 检查标的代码格式是否正确（如带 `.sh` 或 `.sz` 后缀） |
| `503` | 行情通道连接异常 | 检查本地客户端数据服务是否开启，网络是否畅通 |

---

## 6. 端到端 Python 开发实战范例

以下程序完整演示了 **“先发起单次综合十档快照查询（完整解析买卖十档、分笔成交明细与买一卖一委托队列），再建立千档盘口与逐笔流式订阅”** 的全套标准工作流：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D204 WebSocket 客户端：包含单次十档快照全字段解析 + 千档全深度盘口与逐笔流式订阅
依赖安装: pip install websocket-client
"""

import json
import time
import websocket

WS_URL = "ws://127.0.0.1:8080/d204"
TARGET = "600519.sh"  # 目标标的: 贵州茅台


def parse_snapshot(data):
    """解析单次十档综合快照的完整结构"""
    name = data.get("name")
    sym = data.get("symbol")
    dt = data.get("datetime")
    price = data.get("last_price", 0) / 1000.0
    prev_close = data.get("prev_close", 0) / 1000.0
    open_p = data.get("open_price", 0) / 1000.0
    high_p = data.get("high_price", 0) / 1000.0
    low_p = data.get("low_price", 0) / 1000.0
    vwap = data.get("vwap", 0) / 1000.0
    chg = data.get("change_rate", 0.0)
    weibi = data.get("weibi", 0.0)
    weicha = data.get("weicha", 0)
    vol = data.get("volume", 0)
    amt = data.get("amount", 0)

    print(f"\n====================【{name} ({sym}) 十档综合快照】====================")
    print(f"时间: {dt} | 状态: {data.get('trading_status')} | 现价: {price:.2f} ({chg:+.2f}%)")
    print(f"开盘: {open_p:.2f} | 最高: {high_p:.2f} | 最低: {low_p:.2f} | 昨收: {prev_close:.2f} | 均价: {vwap:.2f}")
    print(f"成交量: {vol} 股 | 成交额: {amt:.2f} 元 | 换手率: {data.get('turnover_rate')}% | 笔数: {data.get('trade_count')}")
    print(f"委比: {weibi:.2f}% | 委差: {weicha} 股 | 加权委买价: {data.get('weighted_avg_bid_price', 0)/1000.0:.2f} | 加权委卖价: {data.get('weighted_avg_ask_price', 0)/1000.0:.2f}")

    # 1. 打印卖十档与买十档
    print("\n--- 盘口十档申报 ---")
    asks = data.get("asks", [])
    for a in reversed(asks[:10]):
        print(f"  卖{a.get('level'):<2} | 价格:{a.get('price')/1000.0:>8.2f} | 挂单量:{a.get('volume'):>6}股 | 笔数:{a.get('order_count')}")

    bids = data.get("bids", [])
    for b in bids[:10]:
        print(f"  买{b.get('level'):<2} | 价格:{b.get('price')/1000.0:>8.2f} | 挂单量:{b.get('volume'):>6}股 | 笔数:{b.get('order_count')}")

    # 2. ⭐️ 重点：解析买一卖一委托排队明细队列 (order_queue)
    queue = data.get("order_queue", {})
    bid1_q = queue.get("bid1", [])
    ask1_q = queue.get("ask1", [])
    if bid1_q or ask1_q:
        print("\n--- 买一/卖一前沿委托挂单排队队列 (order_queue) ---")
        if bid1_q:
            print(f"  买一排队前5笔明细: {bid1_q[:5]} (共 {len(bid1_q)} 笔明细)")
        if ask1_q:
            print(f"  卖一排队前5笔明细: {ask1_q[:5]} (共 {len(ask1_q)} 笔明细)")

    # 3. ⭐️ 重点：解析分笔成交明细 (recent_trades)
    trades = data.get("recent_trades", [])
    if trades:
        print(f"\n--- 最近分笔成交明细 (recent_trades，共 {len(trades)} 笔) ---")
        for t in trades[:5]:
            side_desc = "🟢 外盘主买" if t.get("side") == "B" else "🔴 内盘主卖"
            print(f"  时间:{t.get('time')} | 成交号:{t.get('trade_id')} | 价:{t.get('price', 0)/1000.0:.2f} | 量:{t.get('volume')}股 | {side_desc}")

    print("=======================================================================\n")


def parse_thousand_book(sym, rows):
    """解析实时千档深度盘口变动"""
    for r in rows:
        bids = r.get("bids", [])
        asks = r.get("asks", [])
        b1_p = (bids[0].get("price") / 1000.0) if bids else 0.0
        b1_v = bids[0].get("volume") if bids else 0
        a1_p = (asks[0].get("price") / 1000.0) if asks else 0.0
        a1_v = asks[0].get("volume") if asks else 0
        print(f"[千档盘口] {sym} | 买一:{b1_p:.2f} ({b1_v}股, 共{len(bids)}档) <=> 卖一:{a1_p:.2f} ({a1_v}股, 共{len(asks)}档)")


def parse_trade(sym, rows):
    """解析逐笔成交"""
    for r in rows:
        side_desc = "🟢 外盘主买" if r.get("side") == "B" else "🔴 内盘主卖"
        price = r.get("price", 0) / 1000.0
        vol = r.get("volume", 0)
        print(f"[逐笔成交] {sym} | {side_desc} | 价格:{price:.2f} | 数量:{vol}股 | 成交号:{r.get('trade_id')}")


def parse_entrust(sym, rows):
    """解析逐笔委托与撤单"""
    for r in rows:
        ot = r.get("order_type")
        act = "🔴【撤单删除】" if ot == "D" else "新增挂单"
        side = "买" if r.get("side") == "B" else "卖"
        price = r.get("price", 0) / 1000.0
        vol = r.get("volume", 0)
        print(f"[逐笔委托] {sym} | {act} | {side} | 价格:{price:.2f} | 数量:{vol}股 | 订单号:{r.get('order_id')}")


def on_message(ws, message):
    try:
        payload = json.loads(message)
    except Exception as e:
        print("JSON 解析失败:", e)
        return

    items = payload.get("list", [])
    for it in items:
        action = it.get("action")
        typ = it.get("type")
        sym = it.get("symbol")

        # 错误提示
        if typ == "error":
            print(f"[错误] code={it.get('code')}: {it.get('msg')}")
            continue

        # 控制回执
        if typ == "response":
            print(f"[控制回执] {sym} -> {it.get('message')}")
            continue

        # 1. 单次快照响应 (once: snapshot)
        if action == "once" and typ == "snapshot":
            parse_snapshot(it)
            # 快照解析展示完成后，启动流式订阅演示
            subscribe_streaming(ws)
            continue

        # 2. 流式推送数据 (push)
        if action == "push":
            rows = it.get("rows", [])
            if typ == "thousand":
                parse_thousand_book(sym, rows)
            elif typ == "trade":
                parse_trade(sym, rows)
            elif typ == "entrust":
                parse_entrust(sym, rows)


def subscribe_streaming(ws):
    """批量订阅千档深度盘口与逐笔流"""
    print("\n>>> 开始下发批量流式订阅指令 (千档盘口 + 逐笔成交 + 逐笔委托)...")
    batch_cmd = [
        {"action": "push", "type": "thousand", "symbol": TARGET},
        {"action": "push", "type": "trade", "symbol": TARGET},
        {"action": "push", "type": "entrust", "symbol": TARGET}
    ]
    ws.send(json.dumps(batch_cmd))


def on_open(ws):
    print(">>> D204 WebSocket 连接建立成功！")
    # 首先发起单次查询：获取目标股票综合十档快照（含指标、十档、分笔成交与委托队列）
    print(f">>> 发送单次快照查询 (once: snapshot) -> {TARGET}")
    once_query = {
        "action": "once",
        "type": "snapshot",
        "symbol": TARGET
    }
    ws.send(json.dumps(once_query))


def on_error(ws, err):
    print("WebSocket 出错:", err)


def on_close(ws, code, msg):
    print(f"WebSocket 连接断开: {code} - {msg}")


if __name__ == "__main__":
    print(f"正在连接 D204 行情接口: {WS_URL} ...")
    app = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    app.run_forever()
```
