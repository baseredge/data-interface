# D5 历史深度行情与全量 Level 2 归档 API

D5 是运行在本地的标准 HTTP 数据服务，提供全市场历史 Level 2 归档行情（逐笔委托、逐笔成交、行情快照）与早盘集合竞价数据。

> 接口实施分时流控保护（开盘时段 1 QPS / 闲时与周末 100 QPS），详见 [第 9 节 调用频率与流控策略](#9-调用频率与流控策略-rate-limit)。

---

## 1. 开始前准备

1. **服务启动与登录**：启动本地 `data_interface` 程序，并确认已登录且账号具备 D5 产品权限。
2. **本地代理地址**：默认 HTTP 服务地址为：
   ```text
   http://127.0.0.1:8080
   ```
   如修改了配置文件中的端口，请将 `8080` 替换为实际监听端口。

---

## 2. 接口总览

### 2.1 全日 Level 2 归档接口 (L2P)
| 接口名称 | 请求方式 | 接口路径 | 核心用途 | 频率限制 (QPS) |
| :--- | :--- | :--- | :--- | :--- |
| **L2P_可用交易日列表** | `GET` | `/d5/l2plus/dates` | 获取全市场已完成归档的所有交易日列表 | 盘中 1 / 闲时 100 |
| **L2P_单日可用股票列表** | `GET` | `/d5/l2plus/stocks` | 查询指定日期可供分析的股票代码清单，支持按沪深市场筛选 | 盘中 1 / 闲时 100 |
| **L2P_单股深度数据 (行情/委托/成交)** | `GET` | `/d5/l2plus/stock` | 提取单只股票的全量逐笔成交、逐笔委托和全景盘口切片数据 | 盘中 1 / 闲时 100 |

### 2.2 早盘集合竞价 (09:15-09:25:03) 归档接口 (D203 竞价)
| 接口名称 | 请求方式 | 接口路径 | 核心用途 | 频率限制 (QPS) |
| :--- | :--- | :--- | :--- | :--- |
| **d203_早盘竞价可用日期** | `GET` | `/d5/auction/d203/dates` | 获取全市场早盘竞价已完成归档的所有交易日列表 | 盘中 1 / 闲时 100 |
| **d203_早盘竞价全市场流** | `GET` | `/d5/auction/d203/stream` | 通过 HTTP 分块流式获取全市场当日早盘竞价明细 | 盘中 1 / 闲时 100 |

### 2.3 全日高频逐笔 (09:15-15:00) 归档接口 (D203 全天)
| 接口名称 | 请求方式 | 接口路径 | 核心用途 | 频率限制 (QPS) |
| :--- | :--- | :--- | :--- | :--- |
| **d203_全天逐笔可用日期** | `GET` | `/d5/fullday/d203/dates` | 获取全天高频逐笔已完成归档的所有交易日列表 | 盘中 1 / 闲时 100 |
| **d203_全天股票状态清单** | `GET` | `/d5/fullday/d203/stocks` | 查询指定日期全市场股票收录三态（`ready`、`empty`、`pending`） | 盘中 1 / 闲时 100 |
| **d203_单股全天逐笔数据** | `GET` | `/d5/fullday/d203/stock` | 提取单只标的全天（9:15-15:00）全量逐笔委托与逐笔成交 NDJSON 流 | 盘中 1 / 闲时 100 |

---

## 3. 接口详细定义

### 3.1 可用交易日列表

获取历史全市场已归档入库的全部可用交易日清单。

- **请求路径**：`GET /d5/l2plus/dates`
- **请求参数**：无

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/l2plus/dates
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "type": "l2plus",
    "total": 295,
    "dates": [
      20260930,
      20260929,
      20260926,
      20260925
    ]
  }
}
```

---

### 3.2 单日可用股票列表

查询指定交易日可供分析的股票代码清单。

- **请求路径**：`GET /d5/l2plus/stocks`
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `date` | integer / string | **是** | 8 位交易日代码 | `20260930` |
| `market` | string | 否 | 市场过滤：`SH`（沪市）或 `SZ`（深市），留空则返回全市场 | `SH` |

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/l2plus/stocks?date=20260930&market=SH
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "type": "l2plus",
    "date": 20260930,
    "total": 2260,
    "codes": [
      "600000.SH",
      "600001.SH",
      "600519.SH"
    ]
  }
}
```

---

### 3.3 单股深度数据 (行情/委托/成交)

全自动获取单只股票在指定交易日的全量高频深度数据。本地客户端代理在纯内存中完成解析，直接输出清洗后的标准 JSON 数据。

- **请求路径**：`GET /d5/l2plus/stock`
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `date` | integer / string | **是** | 8 位交易日代码 | `20260930` |
| `code` | string | **是** | 股票代码（支持纯数字如 `600519` 或标准后缀如 `600519.SH`、`000001.SZ`） | `600519.SH` |

#### 输出数据说明

- 数据直接以完整的标准 CSV 纯文本字符串交付（各列逗号分隔，各行换行符分隔）。
- **极速性能与类型自动推断**：Python 可直接调用 `pd.read_csv(io.StringIO(csv_text))` 或 `polars.read_csv(...)`，利用底层的多线程 C/Rust 解析器极速秒级解析，且**自动将价格推断为 float64、成交量推断为 int64**，无需手动进行类型转换。
- **易于归档**：如需离线存盘，一行代码 `f.write(csv_text)` 即可直接持久化为标准 CSV 文件或直接导入 ClickHouse / DolphinDB。

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "stock": "600519.SH",
  "date": 20260930,
  "files": {
    "行情.csv": "时间,最新价,成交量,成交额,买一价,买一量,卖一价,卖一量\n09:30:00,1800.00,1000,1800000.00,1799.90,100,1800.00,200\n...",
    "逐笔成交.csv": "成交时间,成交序号,成交价格,成交数量,成交金额,BS标志,买方委托序号,卖方委托序号\n09:30:01,100001,1800.00,100,180000.00,B,200001,200002\n...",
    "逐笔委托.csv": "委托时间,委托序号,委托价格,委托数量,BS标志,委托类型\n09:30:00,200001,1800.00,100,B,2\n..."
  }
}
```

---

## 4. 数据字段与状态枚举字典

D5 包含三种全量数据文件（`逐笔委托.csv`、`逐笔成交.csv`、`行情.csv`）。为了保证高频海量数据的高效传输与量化代码的原生兼容性，行内数据字段保留交易所与行业标准代码（单字符 ASCII）。各字段定义及状态枚举字典如下：

### 4.1 逐笔委托 (`逐笔委托.csv`)

记录交易所订单簿接收到的每一笔限价/市价申报与撤单行为。

| 字段名称 | 类型 | 说明与格式 |
| :--- | :---: | :--- |
| **代码** | 字符 | 标的代码（如 `605179.SH`） |
| **交易所代码** | 字符 | 交易所标的代码（如 `605179`） |
| **自然日** | 整数 | 交易日期（8 位整型，如 `20260817`） |
| **时间** | 整数 | 委托时间戳（毫秒级，格式 `HHMMSSmmm`，如 `91400270` 代表 `09:14:00.270`） |
| **委托编号** | 字符 | 申报业务流水号 |
| **交易所委托号** | 整数 | 交易所系统顺序委托号（可与逐笔成交中的叫买/叫卖序号关联） |
| **委托类型** | 字符 | **委托状态枚举**（详见下表） |
| **委托代码** | 字符 | **买卖类别枚举**（详见下表） |
| **委托价格** | 整数 | 申报价格（定点整数，**需除以 10000 换算为元**，如 `319100` 代表 `31.91` 元；市价或撤单通常为 `0`） |
| **委托数量** | 整数 | 申报股数（如 `100` 代表 100 股） |

#### 逐笔委托枚举值速查表：

| 字段 | 代码 | 语义明文 | 业务解释 |
| :--- | :---: | :--- | :--- |
| **委托类型** | **`A`** | **新增委托 (Add)** | 新报单入队（限价或市价报单生效进入排队队列） |
| | **`D`** | **撤单委托 (Delete)** | 撤销原挂单（此时委托数量为撤单股数） |
| | **`S`** | **系统/状态 (Status)** | 产品状态变更、停复牌或开盘初始化通知 |
| **委托代码** | **`B`** | **买入申报 (Buy)** | 买方委托申报 |
| | **`S`** | **卖出申报 (Sell)** | 卖方委托申报 |
| | **`I`** | **盘前基准 (Init)** | 盘前初始化挂单基准 |
| | **`O`** | **集合竞价 (Open/Cross)** | 集合竞价或专有阶段申报 |

---

### 4.2 逐笔成交 (`逐笔成交.csv`)

记录撮合系统实际撮合成交或因撤单完成的每一笔逐笔流水。

| 字段名称 | 类型 | 说明与格式 |
| :--- | :---: | :--- |
| **代码** | 字符 | 标的代码（如 `605179.SH`） |
| **交易所代码** | 字符 | 交易所标的代码（如 `605179`） |
| **自然日** | 整数 | 交易日期（8 位整型，如 `20260817`） |
| **时间** | 整数 | 成交时间戳（毫秒级，格式 `HHMMSSmmm`，如 `92500020` 代表 `09:25:00.020`） |
| **成交编号** | 整数 | 撮合成交流水号（顺序递增） |
| **成交代码** | 字符 | 成交属性（正常成交为空或 `\0`；**`C`** 代表撤单成交） |
| **委托代码** | 字符 | 对应撮合委托属性 |
| **BS标志** | 字符 | **主动买卖方向（内外盘标志）**（详见下表） |
| **成交价格** | 整数 | 成交单价（定点整数，**需除以 10000 换算为元**，如 `324200` 代表 `32.42` 元） |
| **成交数量** | 整数 | 实际成交股数（如 `200` 代表 200 股） |
| **叫卖序号** | 整数 | 卖方对应的交易所委托号（可关联逐笔委托） |
| **叫买序号** | 整数 | 买方对应的交易所委托号（可关联逐笔委托） |

#### 逐笔成交枚举值速查表：

| 字段 | 代码 | 语义明文 | 业务解释 |
| :--- | :---: | :--- | :--- |
| **BS标志** | **`B`** | **主动买入 (外盘 / Buy)** | 成交由买方以卖一价或更高价格主动吃单触发，反映多头资金主动进场 |
| | **`S`** | **主动卖出 (内盘 / Sell)** | 成交由卖方以买一价或更低价格主动砸盘触发，反映空头资金主动卖出 |
| | 空格或 `\0` | **集合竞价 / 无明确方向** | 9:25 开盘集合竞价或尾盘撮合集中产生的成交记录 |
| **成交代码** | 空格或 `\0` | **正常撮合成交** | 双边挂单撮合匹配成功并扣减挂单队列 |
| | **`C`** | **撤单成交 (Cancel)** | 撤单行为引起的撮合状态记录 |

---

### 4.3 盘口深度切片 (`行情.csv`)

高频全景行情快照，按固定频度（每 3 秒或有异动时）汇总输出盘口状态。

| 核心字段分类 | 字段名称 | 说明 |
| :--- | :--- | :--- |
| **基本信息** | `代码`, `交易所代码`, `自然日`, `时间` | 标的标识与毫秒时间戳（`HHMMSSmmm`） |
| **价格量额** | `成交价`, `最高价`, `最低价`, `开盘价`, `前收盘` | 价格字段均为定点整型，**除以 10000 即为实际元** |
| | `成交量`, `成交额`, `成交笔数`, `当日累计成交量`, `当日成交额` | 当日累计与当前切片分时成交统计 |
| **十档盘口** | `申买价1` ~ `申买价10`，`申买量1` ~ `申买量10` | 完整十档委买排队价（除以 10000）与挂单量（股） |
| | `申卖价1` ~ `申卖价10`，`申卖量1` ~ `申卖量10` | 完整十档委卖排队价（除以 10000）与挂单量（股） |
| **加权统计** | `加权平均叫买价`, `加权平均叫卖价` | 队列加权均价（除以 10000） |
| | `叫买总量`, `叫卖总量` | 全市场委买总手数与委卖总手数 |

---

## 5. 早盘集合竞价 (09:15-09:25:03) 归档数据接口

系统每日归档全市场所有标的（7800+ 交易品种）在 09:15:00 至 09:25:03 期间的逐笔委托、逐笔成交与开盘千档排盘。接口提供 HTTP 分块流式传输（Transfer-Encoding: chunked，NDJSON 格式）。

---

### 5.1 早盘竞价可用日期列表

获取全市场已归档入库的早盘集合竞价交易日列表。

- **请求路径**：`GET /d5/auction/d203/dates`
- **请求参数**：无

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/auction/d203/dates
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "source": "d203",
    "total": 1,
    "dates": [
      20261019
    ]
  }
}
```

---

### 5.2 全市场早盘竞价标准化流式接口 (NDJSON Stream)

流式接收全市场所有标的早盘竞价明细，每行输出一条标准 NDJSON 记录。

> - **单日全量流式**：本接口严格按日期 `date` 一次性获取全市场流，不支持单只标的参数（若传入 `code` 或 `stock` 返回 400 拒绝）。
> - **发布时效与自动等待**：当天的全部竞价数据大约在 **09:25:25** 出现可下载。若在 09:15–09:40 提前发起请求，连接将自动保持活跃并下发等待心跳，数据就绪后直接顺畅推流。

- **请求路径**：`GET /d5/auction/d203/stream`
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `date` | integer / string | 否 | 8 位交易日代码，留空默认获取当天交易日 | `20261020` |
| `wait` | boolean / integer | 否 | 强制等待开关（`1` 或 `true`）。盘中 09:15-09:40 默认自动开启等待 | `1` |

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/auction/d203/stream
GET http://127.0.0.1:8080/d5/auction/d203/stream?date=20261020
```

#### 响应格式 (application/x-ndjson; charset=utf-8)
每行一个独立的标准化 D203 JSON 记录（外层为 `{"ts": ..., "list": [ ... ]}` 标准信封，业务属性统一收敛在内包）：
1. **状态通知 (`type="msg"`)**：
   - **连接建立时**：代理即刻下发正在同步提示及数据大小：`{"ts":...,"list":[{"date":20261020,"action":"push","type":"msg","message":"正在同步早盘竞价数据，数据大小 69.28MB","code":0}]}`
   - **全部推送完毕时**：流末尾下发推送完成通知：`{"ts":...,"list":[{"date":20261020,"action":"push","type":"msg","message":"全部8156只数据已推完","code":0}]}`
2. **逐笔委托 (`type="entrust"`)**：包含竞价阶段全部委托申报明细。
3. **逐笔成交 (`type="trade"`)**：包含竞价阶段全部撮合成交明细。
4. **全息队列 (`type="fullqueue"`)**：包含 09:25 集合竞价结束时的买卖深度队列排盘（`buy` / `sell` 数组）。

```json
{"ts":1729301106000,"list":[{"date":20261020,"action":"push","type":"msg","message":"正在同步早盘竞价数据，数据大小 69.28MB","code":0}]}
{"ts":1729301106000,"list":[{"date":20261020,"action":"push","type":"entrust","symbol":"SZ000007","code":"000007","market_id":0,"total_num":11886,"rows":[...]}]}
{"ts":1729301106000,"list":[{"date":20261020,"action":"push","type":"trade","symbol":"SZ000007","code":"000007","market_id":0,"total_num":10812,"rows":[...]}]}
{"ts":1729301106000,"list":[{"date":20261020,"action":"push","type":"fullqueue","symbol":"SZ000007","code":"000007","market_id":0,"buy":[{"price":...,"order_count":...,"queue":[...]}],"sell":[...]}]}
{"ts":1729301106000,"list":[{"date":20261020,"action":"push","type":"msg","message":"全部8156只数据已推完","code":0}]}
```

#### Python 流式消费示例（开箱即用，流式按行消费）

```python
import json
import requests

def stream_auction_market(date_str: str):
    """
    全市场早盘竞价数据流式消费者：
    - 直接从本地代理获取标准化流 (NDJSON)
    - 流式接收三大业务类型 (entrust / trade / fullqueue)
    """
    url = f"http://127.0.0.1:8080/d5/auction/d203/stream?date={date_str}"
    with requests.get(url, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                frame = json.loads(line)
                for item in frame.get("list", []):
                    action_type = item.get("type")      # "msg" | "entrust" | "trade" | "fullqueue"
                    if action_type == "msg":
                        print(f"[系统提示] {item.get('message')}")
                        continue
                    date_val = item.get("date")
                    symbol = item.get("symbol")        # 如 "SZ000007", "SH600519"
                    yield symbol, action_type, item

if __name__ == "__main__":
    for symbol, action_type, item in stream_auction_market("20261020"):
        if action_type == "fullqueue":
            print(f"[{symbol}] 开盘千档: 买 {len(item.get('buy', []))} 档, 卖 {len(item.get('sell', []))} 档")
            break
```

---

## 6. 全日高频逐笔 (09:15-15:00) 归档数据接口

系统每日盘后自动归档全市场所有股票标的（动态全市场 8000+ 品种）自 09:15:00 至 15:00:00 的全量逐笔委托与逐笔成交高频数据。

核心运行契约：
- **三态守恒律**：$\text{total} \equiv \text{len}(\text{ready}) + \text{len}(\text{empty}) + \text{len}(\text{pending})$。
  - `ready`：有交易数据且已完成云端归档，可供即时极速下载。
  - `empty`：全天停牌或无委托/成交记录的标的，自然排查收录，不额外消耗网络带宽。
  - `pending`：排队等待采集处理中。
- **纯内存流式处理**：客户端代理采用内存解压与分块流式传输（`application/x-ndjson`），零临时磁盘占用，零内存持久缓存负担。
- **全量时序保真输出**：原生直出全量逐笔委托与逐笔成交时序复合流，100% 保留撮合先后微秒级交织关系。

---

### 6.1 全天逐笔可用日期列表

获取已归档入库的全天逐笔交易日列表。

- **请求路径**：`GET /d5/fullday/d203/dates`
- **请求参数**：无

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/fullday/d203/dates
```

#### 响应示例
```json
{
  "code": 200,
  "dates": [
    20261021
  ],
  "message": "success"
}
```

---

### 6.2 当日股票三态清单

查询指定日期全市场所有股票的状态划分与收录进度。

- **请求路径**：`GET /d5/fullday/d203/stocks`
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `date` | integer / string | **是** | 8 位交易日代码 | `20261021` |

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/fullday/d203/stocks?date=20261021
```

#### 响应示例
```json
{
  "code": 200,
  "date": 20261021,
  "status": "done",
  "total": 8160,
  "ready_num": 5120,
  "empty_num": 3040,
  "pending_num": 0,
  "ready": [
    "SH600519",
    "SZ300750"
  ],
  "empty": [],
  "pending": []
}
```

---

### 6.3 单股全天逐笔提取

提取指定标的全天（09:15:00 至 15:00:00）的逐笔委托与逐笔成交高频明细。以 NDJSON（换行符分隔的 JSON）流式返回。

- **请求路径**：`GET /d5/fullday/d203/stock`
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `date` | integer / string | **是** | 8 位交易日代码 | `20261021` |
| `symbol` | string | **是** | 带市场前缀的标的代码（如 `SH600519`, `SZ300750`）或纯 6 位代码 | `SH600519` |

#### 请求示例
```text
GET http://127.0.0.1:8080/d5/fullday/d203/stock?date=20261021&symbol=SH600519
```

#### 响应示例（NDJSON，每行一条标准 JSON 对象）
```json
{"ts":1792571817730,"list":[{"date":20261021,"action":"push","type":"entrust","symbol":"SH600519","code":"600519","market_id":1,"name":"贵州茅台","precise":2,"unit":100,"is_begin":true,"statistics":{"buy_volume":5144569,"sell_volume":5307529,"buy_order_count":27316,"sell_order_count":29822,"buy_cancel_count":8528,"sell_cancel_count":9091},"total_num":57138,"rows":[{"time":91500,"seq":1,"order_no":197,"price":133500,"volume":100,"direction":1,"status":1,"volume_code":3,"flags":2}]}]}
{"ts":1792571817740,"list":[{"date":20261021,"action":"push","type":"trade","symbol":"SH600519","code":"600519","market_id":1,"name":"贵州茅台","precise":2,"unit":100,"is_begin":true,"statistics":{"buy_volume":1256000,"sell_volume":1341000},"total_num":38421,"rows":[{"time":92500,"seq":1,"trade_no":1024,"price":133500,"volume":12000,"buy_no":197,"sell_no":821,"active_flag":1}]}]}
```

#### 字段解释
- `ts`：毫秒时间戳。
- `list[].date`：交易日期（如 `20261021`）。
- `list[].type`：`"entrust"` 为逐笔委托，`"trade"` 为逐笔成交。
- `list[].statistics`：全天委托/成交汇总统计指标（买入/卖出委托总量、委托笔数、撤单笔数）。
- `list[].rows[]`：逐笔明细数组：
  - `time`：时分秒（如 `91500` 代表 09:15:00）。
  - `seq`：流水序号。
  - `price`：委托或成交单价（定点整数，需除以 $10^{\text{precise}}$，通常为 100，即分换算为元）。
  - `volume`：委托或成交股数。
  - `direction`：买卖方向（1=买，2=卖）。
  - `status`：委托或成交状态（含撤单标识）。

---

## 7. Python 量化接入示例

下面是标准的量化 Python 脚本，展示如何从本地代理拉取数据并快速转换为 Pandas DataFrame。代码内置了针对 `HTTP 429` 频率限制的自适应重试逻辑：

```python
import io
import time
import requests
import pandas as pd

BASE_URL = "http://127.0.0.1:8080"

def request_with_retry(url: str, params: dict = None, timeout: int = 30, max_retries: int = 5):
    """
    通用请求封装：支持自适应流控退避重试 (处理 429 Too Many Requests)
    """
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            # 读取服务端返回的建议退避等待秒数 (默认退避 1 秒)
            retry_data = resp.json().get("data", {})
            wait_sec = retry_data.get("retry_after_seconds", 1)
            print(f"[429 触发限频] 等待 {wait_sec} 秒后自动重试 (第 {attempt+1}/{max_retries} 次)...")
            time.sleep(wait_sec)
        else:
            resp.raise_for_status()
    raise RuntimeError(f"请求失败，已达到最大重试次数 ({max_retries}): {url}")

def get_available_dates():
    """获取所有可用交易日"""
    data = request_with_retry(f"{BASE_URL}/d5/l2plus/dates", timeout=10)
    return data["data"]["dates"]

def get_stocks_by_date(date: int, market: str = ""):
    """获取指定交易日的股票代码列表"""
    params = {"date": date}
    if market:
        params["market"] = market
    data = request_with_retry(f"{BASE_URL}/d5/l2plus/stocks", params=params, timeout=15)
    return data["data"]["codes"]

def get_stock_depth_data(date: int, code: str):
    """
    获取单只股票全量深度数据并转换为 DataFrame 字典
    返回包含：'行情', '逐笔成交', '逐笔委托' 的 DataFrame (数值列已由 C 引擎自动推断为 float/int)
    """
    params = {"date": date, "code": code}
    result = request_with_retry(f"{BASE_URL}/d5/l2plus/stock", params=params, timeout=30)

    dfs = {}
    for filename, csv_content in result.get("files", {}).items():
        name = filename.replace(".csv", "")
        # 解析为 DataFrame
        df = pd.read_csv(io.StringIO(csv_content))
        dfs[name] = df

    return dfs

if __name__ == "__main__":
    # 1. 检查最新可用日期
    dates = get_available_dates()
    print(f"当前归档可用交易日数量: {len(dates)}, 最新日期: {dates[0] if dates else '无'}")

    target_date = dates[0] if dates else 20260930
    target_stock = "600519.SH"

    print(f"\n正在提取 {target_date} {target_stock} 深度高频数据...")
    data_dict = get_stock_depth_data(target_date, target_stock)

    for name, df in data_dict.items():
        print(f"\n[{name}] 数据形状: {df.shape}")
        print(df.head(3))

    # 2. 利用枚举代码直接进行量化策略过滤（原生极速匹配）
    if "逐笔成交" in data_dict:
        df_trades = data_dict["逐笔成交"]
        # 筛选主动买入成交（外盘：BS标志 == 'B'）
        active_buys = df_trades[df_trades["BS标志"] == "B"]
        print(f"\n[量化示例] 全天主动买入笔数: {len(active_buys)}")

    if "逐笔委托" in data_dict:
        df_orders = data_dict["逐笔委托"]
        # 筛选撤单委托（委托类型 == 'D'）
        cancels = df_orders[df_orders["委托类型"] == "D"]
        print(f"[量化示例] 全天撤单委托笔数: {len(cancels)}")
```

---

## 8. 错误代码说明

| HTTP 状态码 | 业务 Code | 说明 | 常见排查方法 |
| :--- | :--- | :--- | :--- |
| `200` | `200` | 成功 | 请求处理正常 |
| `400` | `400` | 参数错误 | 缺少必要的 `date`、`code` 或 `symbol` 参数 |
| `403` | `403` | 权限不足 | 当前账号未开通 D5 产品权限 |
| `404` | `404` | 数据未收录 | 指定交易日或股票代码暂未归档完成 / 全天停牌 |
| `429` | `429` | 触发频率限制 | 开盘期间（08:00–16:00）限制 QPS=1，其余闲时 QPS=100。请依 `Retry-After` 退避重试 |
| `500` | `500` | 处理失败 | 数据解码或格式处理异常 |
| `502` | `502` | 服务暂不可用 | 网络传输超时或远端服务临时不可用，建议稍后重试 |
| `503` | `503` | 服务未就绪 | 本地代理服务尚未完成初始化配置 |

---

## 9. 调用频率与流控策略 (Rate Limit)

服务端采用基于北京时间（CST / UTC+8）的多租户分时段令牌桶流控，不同时段适用不同的频率上限：

### 9.1 分时段频率对照表

| 时段 (北京时间) | 日期类型 | 最大频率 (QPS) | 突发容量 (Burst) | 适用场景与建议 |
| :--- | :--- | :--- | :--- | :--- |
| **08:00 – 16:00** | 交易日 (周一至周五) | **1 次/秒** | 2 | 实盘开盘核心时段，仅建议用于单只个股抽样排查或低频告警；严禁盘中启动全市场多线程批量爬取 |
| **16:00 – 次日 08:00** | 交易日盘后及夜间 | **100 次/秒** | 120 | 历史数据回测、多进程/多线程并发批量拉取；全天 5000+ 标的数据数十秒即可完成检索 |
| **全天 (00:00 – 24:00)** | 周末及法定节假日 | **100 次/秒** | 120 | 休息日全天开放极速通道，适合全量离线数据仓库构建与策略深度训练 |

### 9.2 429 超频响应与退避规范

当短时间内调用频率超出当前时段上限时，服务端将立即拦截并返回 `HTTP 429 Too Many Requests`。

- **HTTP 响应头**：携带标准 `Retry-After: <秒数>`（通常为 1）。
- **HTTP 响应体**：返回包含具体流控参数的标准 JSON：
  ```json
  {
    "code": 429,
    "message": "rate limit exceeded: during trading hours (08:00-16:00) max QPS is 1, off-peak max QPS is 100. please retry after 1s",
    "data": {
      "limit_qps": 1,
      "retry_after_seconds": 1
    }
  }
  ```
- **字段解释**：
  - `limit_qps`：当前时段生效的最大 QPS 阈值（开盘时段为 `1`，夜间及周末为 `100`）。
  - `retry_after_seconds`：建议等待重试的休眠秒数（通常休眠 1 秒后即可恢复正常消费）。

### 9.3 高并发批量拉取最佳实践

1. **错峰执行批量任务**：
   - 如果您的策略需要下载全市场数千只股票的历史 Level 2 数据，**强烈建议安排在交易日 16:00 之后运行定时任务**（或周末运行）。
   - 在 100 QPS 极速通道下，拉取一个交易日全市场 5000+ 只股票的数据仅需约 50 秒，效率提升百倍。
2. **多线程并发控制**：
   - 夜间或周末进行批量采集时，建议客户端采用 `10` ~ `20` 个并发工作线程或协程，配合轻量令牌桶控制总体并发在 80~90 QPS，即可在不触发 429 的前提下实现吞吐量最大化。
3. **自适应退避容错**：
   - 生产环境脚本请务必封装对 `429` 状态码的重试处理（参考 [第 7 节 Python 量化接入示例](#7-python-量化接入示例) 中的 `request_with_retry` 函数），遇到 429 时休眠 `retry_after_seconds` 秒再自动重试，保证批处理任务无人值守、永不断流。
