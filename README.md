# Data Interface - A股高频 Level-2 行情接口代理中间件

> 🚀 **专为 QMT、PTrade、vn.py、Python 量化交易与 MQTT/WebSocket 推流打造的高性能 A 股行情网关**

[![Release](https://img.shields.io/github/v/release/baseredge/data-interface?color=blue&label=Latest%20Release)](https://github.com/baseredge/data-interface/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen)]()
[![Ecosystem](https://img.shields.io/badge/Ecosystem-QMT%20%7C%20PTrade%20%7C%20vn.py%20%7C%20MQTT-red)]()
[![Language](https://img.shields.io/badge/Language-C%2B%2B23-blue)]()
[![Protocol](https://img.shields.io/badge/Protocol-HTTP%20%2F%20WebSocket-orange)]()

`Data Interface` 是面向国内量化投资与高频交易团队研发的本地行情代理中间件。基于现代 **C++23** 编写，致力于解决量化实盘与回测中的核心痛点：将底层复杂的高频长连接与私有二进制行情流，在本地近源转换为标准化、极易接入的 **WebSocket JSON 实时推送流** 与 **HTTP RESTful API**。

---

## 🔌 主流量化生态无缝接入

无论您使用的是券商实盘交易终端还是自研量化回测框架，均可即插即用：

- **迅投 QMT / xtquant 极简量化接入**
  - 为 QMT 实盘策略注入外部独立的毫秒级 **Level-2 逐笔成交** 与 **十档盘口** 深度数据。
  - 突破 QMT 默认基础行情在档位、深度和刷新频率上的瓶颈，赋能日内回转（T+0）、大单监控与盘口微观结构策略。
- **恒生 PTrade 策略联动**
  - 作为独立外部行情驱动源，与 PTrade 交易终端协同运行，捕捉毫秒级盘口异动并驱动条件单触发。
- **vn.py (vnpy) 开源交易框架**
  - 采用极简 WebSocket JSON 格式，可轻松封装为 vn.py 的自定义行情网关（`DataInterfaceGateway`），直接驱动 CTA 策略引擎与微结构算法。
- **MQTT / 消息队列总线分发**
  - 配合轻量 Python 脚本即可一键转推至 MQTT Broker（如 EMQX、Mosquitto），实现多台交易服务器、多账户、多子策略的内网低延迟组播与分发。

---

## ✨ 核心特性

- **⚡ 毫秒级 Level-2 深度行情推流**
  - **逐笔成交（Tick Execution）** 与 **逐笔委托（Order Detail）** 全量推送。
  - **十档买卖盘口（Depth 10 Orderbook）** 毫秒级快照更新。
  - 严格维护递增序列号（SeqNum），丢包、断线与时序乱序可精准自检。
- **🌐 统一标准协议双栈**
  - **WebSocket 实时推流**：标准 JSON 数据流，下游 Python / Go / C++ / C# / Node.js 均可秒级解析。
  - **HTTP RESTful 接口**：涵盖全市场行情快照、历史K线（分时/日/周）、资金流向、板块热点与综合数据。
- **🛡️ 纯内存运行与零磁盘垃圾 (Zero-Persistence)**
  - 采用纯内存环形缓冲区架构，**严禁向本地磁盘写入任何无用的网络缓存文件**，绿色轻量，永不产生磁盘碎片。
- **💻 三端原生统一管理控制台**
  - 支持 Windows (Win32 GDI)、macOS (Cocoa) 与 Linux (GTK) 三大平台，拥有 100% 绝对一致的原生管理界面。运行内存常驻仅 ~15MB，附带本地状态监控探针。

---

## 🏗️ 架构拓扑

```text
[ 量化交易终端 / 策略系统 ]
  ├── 迅投 QMT / xtquant
  ├── 恒生 PTrade
  ├── vn.py 开源框架
  └── 自研 Python/C++ 策略 ────► MQTT Broker (可选)
             │
             │ HTTP (8080) / WebSocket (/d101, /d201~/d204)
             ▼
┌────────────────────────────────────────────────────────┐
│           Data Interface (本地高性能代理中间件)           │
│  - 纯内存运行 (Zero Disk Pollution)                    │
│  - C++23 异步事件驱动内核                             │
│  - 原生桌面控制台 (Windows / macOS / Linux)            │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 快速上手 (Quick Start)

### 1. 下载与运行
前往 [Releases 页面](https://github.com/baseredge/data-interface/releases) 下载适合您系统的最新绿色免安装发行包（如 `data_interface_win_amd64.zip`）。

解压后直接启动：
- **Windows**: 双击 `data_interface.exe`
- **Linux / macOS**: `./data_interface`

服务启动后，默认在本地监听：
- **业务数据端口**：`http://127.0.0.1:8080`
- **本地管理探针**：`http://127.0.0.1:9527`

### 2. Python 快速订阅示例 (Level-2 实时推流)

```python
import asyncio
import json
import websockets

async def subscribe_level2():
    # 连接本地行情通道 (以 d204 通道为例)
    uri = "ws://127.0.0.1:8080/d204"
    async with websockets.connect(uri) as ws:
        # 订阅指定股票标的的逐笔与十档盘口
        sub_msg = {
            "action": "subscribe",
            "symbols": ["000001", "600519"]
        }
        await ws.send(json.dumps(sub_msg))
        print("订阅成功，等待高频行情推送...")

        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            # data 包含: 股票代码, 时间戳, 序列号, 逐笔成交/委托明细, 十档买卖盘口
            print(f"收到推送 [{data.get('type')}]: {data}")

if __name__ == "__main__":
    asyncio.run(subscribe_level2())
```

### 3. QMT / MQTT 联动模式示例 (行情转推)

```python
import json
import asyncio
import websockets
# 可选配合 paho-mqtt 转推给局域网其他策略
# import paho.mqtt.client as mqtt

async def forward_to_quant():
    uri = "ws://127.0.0.1:8080/d204"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action": "subscribe", "symbols": ["000001"]}))
        while True:
            msg = await ws.recv()
            tick = json.loads(msg)
            # 此时可直接喂入 QMT 回调函数，或通过 MQTT 发送给分布式策略集群
            # mqtt_client.publish(f"stock/l2/{tick['symbol']}", msg)

if __name__ == "__main__":
    asyncio.run(forward_to_quant())
```

---

## 📚 接口协议目录

完整技术规范文档与各语言调用示例已开源在 [`docs/`](./docs) 与 [`examples/`](./examples) 目录：

| 模块代码 | 通信协议 | 业务功能说明 | 文档链接 |
| :--- | :--- | :--- | :--- |
| **`d1`** | HTTP | 基础行情、财务简况与综合指标查询 | [d1_http_api.md](./docs/d1_http_api.md) |
| **`d2`** | HTTP | 历史K线、分时成交与盘口明细 | [d2_http_api.md](./docs/d2_http_api.md) |
| **`d3`** | HTTP | 盘口与特色指标接口 | [d3_http_api.md](./docs/d3_http_api.md) |
| **`d4`** | HTTP | 资金流向与市场异动 | [d4_http_api.md](./docs/d4_http_api.md) |
| **`d6`** | HTTP | 全市场行情快照与标的列表 | [d6_market_api.md](./docs/d6_market_api.md) |
| **`d101`** | WebSocket | 实时十档深度快照推送 | [d101_ws_api.md](./docs/d101_ws_api.md) |
| **`d201`** | WebSocket | 实时委托异动与大单监控 | [d201_ws_api.md](./docs/d201_ws_api.md) |
| **`d202`** | WebSocket | 实时盘口集合竞价深度 | [d202_ws_api.md](./docs/d202_ws_api.md) |
| **`d204`** | WebSocket | 毫秒级逐笔成交 / 逐笔委托高频流 | [d204_ws_api.md](./docs/d204_ws_api.md) |

---

## ❓ 常见问题 (FAQ)

### Q: 如何与券商的迅投 QMT 或 PTrade 配合使用？
**A**: 在运行 QMT 或 PTrade 交易客户端的同台机器（或局域网服务器）启动本代理。您的 Python 策略脚本通过 WebSocket 连接本地 `8080` 端口订阅实时行情，同时调用 QMT 的 `xtquant` 或 PTrade 的交易接口执行下单，从而实现“极致行情报送 + 券商极速实盘”的高效配合。

### Q: 是否支持多进程、多策略客户端并发订阅？
**A**: 支持。本地代理内核基于现代 C++ 异步事件驱动模型打造，内置高效的内存分发与组播机制，支持数十个本地量化进程并发接入，吞吐延时在亚毫秒级别。

---

## 🔍 核心检索词与覆盖场景 (Keywords)

`A股行情接口` | `Level-2行情` | `L2数据` | `逐笔成交` | `逐笔委托` | `十档盘口` | `高频量化` | `量化交易` | `迅投QMT` | `xtquant` | `恒生PTrade` | `vn.py` | `MQTT行情分发` | `WebSocket行情推送` | `股票数据API` | `Python量化接口` | `A-share Level2 Gateway`

---

## 📄 授权与免责声明
本项目发布的二进制客户端与公开文档仅供技术研究、量化策略开发与学术交流使用。使用者应自行确保数据接入来源的合规性。
