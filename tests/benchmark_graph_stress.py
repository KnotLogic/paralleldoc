"""
Empirical Benchmark: Graph Cycle Tolerance & Scale Stress.
Author: Challenger M1-2
Measures runtime and memory scaling across varying node counts.
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validator import IntegrityEngine


def benchmark_chain_graph(node_count: int, cycle: bool = True):
    engine = IntegrityEngine()
    adj = {f"n_{i}": [f"n_{i+1}"] for i in range(node_count - 1)}
    if cycle:
        adj[f"n_{node_count - 1}"] = ["n_0"]
    else:
        adj[f"n_{node_count - 1}"] = []

    start = time.perf_counter()
    try:
        cycles = engine._detect_cycles(adj)
        elapsed = time.perf_counter() - start
        return {"nodes": node_count, "cycles_found": len(cycles), "elapsed_ms": elapsed * 1000, "status": "OK"}
    except RecursionError as e:
        elapsed = time.perf_counter() - start
        return {"nodes": node_count, "cycles_found": 0, "elapsed_ms": elapsed * 1000, "status": "RecursionError", "error": str(e)}


def benchmark_complex_web(node_count: int):
    engine = IntegrityEngine()
    adj = {f"n_{i}": [] for i in range(node_count)}
    for i in range(node_count - 1):
        adj[f"n_{i}"].append(f"n_{i+1}")
        if i % 5 == 0 and i > 10:
            adj[f"n_{i}"].append(f"n_{i-10}")  # cycle edge

    start = time.perf_counter()
    try:
        cycles = engine._detect_cycles(adj)
        elapsed = time.perf_counter() - start
        return {"nodes": node_count, "cycles_found": len(cycles), "elapsed_ms": elapsed * 1000, "status": "OK"}
    except RecursionError as e:
        elapsed = time.perf_counter() - start
        return {"nodes": node_count, "cycles_found": 0, "elapsed_ms": elapsed * 1000, "status": "RecursionError", "error": str(e)}


if __name__ == "__main__":
    print("=== CHAIN GRAPH BENCHMARK ===")
    for n in [100, 250, 500, 750, 900, 1000, 1200, 1500]:
        res = benchmark_chain_graph(n)
        print(f"Nodes: {res['nodes']:4d} | Status: {res['status']:14s} | Time: {res['elapsed_ms']:7.2f} ms | Cycles: {res['cycles_found']}")

    print("\n=== COMPLEX WEB BENCHMARK ===")
    for n in [100, 250, 500, 750, 900, 1000, 1200]:
        res = benchmark_complex_web(n)
        print(f"Nodes: {res['nodes']:4d} | Status: {res['status']:14s} | Time: {res['elapsed_ms']:7.2f} ms | Cycles: {res['cycles_found']}")
