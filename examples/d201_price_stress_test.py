"""D201 单个价位 (price) 1000 并发压测脚本。

业务逻辑：
    1. 从 D4 HTTP 接口 (/d4/l1/instrument_list) 获取当日涨幅排名前 N（如 1000）只股票及其涨跌停价。
    2. 针对每只股票按涨停价压测：
       - 若已涨停 (price >= limit_up)：订阅买盘涨停价 (direction=0, priceCent=limit_up * 10)
       - 若未涨停 (price < limit_up)：订阅卖盘涨停价 (direction=1, priceCent=limit_up * 10)
    3. 启动多线程/并发 WebSocket 连接压测，统计连接成功率、首包到达率、后续持续推流率及吞吐量。

用法：
    # 快速试跑 20 只股票，跑 10 秒
    python d201_price_stress_test.py --count 20 --seconds 10

    # 全量 1000 股票并发压测 30 秒
    python d201_price_stress_test.py --count 1000 --seconds 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import websocket
except ImportError:
    print(
        "缺少 websocket-client，请先执行: python -m pip install websocket-client",
        file=sys.stderr,
    )
    raise

WS_URL = "ws://127.0.0.1:8080/d201"
D4_URL = "http://127.0.0.1:8080/d4/l1/instrument_list"


def fetch_top_stocks(d4_url: str, target_count: int = 1000) -> list[dict[str, Any]]:
    """从 D4 接口获取涨幅降序排列的前 target_count 只股票（过滤掉无涨停价的无涨跌幅股票）。"""
    # 每次请求最多 1000 条，若 target_count > 1000 则分页获取
    stocks: list[dict[str, Any]] = []
    skip = 0
    fetch_batch = min(1000, target_count + 100)

    while len(stocks) < target_count:
        params = (
            f"?universe=cn_hsj_stock&skip={skip}&count={fetch_batch}"
            f"&fields=code,name,price,change_pct,limit_up,limit_down&sort=4&order=0"
        )
        full_url = d4_url + params
        req = Request(full_url, headers={"User-Agent": "d201-stress-tester"})
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"请求 D4 接口失败: {exc}") from exc

        rows = data.get("rows", [])
        if not rows:
            break

        for r in rows:
            code = r.get("code", "")
            limit_up = int(r.get("limit_up") or 0)
            price = int(r.get("price") or 0)
            change_pct = float(r.get("change_pct") or 0) / 100.0
            name = r.get("name", "")

            # 过滤没有涨停价的无限制个股 (如上市首日新股)
            if limit_up <= 0:
                continue

            # 判断是否已涨停
            is_limit_up = (price >= limit_up)
            # D4 的 limit_up 单位为“分”，D201 priceCent 单位为“元×1000（厘）”，需乘以 10
            target_price_cent = limit_up * 10
            direction = 0 if is_limit_up else 1

            stocks.append({
                "code": code,
                "name": name,
                "price": price,
                "limit_up": limit_up,
                "change_pct": change_pct,
                "is_limit_up": is_limit_up,
                "direction": direction,
                "priceCent": target_price_cent,
            })
            if len(stocks) >= target_count:
                break

        skip += len(rows)
        if skip >= data.get("total", 0):
            break

    return stocks


def receive_one_stock(
    stock_info: dict[str, Any],
    ws_url: str,
    connect_timeout: float,
    recv_timeout: float,
    started_time: float,
    deadline_time: float,
) -> dict[str, Any]:
    code = stock_info["code"]
    direction = stock_info["direction"]
    price_cent = stock_info["priceCent"]

    result: dict[str, Any] = {
        "code": code,
        "name": stock_info["name"],
        "isLimitUp": stock_info["is_limit_up"],
        "direction": direction,
        "priceCent": price_cent,
        "status": "connect_failed",
        "connectSeconds": None,
        "firstDataSeconds": None,
        "frames": 0,
        "initialSnapshots": 0,
        "streamUpdates": 0,
        "errors": [],
    }

    ws = None
    try:
        t0 = time.monotonic()
        ws = websocket.create_connection(ws_url, timeout=connect_timeout)
        result["connectSeconds"] = round(time.monotonic() - t0, 3)
        result["status"] = "connected"
        ws.settimeout(recv_timeout)

        # 发送单个价位订阅命令
        sub_cmd = [{
            "type": "price",
            "code": code,
            "enable": 1,
            "direction": direction,
            "priceCent": price_cent,
            "userParam": 1,
        }]
        ws.send(json.dumps(sub_cmd, separators=(",", ":")))

        while time.monotonic() < deadline_time:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException as exc:
                result["status"] = "closed"
                result["errors"].append(str(exc))
                break

            if not raw:
                result["status"] = "closed"
                break

            result["frames"] += 1
            try:
                msg = json.loads(raw)
            except Exception as exc:
                result["errors"].append(f"JSON: {exc}")
                continue

            for item in msg.get("list", []):
                typ = item.get("type")
                if typ == "error":
                    result["errors"].append(str(item.get("msg", "未知错误")))
                elif typ == "price":
                    data = item.get("data") or {}
                    if data.get("code") != code:
                        continue

                    if result["firstDataSeconds"] is None:
                        result["firstDataSeconds"] = round(time.monotonic() - started_time, 3)

                    # 判断是初始快照还是后续增量变动推流
                    # 当 isFirst==1 或包含初始大批量委托 records 时为快照；后续为增量变动
                    if data.get("isFirst") == 1 or result["initialSnapshots"] == 0:
                        result["initialSnapshots"] += 1
                    else:
                        result["streamUpdates"] += 1

    except Exception as exc:
        result["errors"].append(str(exc))
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="D201 单个价位 (price) 1000 股票并发压测工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=1000, help="测试股票数量")
    parser.add_argument("--seconds", type=float, default=30.0, help="压测持续时间（秒）")
    parser.add_argument("--ws-url", default=WS_URL, help="D201 WebSocket 接口地址")
    parser.add_argument("--d4-url", default=D4_URL, help="D4 HTTP 股票列表接口地址")
    parser.add_argument("--connect-timeout", type=float, default=10.0, help="单连接握手超时")
    parser.add_argument("--recv-timeout", type=float, default=1.0, help="接收单帧超时")
    parser.add_argument("--workers", type=int, default=0, help="并发线程数 (默认等于股票数)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workers = args.workers if args.workers > 0 else args.count

    print(f"=== D201 单个价位 (price) 并发压测 ===")
    print(f"1. 正在从 D4 获取涨幅排名前 {args.count} 只股票行情参数...")
    t_start_fetch = time.monotonic()
    stocks = fetch_top_stocks(args.d4_url, args.count)
    print(f"   已获取 {len(stocks)} 只有效股票 (耗时 {time.monotonic() - t_start_fetch:.2f}s)")

    limit_up_cnt = sum(1 for s in stocks if s["is_limit_up"])
    non_limit_cnt = len(stocks) - limit_up_cnt
    print(f"   - 已涨停 (测买盘涨停价 direction=0): {limit_up_cnt} 只")
    print(f"   - 未涨停 (测卖盘涨停价 direction=1): {non_limit_cnt} 只")

    print(f"\n2. 开始建立 {len(stocks)} 个 WebSocket 连接并发压测...")
    print(f"   目标地址: {args.ws_url}")
    print(f"   压测时长: {args.seconds} 秒")
    print(f"   线程池大小: {workers}")

    started_wall = datetime.now().astimezone().isoformat(timespec="seconds")
    started_mono = time.monotonic()
    deadline_mono = started_mono + args.seconds

    results: list[dict[str, Any]] = []
    completed_cnt = 0

    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="price_stress") as pool:
            futures = [
                pool.submit(
                    receive_one_stock,
                    stk,
                    args.ws_url,
                    args.connect_timeout,
                    args.recv_timeout,
                    started_mono,
                    deadline_mono,
                )
                for stk in stocks
            ]

            for index, fut in enumerate(as_completed(futures), 1):
                res = fut.result()
                results.append(res)
                completed_cnt += 1
                if completed_cnt % 50 == 0 or completed_cnt == len(stocks):
                    print(f"   [进度] 已结束 {completed_cnt}/{len(stocks)} 个连接测试...", flush=True)

    except KeyboardInterrupt:
        print("\n[中断] 用户手动按 Ctrl+C 停止测试，汇总已有数据...", file=sys.stderr)

    # 统计指标
    connected = [r for r in results if r["status"] in {"connected", "closed"}]
    had_data = [r for r in results if r["initialSnapshots"] > 0 or r["streamUpdates"] > 0]
    had_stream = [r for r in results if r["streamUpdates"] > 0]
    total_frames = sum(r["frames"] for r in results)
    total_stream_updates = sum(r["streamUpdates"] for r in results)
    total_snapshots = sum(r["initialSnapshots"] for r in results)

    # 计算平均首包延迟
    first_latencies = [r["firstDataSeconds"] for r in results if r["firstDataSeconds"] is not None]
    avg_first_latency = (sum(first_latencies) / len(first_latencies)) if first_latencies else 0.0

    print("\n" + "=" * 50)
    print("                 压测结果汇总")
    print("=" * 50)
    print(f"目标股票数:       {len(stocks)}")
    print(f"连接成功数:       {len(connected)} / {len(stocks)} ({len(connected)/len(stocks)*100:.1f}%)")
    print(f"收到首包数据数:   {len(had_data)} / {len(stocks)} ({len(had_data)/len(stocks)*100:.1f}%)")
    print(f"收到持续推流数:   {len(had_stream)} / {len(stocks)} ({len(had_stream)/len(stocks)*100:.1f}%)")
    print(f"平均首包到达延迟: {avg_first_latency:.3f} 秒")
    print(f"收到总帧数:       {total_frames} 帧")
    print(f"初始快照总数:     {total_snapshots} 帧")
    print(f"持续增量推流总数: {total_stream_updates} 帧")
    print(f"平均推流吞吐率:   {total_frames / args.seconds:.1f} 帧/秒")

    # 错误汇总
    errors = [e for r in results for e in r["errors"]]
    if errors:
        print(f"\n错误总数: {len(errors)} (前 5 条如下):")
        for err in errors[:5]:
            print(f"  - {err}")
    else:
        print("\n无任何连接或解析错误！")

    # 输出落盘
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = Path(__file__).resolve().parent / f"d201_price_stress_result_{stamp}.json"
    summary = {
        "targetCount": len(stocks),
        "durationSeconds": args.seconds,
        "workers": workers,
        "connectedCount": len(connected),
        "hadDataCount": len(had_data),
        "hadStreamCount": len(had_stream),
        "totalFrames": total_frames,
        "totalSnapshots": total_snapshots,
        "totalStreamUpdates": total_stream_updates,
        "avgFirstDataSeconds": round(avg_first_latency, 3),
        "startedAt": started_wall,
        "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "perStock": results,
    }
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细统计报告已保存至: {out_file.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
