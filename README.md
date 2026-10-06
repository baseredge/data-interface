# Data Interface (量化高频行情网关与深度复盘系统)

> 🎯 **面向 QMT、PTrade、vn.py、Python 量化策略与行情推流的高性能轻量化本地代理中间件**  
> ⚡ **现代 C++23 极致内核，实测常驻运行内存仅 ~5MB，亚毫秒级低延迟吞吐**

[![Release](https://img.shields.io/github/v/release/baseredge/data-interface?color=blue&label=Latest%20Release)](https://github.com/baseredge/data-interface/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen)]()
[![Memory Footprint](https://img.shields.io/badge/Memory%20Footprint-~5MB%20Resident-success)]()
[![Ecosystem](https://img.shields.io/badge/Ecosystem-QMT%20%7C%20PTrade%20%7C%20vn.py%20%7C%20MQTT-red)]()
[![Protocol](https://img.shields.io/badge/Protocol-HTTP%20%2F%20WebSocket-orange)]()

`Data Interface` 是专为量化对冲基金、日内高频团队、策略研发人员打造的本地行情中继与微结构复盘引擎。系统采用现代 **C++23** 全异步零拷贝架构，将复杂的私有长连接与高频二进制协议在本地转换为标准 **WebSocket JSON 实时流** 与 **HTTP RESTful API**。

无论实盘执行还是盘后复盘，告别笨重的数据库与臃肿环境，以**仅 ~5MB 的极低系统开销**，提供覆盖实盘高频推流与深度盘口还原的一站式基建支持。

---

## 🔥 量化团队刚需能力矩阵

### 1. 🎞️ D3：3秒级高精盘口现场还原（量化复盘与微结构回溯利器）
做日内 T+0、打板封单研究或高频微结构的量化团队，最核心的痛点是**“盘后无法精准还原当时盘口的真实交战细节”**。
- **3秒级高频切片回放**：完整重构当日历史盘口的每一个切片（Tick 快照）与逐笔成交轨迹（Deal 明细）。
- **微观博弈精准溯源**：每一笔挂单推进、撤单异动、大单吃单与炸板瞬间的量价微结构 100% 还原，彻底告别粗颗粒度的分时线“盲人摸象”。
- **免维护即开即查**：无需自建昂贵且维护繁琐的 Tick 级历史数据库，通过标准 HTTP API 传入日期与标的代码，秒级返回整日高精微结构切片。

### 2. 🌊 D2：主力资金博弈与多维形态数据中心（把握趋势与真假突破）
为趋势跟踪、形态识别、主力意图判定提供全维度的深度量化因子库：
- **全天 240 根连续主力资金流序列**：提供超大单、大单、中单、小单分档净额，精准穿透主力真实吸筹与派发轨迹，识别“指数虚涨、主力暗中撤退”等背离形态。
- **连板梯队与涨停股池生态**：涵盖实时涨停池、连板晋级梯队、首板挖掘、炸板回封统计与封单资金强度，量化短线情绪周期。
- **龙虎榜席位与主力动向透视**：机构专用席位买卖净额、知名游资营业部协同作战动向全记录。
- **微观筹码与市场热度**：北向互联互通资金实时流向、股东户数筹码集中度跃迁、全市场热点板块梯队轮动。

### 3. ⚡ 毫秒级实盘行情推流（D101 / D201 / D204）
- **逐笔成交（Tick Execution）与逐笔委托（Order Detail）全量实时推送**，订单生命周期清晰可溯。
- **十档买卖盘口（Depth 10 Orderbook）毫秒级增量更新**，严格维护递增序列号（SeqNum），防止策略丢包。

---

## 🔌 主流量化生态即插即用

无论使用券商实盘客户端还是自研算法交易总线，均可极速接入：

- **迅投 QMT / xtquant 极简量化协同**
  - 为 QMT 实盘策略注入外部高刷新率的十档盘口与逐笔成交，突破默认行情在深度与频次上的限制，大幅优化挂单撮合与日内策略滑点。
- **恒生 PTrade 策略联动**
  - 作为独立外部行情报送源协同运行，捕捉毫秒级盘口异动并驱动条件单极速触发。
- **vn.py (vnpy) 开源量化框架**
  - 极简 WebSocket JSON 协议，可快速封装为 vn.py 自定义行情网关，驱动 CTA 策略引擎与微观阿尔法算法。
- **MQTT / 消息总线分布式组播**
  - 配合轻量 Python 脚本一键转发至 MQTT Broker（如 EMQX、Mosquitto），实现多台交易服务器、多账户、多子策略的内网低延迟分发。

---

## 💻 极致性能与零持久化设计

- **实测常驻内存仅 ~5MB**：拒绝 Electron、Python 运行时动辄数百兆的内存消耗，即使在最低配置的云服务器或老旧终端上亦可常年轻量静默运行。
- **纯内存运行 (Zero-Persistence)**：采用纯内存环形缓冲区设计，**严禁向本地磁盘写入任何网络缓存文件**，绿色轻量，永不产生磁盘碎片或数据残留。
- **三平台绝对一致的原生控制台**：跨 Windows (Win32 GDI)、macOS (Cocoa)、Linux (GTK) 三端提供 100% 结构与逻辑一致的原生极简管理窗口，自带状态健康探针。

---

## 🚀 快速上手 (Quick Start)

### 1. 下载与运行
前往 [Releases 页面](https://github.com/baseredge/data-interface/releases) 下载适合您操作系统的绿色免安装包（如 `data_interface_win_amd64.zip`）。

解压后直接启动：
- **Windows**: 双击 `data_interface.exe`
- **Linux / macOS**: `./data_interface`

默认本地监听：
- **业务数据服务端口**：`http://127.0.0.1:8080`
- **管理控制台与探针**：`http://127.0.0.1:9527`

### 2. Python 示例：调用 D3 历史微结构复盘数据

```python
import requests

# 调取指定交易日与标的的完整微结构复盘切片
resp = requests.get(
    "http://127.0.0.1:8080/d3/history",
    params={"date": "20250508", "id": "SZ002306"},
    timeout=30
)
data = resp.json()

# 包含整日高精分时 tick 切片与逐笔 deal 成交序列
segments = data.get("segments", [])
print(f"复盘数据加载完成，共获取 {len(segments)} 个高精分段")
```

### 3. Python 示例：实时订阅 D204 毫秒级逐笔与十档推流

```python
import asyncio
import json
import websockets

async def subscribe_orderbook():
    uri = "ws://127.0.0.1:8080/d204"
    async with websockets.connect(uri) as ws:
        # 订阅目标标的高频数据
        await ws.send(json.dumps({"action": "subscribe", "symbols": ["000001", "600519"]}))
        print("订阅成功，实时行情流推送中...")

        while True:
            msg = await ws.recv()
            tick = json.loads(msg)
            # 包含：毫秒时间戳, 序列号, 逐笔成交/委托, 十档买卖盘口深度
            print(f"收到推送 [{tick.get('type')}]: {tick}")

if __name__ == "__main__":
    asyncio.run(subscribe_orderbook())
```

---

## 📚 接口协议目录

完整规范与示例代码已收录于 [`docs/`](./docs) 与 [`examples/`](./examples) 目录：

| 模块代码 | 通信协议 | 核心量化功能与应用场景 | 文档链接 |
| :--- | :--- | :--- | :--- |
| **`d3`** | HTTP | **3秒级盘口现场还原**：历史逐笔成交与分时切片微结构复盘 | [d3_http_api.md](./docs/d3_http_api.md) |
| **`d2`** | HTTP | **全维博弈中心**：连续主力资金流序列、连板梯队、龙虎榜与筹码 | [d2_http_api.md](./docs/d2_http_api.md) |
| **`d1`** | HTTP | **基础数据中心**：多周期K线、财务简况与全市场标的指标 | [d1_http_api.md](./docs/d1_http_api.md) |
| **`d4`** | HTTP | **资金流向异动**：板块资金轮动与实时热点监控 | [d4_http_api.md](./docs/d4_http_api.md) |
| **`d6`** | HTTP | **全市场快照**：高并发标的行情列表批量查询 | [d6_market_api.md](./docs/d6_market_api.md) |
| **`d204`** | WebSocket | **高频逐笔推流**：毫秒级逐笔成交 / 逐笔委托 / 十档盘口更新 | [d204_ws_api.md](./docs/d204_ws_api.md) |
| **`d101`** | WebSocket | **实时十档深度**：盘口毫秒级快照更新 | [d101_ws_api.md](./docs/d101_ws_api.md) |
| **`d201`** | WebSocket | **委托大单监控**：撤单异动与主力委托挂单捕获 | [d201_ws_api.md](./docs/d201_ws_api.md) |
| **`d202`** | WebSocket | **集合竞价深度**：9:15-9:25 开盘集合竞价动态推流 | [d202_ws_api.md](./docs/d202_ws_api.md) |

---

## ❓ 常见问题 (FAQ)

### Q: 为什么实测内存占用仅约 5MB？对服务器性能有何要求？
**A**: 本项目完全基于现代 C++23 编写，采用紧凑的数据结构、高效的无锁队列与就地内存解析，抛弃了一切冗余框架与重型解释器依赖。即便在最低配的 1核1G 云服务器上也能长期满负载稳定运行，CPU 与内存开销几乎可以忽略不计。

### Q: 如何将本系统的深度行情与迅投 QMT / PTrade 交易结合？
**A**: 在交易机器或内网启动本网关，策略脚本通过 WebSocket 连接本地 `8080` 端口订阅实时十档与逐笔推流，计算信号后直接调用 QMT (`xtquant`) 或 PTrade 的本地交易接口执行下单。将“极致的行情解析”与“券商原厂交易通道”分离，既能享受专业级盘口深度，又保留实盘交易的原生稳定性。

---

## 🔍 核心检索词与覆盖场景 (Keywords)

`量化复盘` | `微结构现场还原` | `主力资金流` | `趋势形态识别` | `十档盘口` | `逐笔成交` | `逐笔委托` | `涨停连板梯队` | `龙虎榜追踪` | `筹码集中度` | `迅投QMT` | `xtquant` | `恒生PTrade` | `vn.py` | `MQTT行情推流` | `WebSocket实时行情` | `高频量化交易` | `Python股票数据网关`

---

## 📄 授权与免责声明
本项目发布的二进制客户端与公开文档仅供量化策略研发、学术研究与技术交流使用。使用者应自行确保数据接入来源的合规性。
