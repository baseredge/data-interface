# D203 WebSocket 实时行情接口开发指南

> **适用场景**：高频量化交易、短线主力资金监控、L2 逐笔委托与成交穿透、盘口队列还原与历史逐笔毫秒级复盘。

---

## 1. 快速接入与前置条件

D203 提供标准 WebSocket 流式接口。所有数据均采用 **UTF-8 纯文本 JSON** 格式传输，无需安装复杂的二进制协议库或解析环境，任何支持 WebSocket 的编程语言（Python、Go、C++、Java、Rust、Node.js 等）均可直接接入。

### 1.1 服务连接地址

```text
ws://127.0.0.1:<ProxyPort>/d203
```

- `<ProxyPort>` 为本机 `data_interface` 运行端口（默认为 `8080`，以客户端界面显示的本机代理端口为准）；
- 默认完整连接地址：`ws://127.0.0.1:8080/d203`；
- `/d203` 为固定请求路由路径，连接建立后由客户端直接下发 JSON 指令。

### 1.2 认证与前置条件
1. **本地客户端就绪**：本机已启动 `data_interface` 并已成功登录账号；
2. **积分充足**：当前账号通用积分余额（`pointsBalance`）大于 0；
3. **即连即用**：客户端在本地完成账户认证，外部程序连接本机 WebSocket 时无需在握手协议中注入 Token 或 Cookie。

---

## 2. 请求指令与订阅协议

连接建立后，客户端通过 WebSocket 发送 JSON 指令订阅或退订指定品种。每条客户端消息为**单个 JSON 对象**。

### 2.1 核心请求字段

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `type` | string | 是 | 数据类型：`entrust`（逐笔委托）、`trade`（逐笔成交）、`orderstat`（委托统计）、`fullqueue`（全景队列十档）、`maintrade`（主力大单成交） |
| `code` | string | 是 | 标的代码，格式为大写市场前缀 + 6位代码，如 `SH600519`、`SZ000001`、`BJ832000` |
| `enable` | int | 是 | 操作类型：`1` = 实时持续推送，`0` = 退订释放，`2` = 单次/历史序列翻页查询 |
| `num` | int | 否 | 单批次推送或翻页最大记录条数（默认由服务控制，翻页时建议指定，如 20、50） |
| `startseq` | int | 否 | 起始序号/游标。在 `enable: 2`（单次翻页）时**必填**，用于精准回溯历史逐笔序列 |
| `cond` | object | 否 | 过滤条件对象（仅适用于 `entrust` 逐笔委托，详见 2.3 节） |

### 2.2 基础请求示例

#### 实时流式订阅（逐笔成交与委托）
```json
{"type":"trade","code":"SH600519","enable":1,"num":50}
{"type":"entrust","code":"SH600519","enable":1,"num":50}
```

#### 历史序列回溯与单次翻页查询
```json
{"type":"entrust","code":"SH600519","enable":2,"startseq":100001,"num":50}
```

#### 退订指定标的
```json
{"type":"trade","code":"SH600519","enable":0}
{"type":"entrust","code":"SH600519","enable":0}
```

### 2.3 高级条件过滤（`cond` 参数）

在订阅 `entrust`（逐笔委托）时，可通过 `cond` 对象精确按价格、股数、委托类型或**委托状态（如只看撤单）**进行服务端过滤，大幅降低无效数据下发量：

```json
{
  "type": "entrust",
  "code": "SH600519",
  "enable": 1,
  "cond": {
    "status": [3, 4],
    "lowvol": 10000,
    "highvol": 1000000
  }
}
```

| `cond` 子字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `status` | int[] | **委托状态过滤数组**。可选值：`0`（新增申报）、`1`（挂单排队）、`2`（部分成交）、`3`（部分撤单）、`4`（全部撤单）、`5`（全部成交）。例如订阅全部撤单变动使用 `[3, 4]`（部撤 + 全撤），仅订阅新申报使用 `[0]` |
| `lowprice` / `highprice` | int | 最低/最高委托价格区间（原生整型价码） |
| `lowvol` / `highvol` | int | 最低/最高委托股数区间（单位：股） |
| `ordermmp` | int[] | **委托档数（申报盘口档位）过滤数组**。过滤指定委托档位（如 `[1, 2, 3]` 仅监控买一到买三，`[4]` 涨停价挂单，`[8]` 跌停价挂单，详见 4.1 节档位字典） |

---

## 3. 响应报文与数据结构

所有服务端响应均采用统一的 `ts + list` 外壳包装：
```json
{
  "ts": 1790061785169,
  "list": [
    {
      "action": "push",
      "type": "entrust",
      "symbol": "SH600519",
      "code": "600519",
      "market_id": 1,
      "rows": [ ... ]
    }
  ]
}
```
- `ts`：服务端毫秒级时间戳；
- `list`：行情或控制结果项列表；
- 列表中每一项包含该标的本次变动的具体行数组 `rows`。

---

## 4. 核心数据模型与字段解析

### 4.1 逐笔委托 (`entrust`)

实时还原盘口每一笔委托申报与撤单变动，是洞察主力真实意图、排查虚假挂单的核心数据。

#### 响应结构示例
```json
{
  "action": "push",
  "type": "entrust",
  "symbol": "SH600519",
  "code": "600519",
  "market_id": 1,
  "total_num": 2,
  "rows": [
    {
      "time": 93001230,
      "seq": 102401,
      "order_no": 589214,
      "price": 1650000,
      "volume": 2000,
      "direction": 1,
      "status": 0,
      "order_mmp": 1,
      "volume_code": 2
    },
    {
      "time": 93002500,
      "seq": 102402,
      "order_no": 589214,
      "price": 1650000,
      "volume": 2000,
      "direction": 1,
      "status": 4,
      "order_mmp": 1,
      "volume_code": 2
    }
  ]
}
```

#### `rows` 字段定义与数据字典

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `time` | int | 委托申报时间，格式为 `HHMMSSmmm` 原生整数（如 `93001230` 表示 09:30:01.230） |
| `seq` | int | 单日逐笔全局自增序号，按时间绝对递增 |
| `order_no` | int | **委托单号**（交易所原始订单编号，可用于全生命周期跟踪） |
| `price` | int | 委托价格（原生整型，如 1650000 表示 1650.00 元） |
| `volume` | int | 委托股数（单位：股） |
| `direction` | int | **买卖方向**：`0` = 买入（字段缺省时默认代表 0），`1` = 卖出 |
| `status` | int | **委托状态代码**（`0`=新增申报, `1`=挂单排队, `2`=部分成交, `3`=部分撤单, `4`=全部撤单, `5`=全部成交；字段缺省时默认代表 0，详见下表） |
| `order_mmp` | int | **委托档数（申报盘口位置）**：委托下单当时所处的买卖盘口深度档位（1~3=买1~买3, 4=涨停, 5~7=卖1~卖3, 8=跌停等，详见下表） |
| `volume_code` | int | **单据体量级别**：`1`=超大单，`2`=大单，`3`=中单，`4`=小单 |
| `flags` | int | 业务标记位（整型） |

#### ⭐️ 重点：委托状态代码 (`status`) 对照表

| `status` 取值 | 状态名称 | 核心业务含义与实盘行为 | 量化策略应用要点 |
| :---: | :--- | :--- | :--- |
| **`0`** | **新增申报** | 订单初次进入交易所撮合队列，正式挂入买/卖盘口。<br>*(注：当 JSON 响应缺省此字段时，默认值即代表 0)* | 捕捉实时新增委托深度、大资金挂单测压。 |
| **`1`** | **挂单排队** | 订单在交易所队列中排队等待撮合，未完成成交。 | 追踪在册未撮合的有效存量挂单。 |
| **`2`** | **部分成交** | 该笔订单部分股数被撮合，剩余未成交股数继续保留在挂单队列。 | 追踪未完全撮合的被动挂单消耗进度。 |
| **`3`** | **部分撤单（部撤）** | 交易者在部分成交后，撤回剩余未成交的股数。 | 监控大单吃进部分后的撤退动作，还原真实撤单规模。 |
| **`4`** | **全部撤单（全撤）** | **交易者主动全额撤回该订单**。未成交部分全部注销，直接从盘口中删除。 | **核心风向标**：监控高频撤单、假挂单垫单、压盘后瞬间撤单突破等操盘动作。 |
| **`5`** | **全部成交** | 整笔挂单已全额被对手盘撮合吃掉，订单生命周期彻底终结并退出盘口。 | 确认挂单完全兑现，用于构建真实成交链条与订单完结闭环。 |

#### ⭐️ 重点：委托档数 (`order_mmp`) 对照表

`order_mmp`（Order Market Position）记录了委托申报时所处的盘口挂单档位，是洞察挂单意图（如是否顶格涨停申报、是压在卖一还是深埋十档）的核心指标：

| `order_mmp` 取值 | 盘口位置 | 业务含义说明 | 典型量化策略应用 |
| :---: | :--- | :--- | :--- |
| **`1` ~ `3`** | **买一 ~ 买三** | 下单时委托价位于买方最优盘口前三档 | 监测最前沿核心买盘支撑与逼空垫单 |
| **`4`** | **涨停价** | 下单委托价格直接报在涨停价位（封板委托） | **打板/封单监测**：监控涨停板排队挂单与封板资金规模 |
| **`5` ~ `7`** | **卖一 ~ 卖三** | 下单时委托价位于卖方最优盘口前三档 | 监测最前沿核心卖盘抛压与压盘试盘 |
| **`8`** | **跌停价** | 下单委托价格直接报在跌停价位（跌停封单） | **撬板/跌停监测**：监控跌停板封单堆积或出逃 |
| **`14` ~ `20`** | **买四 ~ 买十** | 委托价位于买四至买十深度档位（值 = `10 + 档位`，如 14=买4, 20=买10） | 监控主力中远端真假护盘大单与底仓托单 |
| **`24` ~ `30`** | **卖四 ~ 卖十** | 委托价位于卖四至卖十深度档位（值 = `20 + 档位`，如 24=卖4, 30=卖10） | 监控中远端压盘大单、空中楼阁假压单 |
| **`0`** | **盘口外 / 未入档** | 挂单价格超出当前十档盘口范围，或直接成交流水 | 统计超深度挂单与场外沉淀单 |

#### ⭐️ 辅助维度：单据体量 (`volume_code`) 对照表

| `volume_code` 取值 | 体量级别 | 说明 |
| :---: | :--- | :--- |
| **`1`** | **超大单** | 机构与特大主力资金订单 |
| **`2`** | **大单** | 大户及一般机构订单 |
| **`3`** | **中单** | 中户及大散户订单 |
| **`4`** | **小单** | 普通散户订单 |

---

### 4.2 逐笔成交 (`trade`)

记录交易所撮合引擎完成的每一笔真实成交细节，包含买卖双方原始委托编号及主动成交意图。

#### 响应结构示例
```json
{
  "action": "push",
  "type": "trade",
  "symbol": "SH600519",
  "code": "600519",
  "market_id": 1,
  "rows": [
    {
      "time": 93005120,
      "seq": 182390,
      "trade_no": 91823,
      "price": 1650000,
      "volume": 500,
      "amount": 825000,
      "active_flag": 1,
      "buy_no": 589215,
      "buy_volume": 500,
      "buy_status": 5,
      "buy_volume_code": 3,
      "sell_no": 589110,
      "sell_volume": 500,
      "sell_status": 2,
      "sell_volume_code": 3,
      "volume_code": 3
    }
  ]
}
```

#### `rows` 字段定义与数据字典

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `time` | int | 撮合成交时间（`HHMMSSmmm`） |
| `seq` | int | 逐笔全局自增序号 |
| `trade_no` | int | 成交流水号 |
| `price` | int | 撮合成交价格（原生整数） |
| `volume` | int | 成交数量（股） |
| `amount` | int | 成交金额（元，部分品种可能省略由价格与数量推算） |
| `active_flag` | int | **主动买卖标志**：`0` = **主动买入（外盘，买方较晚委托并主动吃单；字段缺省时无条件代表 0）**；`1` = **主动卖出（内盘，卖方较晚委托并主动吃单）**；详见下方主动方向判定说明 |
| `buy_no` | int | **买方原始委托单号**（可与 `entrust.order_no` 关联） |
| `buy_volume` | int | 本次成交对应买方撮合数量 |
| `buy_status` | int | **买方委托在此次撮合后的状态**（包含基础状态 `1, 2, 4` 与执行状态 `10, 11, 13, 14, 15`，详见下表） |
| `buy_volume_code` | int | 买方单据体量级别（`1`=超大单，`2`=大单，`3`=中单，`4`=小单） |
| `sell_no` | int | **卖方原始委托单号**（可与 `entrust.order_no` 关联） |
| `sell_volume` | int | 本次成交对应卖方撮合数量 |
| `sell_status` | int | **卖方委托在此次撮合后的状态**（含义同买方，详见下表） |
| `sell_volume_code` | int | 卖方单据体量级别（同上） |
| `volume_code` | int | 本笔撮合成交的综合体量级别 |

#### ⭐️ 重点：逐笔成交委托状态码 (`buy_status` / `sell_status`) 对照表

逐笔成交下发的 `buy_status` 与 `sell_status` 反映了该笔订单在撮合发生的瞬间所处的生命周期与执行角色（由低位基础状态码 `0~5` 与撮合执行状态标志 `+10` 构成）：

| 状态码 | 对应基础状态 | 撮合微观行为说明 | 订单盘口队列去向 |
| :---: | :---: | :--- | :--- |
| **`1`** / **`11`** | 1 (挂单排队) | **在册排队挂单被撮合**（Maker 角色，原在盘口中排队被吃） | 视成交量决定是否继续留存 |
| **`2`** | 2 (部分成交) | **部分成交（非终态）**：本次撮合仅吃掉部分委托量，剩余量继续排队 | **继续保留在盘口队列** |
| **`4`** / **`14`** | 4 (全部撤单) | **撤单/注销确认**：订单剩余未成交部分撤回 | 从盘口队列彻底移除 |
| **`10`** | 0+10 | **主动吃单方到达即撮合**（Taker 角色，新增申报直接命中对手盘） | 视成交量决定是否终结 |
| **`13`** | 3+10 | **撮合伴随部分撤单/自动废单** | 扣除撤单部分 |
| **`5`** / **`15`** | 5 (全部成交) | **全部成交完结（终态）**：整笔订单在本次撮合后剩余量为 0，生命周期完全终结 | **从盘口队列彻底移除** |

> **量化策略订单生命周期判定：**
> - **终态过滤（从盘口深度缓存中移除订单）**：判断 `status == 5 || status == 15`（全部成交完结）或 `status == 4 || status == 14`（全额撤单）；
> - **排队更新（更新盘口深度缓存中的未成交余量）**：判断 `status == 2`（部分成交，剩余挂单量 = 原始委托量 - 累计成交量）。

#### ⭐️ 重点：主动买卖方向 (`active_flag`) 判定原理与微观跳价说明

1. **默认值规范**：
   在 JSON 响应中，若 `active_flag` 字段缺省未出现，默认代表 `0`（主动买入 / 外盘）；显式出现 `1` 时代表主动卖出（内盘）。
2. **撮合时序判定（第一性原理）**：
   主动买卖方向完全基于交易所撮合引擎中订单进入队列的**到达时序**确定，绝非基于价格变动（Tick Rule）进行事后反推：
   - 每条成交记录均携带买方单号 `buy_no` 与卖方单号 `sell_no`；
   - **`buy_no > sell_no`**：买方到达较晚，主动击打先挂单的卖方（Taker 为买方），系统推送 **`0`（主买/外盘）**；
   - **`sell_no > buy_no`**：卖方到达较晚，主动击打先挂单的买方（Taker 为卖方），系统推送 **`1`（主卖/内盘）**。
3. **价格上涨但 `flag=1` 的微观结构解析**：
   在盘口买方抬高申报或跳价时，会出现“成交价较前一笔上涨但仍标记为主动卖出”的正常现象：
   - 例如：上一笔成交价为 100.00 元；随后买方在 100.05 元挂入新的高价限价买单（Maker，先入队，`buy_no` 较小）；紧接着激进卖方下单（Taker，后入队，`sell_no` 较大）以 100.05 元或市价直接吃掉该买单。此时成交价为 100.05 元（相对上一笔上涨了 0.05 元），但发起主动吃单行为的是卖方，因此系统准确标记为 `flag=1`。
   - **策略建议**：高频量化中切勿使用相邻两笔价格涨跌反推主动方向，以订单号到达时序确定的 `active_flag` 才是真实撮合事实。

> **实战技巧**：通过 `trade` 中的 `buy_no` 与 `sell_no` 向上追溯 `entrust` 委托单，可以精确还原大资金是在被动挂单等待对手盘吞噬，还是在主动扫盘吃单！

---

### 4.3 委托统计 (`orderstat`)

提供全日累计的宏观委买、委卖、订单数以及**买卖累计撤单笔数**统计，适合构建资金动能与盘面冷热指标。

```json
{
  "action": "push",
  "type": "orderstat",
  "symbol": "SH600519",
  "statistics": {
    "buy_volume": 12890500,
    "sell_volume": 15402100,
    "buy_order_count": 8920,
    "sell_order_count": 9410,
    "buy_cancel_count": 1340,
    "sell_cancel_count": 1120
  }
}
```

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `buy_volume` / `sell_volume` | int | 累计委买总股数 / 累计委卖总股数 |
| `buy_order_count` / `sell_order_count` | int | 累计委买总笔数 / 累计委卖总笔数 |
| `buy_cancel_count` / `sell_cancel_count` | int | **累计买方撤单笔数 / 累计卖方撤单笔数**（计算市场撤单倾向的核心参数） |

---

### 4.4 全景队列十档 (`fullqueue`)

提供买卖前十档的详细深度排队队列，以及该档位内部发生的微观挂单/撤单变更操作。

- `direction`：`1` = 买方队列，`2` = 卖方队列；
- `is_full`：`true` = 全景快照刷新，`false` = 增量变化；
- `price`：档位价格；
- `volume`：档位总排队股数；
- `order_count`：该档位排队挂单笔数；
- `operations`：队列具体明细事件：
  - `order_no`：排队的委托单号；
  - `volume`：排队股数；
  - `trade_volume`：已撮合成交股数；
  - `status`：状态（`0`=挂单排队，`1`=撮合成交移除，`3`=撤单移除）。

---

### 4.5 主力成交 (`maintrade`)

专门筛选下发大额成交订单，方便策略直接捕获大机构、主力游资扫盘动作。

- `time`：成交时间；
- `trade_no`：成交编号；
- `price`：成交价格；
- `volume`：大额成交股数；
- `amount`：成交总金额；
- `active_flag`：主动方向（`0`=主买/外盘，`1`=主卖/内盘；枚举定义与 `trade.active_flag` 完全一致，字段缺省时代表 0）。

---

### 4.6 微观结构与量化识别指南（冰山订单 / 隐藏量识别）

1. **A 股集中竞价撮合机制说明**：
   沪深交易所股票集中竞价交易系统中，撮合引擎**不存在原生的冰山保留量订单类型（Reserve/Iceberg Order）**。市场上所有所谓的“冰山订单”，100% 属于算法交易执行端（如 TWAP、VWAP、POV 等分批拆单算法）在客户端或交易柜台总线层面的行为。
2. **数据接口边界**：
   本接口严格透传交易所下发的原始委托与成交流水，不存在也不伪造任何“原生隐藏量字段”。量化策略对冰山订单应作为**“行为特征识别（疑似隐藏量）”**。
3. **推荐识别方法**：
   - **盘口吃完快速回填（Queue Refill）**：某核心买卖档位或某一固定价位挂单被大单连续吃掉后，极短时间窗口（如数十至数百毫秒）内有新委托（`entrust`）迅速申报并补齐相同或近似规模的委托量；
   - **累计成交远超初始挂单量**：在 `trade` 记录中，针对该固定价位的连续成交总量大幅超过该价位最初挂出的在册委托深度；
   - **委托特征聚集性**：连续多次补单在单笔委托数量（`volume`）、体量分级（`volume_code`）上呈现高度统计一致性。

---

## 5. 错误码与控制响应

| 代码 (`code`) | 提示信息 | 处理建议 |
| :---: | :--- | :--- |
| `400` | 参数错误 / 格式非法 | 检查 JSON 语法、字段类型与 `code` 大小写格式 |
| `405` | 请先认证登录 | 打开本地客户端完成用户登录 |
| `407` | 积分不足 | 账号通用积分已耗尽，请充值或等待次日赠送积分重置 |
| `503` | 服务连接失败 / 暂不可用 | 确认客户端本地数据服务处于“运行中”状态 |

---

## 6. 端到端 Python 开发实战范例

以下是基于 Python `websocket-client` 编写的完整独立量化接收程序，包含**实时连接、逐笔委托/成交订阅、撤单状态（全撤/部撤）判断及大单主动买入过滤**：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D203 WebSocket 极速逐笔行情接收客户端
依赖安装: pip install websocket-client
"""

import json
import threading
import time
import websocket

# 本机 data_interface 代理端口（默认 8080）
WS_URL = "ws://127.0.0.1:8080/d203"
TARGET_STOCK = "SH600519"  # 目标标的: 贵州茅台


def format_time(t_val):
    """格式化 HHMMSSmmm 时间整型为可读字符串"""
    s = str(t_val).zfill(9)
    return f"{s[0:2]}:{s[2:4]}:{s[4:6]}.{s[6:9]}"


def format_mmp(mmp):
    """格式化委托档数 (Order Market Position)"""
    if 1 <= mmp <= 3:
        return f"买{mmp}"
    if mmp == 4:
        return "涨停"
    if 5 <= mmp <= 7:
        return f"卖{mmp - 4}"
    if mmp == 8:
        return "跌停"
    if 14 <= mmp <= 20:
        return f"买{mmp - 10}"
    if 24 <= mmp <= 30:
        return f"卖{mmp - 20}"
    return "—" if mmp == 0 else f"档{mmp}"


def format_vol_code(vc):
    """单据体量级别说明"""
    return {1: "超大单", 2: "大单", 3: "中单", 4: "小单"}.get(vc, "—")


def parse_entrust(stock_code, row):
    """解析逐笔委托与撤单状态"""
    time_str = format_time(row.get("time", 0))
    order_no = row.get("order_no", 0)
    price = row.get("price", 0) / 1000.0  # 假设为厘/毫转换，具体依标的整数位
    vol = row.get("volume", 0)
    direction = "卖出" if row.get("direction") == 1 else "买入"
    status = row.get("status", 0)
    mmp_str = format_mmp(row.get("order_mmp", 0))
    vc_str = format_vol_code(row.get("volume_code", 0))

    # 委托状态映射字典
    status_desc = {
        0: "新增申报",
        1: "挂单排队",
        2: "部分成交",
        3: "🟠【部分撤单】",
        4: "🔴【全部撤单】",
        5: "全部成交"
    }.get(status, f"状态({status})")

    # 重点高亮撤单记录
    if status in (3, 4):
        print(f"[委托撤单] {time_str} | 标的:{stock_code} | 单号:{order_no} | {direction} | 档位:{mmp_str} | 级别:{vc_str} | 价格:{price:.2f} | 数量:{vol}股 | 状态:{status_desc}")
    else:
        # 常规挂单（如需精简日志可注释）
        print(f"[委托挂单] {time_str} | 标的:{stock_code} | 单号:{order_no} | {direction} | 档位:{mmp_str} | 级别:{vc_str} | 价格:{price:.2f} | 数量:{vol}股 | 状态:{status_desc}")


def parse_trade(stock_code, row):
    """解析逐笔成交与主力买卖方向"""
    time_str = format_time(row.get("time", 0))
    trade_no = row.get("trade_no", 0)
    price = row.get("price", 0) / 1000.0
    vol = row.get("volume", 0)
    active = row.get("active_flag", 0)

    # 主动方向
    act_str = {
        0: "🔴 主动买入(外盘)",
        1: "🟢 主动卖出(内盘)"
    }.get(active, "未知")

    buy_no = row.get("buy_no", 0)
    sell_no = row.get("sell_no", 0)
    buy_st = row.get("buy_status", 0)
    sell_st = row.get("sell_status", 0)
    vc_str = format_vol_code(row.get("volume_code", 0))

    st_map = {0: "新单", 1: "排队", 2: "部成", 3: "部撤", 4: "全撤", 5: "全成"}

    print(f"[逐笔成交] {time_str} | 标的:{stock_code} | 成交号:{trade_no} | 价:{price:.2f} | 量:{vol}股 | 级别:{vc_str} | 方向:{act_str} | 买单:{buy_no}({st_map.get(buy_st, str(buy_st))}) <=> 卖单:{sell_no}({st_map.get(sell_st, str(sell_st))})")


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception as e:
        print("JSON 解析失败:", e)
        return

    # 遍历外层 list 项
    msg_list = data.get("list", [])
    for item in msg_list:
        action = item.get("action")
        msg_type = item.get("type")
        code = item.get("symbol") or item.get("code")

        # 系统控制或通知消息
        if action == "system" or msg_type == "system":
            print(f"[系统提示] {item.get('message')}")
            continue

        # 错误消息
        if action == "error" or msg_type == "error":
            print(f"[错误提醒] code={item.get('code')}, msg={item.get('message')}")
            continue

        # 行情数据解析
        rows = item.get("rows", [])
        if msg_type == "entrust":
            for r in rows:
                parse_entrust(code, r)
        elif msg_type == "trade":
            for r in rows:
                parse_trade(code, r)
        elif msg_type == "orderstat":
            stats = item.get("statistics", {})
            print(f"[委托统计] 标的:{code} | 委买总量:{stats.get('buy_volume')} | 委卖总量:{stats.get('sell_volume')} | 买撤单笔数:{stats.get('buy_cancel_count')} | 卖撤单笔数:{stats.get('sell_cancel_count')}")


def on_open(ws):
    print(">>> WebSocket 连接成功！准备下发订阅指令...")

    # 1. 订阅逐笔成交
    sub_trade = {
        "type": "trade",
        "code": TARGET_STOCK,
        "enable": 1,
        "num": 50
    }
    ws.send(json.dumps(sub_trade))

    # 2. 订阅逐笔委托（包含挂单与撤单）
    sub_entrust = {
        "type": "entrust",
        "code": TARGET_STOCK,
        "enable": 1,
        "num": 50
    }
    ws.send(json.dumps(sub_entrust))

    # 3. 订阅全日委托统计
    sub_stat = {
        "type": "orderstat",
        "code": TARGET_STOCK,
        "enable": 1
    }
    ws.send(json.dumps(sub_stat))


def on_error(ws, error):
    print("WebSocket 异常:", error)


def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket 已断开连接: {close_status_code} - {close_msg}")


if __name__ == "__main__":
    print(f"正在连接 D203 行情端点: {WS_URL} ...")
    ws_app = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    # 启动 WebSocket 接收循环
    ws_app.run_forever()
```
