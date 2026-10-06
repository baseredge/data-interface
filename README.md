# Data Interface (股票行情数据接口代理服务)

> 🚀 **面向高频量化交易与数据分析的高性能 A 股行情网关与协议代理中间件**

[![Release](https://img.shields.io/github/v/release/baseredge/data-interface?color=blue&label=Latest%20Release)](https://github.com/baseredge/data-interface/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen)]()
[![Language](https://img.shields.io/badge/Language-C%2B%2B23-blue)]()
[![Protocol](https://img.shields.io/badge/Protocol-HTTP%20%2F%20WebSocket-orange)]()

`Data Interface` 是基于现代 **C++23** 构建的高性能金融行情代理与协议转换服务。它将上游复杂的底层长连接与高频二进制数据流，无缝转换为量化策略极易接入的标准 **HTTP RESTful API** 与 **WebSocket JSON 实时推送流**。

---

## ✨ 核心特性

- **⚡ 毫秒级 Level-2 深度行情推流**
  - **逐笔成交（Tick Execution）** 与 **逐笔委托（Order Detail）** 全量推送。
  - **十档买卖盘口（Depth 10 Orderbook）** 毫秒级快照更新。
  - 自动维护递增序列号（SeqNum），丢包与断线可自检。
- **🌐 统一标准协议双栈**
  - **WebSocket 实时流**：采用精简优化的 JSON 数据格式，专为 Python / Go / Node.js 等下游策略系统设计。
  - **HTTP RESTful 接口**：覆盖基础日线/分时K线、历史明细、板块热点与综合数据查询。
- **🛡️ 纯内存运行与零磁盘垃圾 (Zero-Persistence)**
  - 运行时纯内存缓存，不向磁盘落盘任何无用的网络缓存或临时数据文件，绿色轻量。
- **💻 三端一致的原生桌面管理控制台**
  - 提供 Windows (Win32 GDI)、macOS (Cocoa) 与 Linux (GTK) 原生轻量桌面管理界面，日常内存占用低于 20MB。

---

## 🏗️ 系统架构

```text
[ 用户量化策略 (Python / C++ / Go) ]
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
前往 [Releases 页面](https://github.com/baseredge/data-interface/releases) 下载最新绿色发行包（如 `data_interface_win_amd64.zip`）。

解压后直接运行可执行文件：
- **Windows**: 双击 `data_interface.exe`
- **Linux / macOS**: `./data_interface`

服务启动后，默认在本地监听：
- **业务数据代理端口**：`http://127.0.0.1:8080`
- **管理控制台与探针**：`http://127.0.0.1:9527`

### 2. Python 快速订阅示例 (WebSocket Level-2 实时行情)

```python
import asyncio
import json
import websockets

async def subscribe_level2():
    # 连接本地行情通道 (以 d204 通道为例)
    uri = "ws://127.0.0.1:8080/d204"
    async with websockets.connect(uri) as ws:
        # 订阅指定股票代码的逐笔与十档数据
        sub_msg = {
            "action": "subscribe",
            "symbols": ["000001", "600519"]
        }
        await ws.send(json.dumps(sub_msg))
        print("订阅成功，等待行情推送...")

        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            print(f"收到推送 [{data.get('type')}]: {data}")

if __name__ == "__main__":
    asyncio.run(subscribe_level2())
```

---

## 📚 接口协议目录

完整技术文档与代码示例已分类存放于 [`docs/`](./docs) 与 [`examples/`](./examples) 目录：

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

### Q: 运行该程序需要配置额外的数据库吗？
**A**: 不需要。本程序基于 C++ 静态编译，绿色免安装，解压即用，无任何 Python/Node.js 运行时或数据库依赖。

### Q: 如何进行多策略客户端的高并发订阅？
**A**: 本地代理内核采用无锁异步队列与并发广播机制，单机轻松支撑数十个量化策略进程并发接入，吞吐延时在亚毫秒级。

---

## 📄 授权与免责声明
本项目发布的二进制客户端与公开文档仅供技术研究、量化策略开发与学术交流使用。使用者应自行确保数据接入来源的合规性。
