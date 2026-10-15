#!/usr/bin/env python3
"""Render llvm-mca JSON reports to JPG images using Playwright Chromium.

Usage:
    python visualizeMca.py float1

Install:
    python -m pip install -r requirements-visualize.txt
    python -m playwright install chromium

The HTML is generated in memory. Only JPG images are saved.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
METRICS = (
    ("IPC", "IPC", False, "Instructions retired per cycle in the llvm-mca model."),
    ("Cycles / iteration", "cycles_per_iteration", True, "TotalCycles ÷ Iterations; modeled cycles per loop iteration."),
    ("Instructions / iteration", "instructions_per_iteration", False, "Instructions ÷ Iterations; modeled instructions per iteration."),
    ("Block RThroughput", "BlockRThroughput", True, "llvm-mca's reciprocal-throughput estimate for the code block."),
)
COMPILER_COLORS = {"gcc": "#2774c8", "clang": "#8b5cf6"}


@dataclass
class Result:
    stem: str
    path: Path
    compiler: str
    isa: str
    opt: str
    status: str
    reason: str = ""
    document: dict[str, Any] | None = None
    region: dict[str, Any] | None = None

    @property
    def label(self) -> str:
        return f"{self.compiler.upper()} · {self.isa} · {self.opt}"

    @property
    def summary(self) -> dict[str, Any]:
        return (self.region or {}).get("SummaryView", {})

    @property
    def instructions(self) -> list[str]:
        value = (self.region or {}).get("Instructions", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def instruction_info(self) -> list[dict[str, Any]]:
        value = (self.region or {}).get("InstructionInfoView", {})
        items = value.get("InstructionList", []) if isinstance(value, dict) else []
        return items if isinstance(items, list) else []

    @property
    def pressure_info(self) -> list[dict[str, Any]]:
        value = (self.region or {}).get("ResourcePressureView", {})
        items = value.get("ResourcePressureInfo", []) if isinstance(value, dict) else []
        return items if isinstance(items, list) else []

    @property
    def timeline_info(self) -> list[dict[str, Any]]:
        value = (self.region or {}).get("TimelineView", {})
        items = value.get("TimelineInfo", []) if isinstance(value, dict) else []
        return items if isinstance(items, list) else []

    @property
    def resources(self) -> list[str]:
        target = (self.document or {}).get("TargetInfo", {})
        items = target.get("Resources", []) if isinstance(target, dict) else []
        return [str(item) for item in items] if isinstance(items, list) else []

    @property
    def cpu(self) -> str:
        return str(((self.document or {}).get("TargetInfo") or {}).get("CPUName", "unknown"))


def parse_stem(stem: str) -> tuple[str, str, str]:
    match = re.match(r"^(gcc|clang)-(.+)-(O[0-3])$", stem, re.IGNORECASE)
    if not match:
        return "other", "UNKNOWN", "?"
    compiler, isa, opt = match.groups()
    isa_key = isa.casefold().replace("-", "_")
    isa_name = {"arm": "ARM", "riscv": "RISCV", "x86_64": "X86_64"}.get(isa_key, isa.upper())
    return compiler.lower(), isa_name, opt.upper()


def find_assembly(asm_dir: Path, stem: str) -> Path | None:
    if not asm_dir.exists():
        return None
    return next((p for p in asm_dir.glob("*.s") if p.stem.casefold() == stem.casefold()), None)


def load_results(experiment_dir: Path) -> list[Result]:
    json_dir = experiment_dir / "mca" / "json"
    if not json_dir.is_dir():
        raise FileNotFoundError(f"MCA JSON directory not found: {json_dir}")

    results: list[Result] = []
    for path in sorted(json_dir.glob("*.json"), key=lambda p: p.name.casefold()):
        compiler, isa, opt = parse_stem(path.stem)
        result = Result(path.stem, path, compiler, isa, opt, "invalid")
        raw = path.read_text(encoding="utf-8-sig")
        if not raw.strip():
            result.status = "optimized"
            result.reason = "JSON is empty; treated as the observed code being optimized away."
            results.append(result)
            continue
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            result.reason = f"Malformed JSON at line {error.lineno}, column {error.colno}."
            results.append(result)
            continue

        result.document = document if isinstance(document, dict) else {}
        regions = result.document.get("CodeRegions", [])
        if not isinstance(regions, list) or not regions:
            result.status = "optimized"
            result.reason = "No code region was emitted by llvm-mca."
            results.append(result)
            continue

        asm = find_assembly(experiment_dir / "asm", path.stem)
        if asm is not None:
            asm_text = asm.read_text(encoding="utf-8", errors="replace")
            if "CGX-MCA-BEGIN" not in asm_text:
                result.status = "optimized"
                result.reason = "Assembly has no CGX-MCA-BEGIN marker; the observed region appears optimized away."
                results.append(result)
                continue

        region = regions[0]
        if not isinstance(region, dict):
            result.reason = "CodeRegions[0] is not an object."
            results.append(result)
            continue
        result.region = region
        if not result.instructions:
            result.status = "optimized"
            result.reason = "The reported code region contains no instructions."
        else:
            result.status = "valid"
        results.append(result)
    return results


def number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    value = number(value, float("nan"))
    if not math.isfinite(value):
        return "—"
    if digits == 0:
        return f"{value:,.0f}"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")


def metric_value(result: Result, key: str) -> float | None:
    summary = result.summary
    if key in ("cycles_per_iteration", "instructions_per_iteration"):
        iterations = number(summary.get("Iterations"))
        if iterations <= 0:
            return None
        field = "TotalCycles" if key == "cycles_per_iteration" else "Instructions"
        return number(summary.get(field)) / iterations
    return number(summary[key], float("nan")) if key in summary else None


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def shorten(value: str, limit: int = 34) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[:limit - 1] + "…"


def svg_bar_chart(results: list[Result], key: str, title: str, explanation: str, lower_is_better: bool) -> str:
    width, height = 980, 410
    left, right, top, bottom = 68, 22, 36, 125
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [(r, metric_value(r, key)) for r in results]
    values = [(r, v) for r, v in values if v is not None and math.isfinite(v)]
    if not values:
        return f'<div class="chart-card"><h3>{esc(title)}</h3><p>No usable measurements.</p></div>'
    maximum = max(v for _, v in values)
    max_axis = maximum * 1.12 if maximum > 0 else 1.0
    step = max_axis / 4
    group_w = plot_w / len(values)
    bar_w = min(36.0, group_w * 0.62)
    svg = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    for tick in range(5):
        val = step * tick
        y = top + plot_h - val / max_axis * plot_h
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="gridline"/>')
        svg.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="tick">{esc(fmt(val))}</text>')
    svg.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" class="axisline"/>')
    for i, (result, value) in enumerate(values):
        x = left + i * group_w + (group_w - bar_w) / 2
        bar_h = value / max_axis * plot_h
        y = top + plot_h - bar_h
        color = COMPILER_COLORS.get(result.compiler, "#64748b")
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(1, bar_h):.1f}" rx="3" fill="{color}"/>')
        svg.append(f'<text x="{x+bar_w/2:.1f}" y="{max(top+12, y-7):.1f}" text-anchor="middle" class="barvalue">{esc(fmt(value))}</text>')
        cx, cy = x + bar_w / 2, top + plot_h + 15
        label = f"{result.compiler.upper()} {result.isa} {result.opt}"
        svg.append(f'<text x="{cx:.1f}" y="{cy:.1f}" transform="rotate(-48 {cx:.1f} {cy:.1f})" text-anchor="end" class="xlabel">{esc(label)}</text>')
    svg.append("</svg>")
    return (f'<div class="chart-card"><div class="chart-heading"><h3>{esc(title)}</h3>'
            f'<p>{esc(explanation)}</p></div>{"".join(svg)}'
            f'<p class="direction">{"Lower values are generally preferable" if lower_is_better else "Higher values appear taller"}. '
            'These are llvm-mca estimates, not real-hardware measurements.</p></div>')


def stat_card(title: str, value: str, detail: str = "") -> str:
    return f'<div class="stat-card"><div class="stat-title">{esc(title)}</div><div class="stat-value">{esc(value)}</div><div class="stat-detail">{esc(detail)}</div></div>'


def condition_title(result: Result) -> str:
    return f"{result.compiler.upper()} / {result.isa} / {result.opt}"


def summary_line(result: Result) -> str:
    s = result.summary
    iterations = number(s.get("Iterations"))
    cycles = number(s.get("TotalCycles"))
    instructions = number(s.get("Instructions"))
    return (f"CPU {result.cpu} · IPC {fmt(s.get('IPC'))} · "
            f"{fmt(cycles / iterations if iterations else None)} cycles/iter · "
            f"{fmt(instructions / iterations if iterations else None)} instructions/iter · "
            f"BRT {fmt(s.get('BlockRThroughput'))}")


def instructions_section(result: Result) -> str:
    info_by_index = {int(item.get("Instruction", -1)): item for item in result.instruction_info if isinstance(item, dict)}
    rows = []
    for index, instruction in enumerate(result.instructions):
        info = info_by_index.get(index, {})
        rows.append(
            f'<tr><td class="num">{index}</td><td class="asm"><code>{esc(instruction.strip())}</code></td>'
            f'<td>{esc(fmt(info.get("Latency"), 0) if "Latency" in info else "—")}</td>'
            f'<td>{esc(fmt(info.get("NumMicroOpcodes"), 0) if "NumMicroOpcodes" in info else "—")}</td>'
            f'<td>{esc(fmt(info.get("RThroughput") if "RThroughput" in info else None))}</td>'
            f'<td>{"load" if info.get("mayLoad") else "—"}</td><td>{"store" if info.get("mayStore") else "—"}</td></tr>'
        )
    return (f'<section class="condition"><h3>{esc(condition_title(result))}</h3><p class="muted">{esc(summary_line(result))}</p>'
            '<table class="data-table"><thead><tr><th>#</th><th>Instruction</th><th>Latency</th><th>µOps</th><th>RThroughput</th><th>Load</th><th>Store</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></section>')


def heat_color(value: float, maximum: float) -> tuple[str, str]:
    ratio = max(0.0, min(1.0, value / maximum)) if maximum > 0 else 0.0
    start, end = (242, 246, 255), (39, 100, 200)
    rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))
    return "#%02x%02x%02x" % rgb, ("#fff" if ratio > 0.56 else "#1f2937")


def pressure_section(result: Result) -> str:
    resources = result.resources
    pressures: dict[tuple[int, int], float] = {}
    for item in result.pressure_info:
        if not isinstance(item, dict):
            continue
        try:
            key = (int(item.get("InstructionIndex", -1)), int(item.get("ResourceIndex", -1)))
        except (TypeError, ValueError):
            continue
        pressures[key] = pressures.get(key, 0.0) + number(item.get("ResourceUsage"))
    if not resources:
        count = max((resource for _, resource in pressures), default=-1) + 1
        resources = [f"Resource {i}" for i in range(count)]
    maximum = max(pressures.values(), default=0.0)
    header = "".join(f'<th title="{esc(resource)}">{esc(resource.replace("SKL", ""))}</th>' for resource in resources)
    rows = []
    for i, instruction in enumerate(result.instructions):
        cells = []
        for ridx, resource in enumerate(resources):
            value = pressures.get((i, ridx), 0.0)
            bg, fg = heat_color(value, maximum)
            cells.append(f'<td style="background:{bg};color:{fg}" title="{esc(resource)}: {esc(value)}">{esc(fmt(value) if value > 0 else "·")}</td>')
        rows.append(f'<tr><th class="row-label"><span>{i}</span> <code>{esc(shorten(instruction, 42))}</code></th>{"".join(cells)}</tr>')
    return (f'<section class="condition"><h3>{esc(condition_title(result))}</h3><p class="muted">{esc(result.cpu)} · darker cells indicate larger per-instruction resource usage.</p>'
            '<div class="heat-wrap"><table class="heat-table"><thead><tr><th>Instruction</th>' + header +
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>')


def timeline_svg(result: Result) -> str:
    timeline = result.timeline_info[:len(result.instructions)]
    if not timeline:
        return '<p class="empty-note">No timeline entries were recorded for this condition.</p>'
    fields = [
        ("CycleDispatched", "dispatch", "#64748b"),
        ("CycleReady", "ready", "#06b6d4"),
        ("CycleIssued", "issue", "#8b5cf6"),
        ("CycleExecuted", "execute", "#f59e0b"),
        ("CycleRetired", "retire", "#16a34a"),
    ]
    cycle_max = max((number(item.get(name)) for item in timeline for name, _, _ in fields), default=1.0)
    cycle_max = max(1.0, cycle_max)
    width, left, right, row_h, top = 1320, 270, 36, 30, 35
    height = top + len(timeline) * row_h + 58
    plot_w = width - left - right
    out = [f'<svg class="timeline-svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(condition_title(result))} timeline">']
    for tick in range(6):
        cycle = cycle_max * tick / 5
        x = left + cycle / cycle_max * plot_w
        out.append(f'<line x1="{x:.1f}" y1="{top-12}" x2="{x:.1f}" y2="{top+len(timeline)*row_h}" class="gridline"/>')
        out.append(f'<text x="{x:.1f}" y="{top-17}" text-anchor="middle" class="tick">{cycle:.0f}</text>')
    for i, item in enumerate(timeline):
        y = top + i * row_h
        out.append(f'<text x="{left-12}" y="{y+5}" text-anchor="end" class="timeline-label">{i}: {esc(shorten(result.instructions[i].strip(), 34))}</text>')
        xs, markers = [], []
        for name, label, color in fields:
            x = left + max(0.0, min(cycle_max, number(item.get(name)))) / cycle_max * plot_w
            xs.append(x)
            markers.append(f'<circle cx="{x:.1f}" cy="{y}" r="4.5" fill="{color}"><title>{esc(label)}: {esc(item.get(name, "—"))}</title></circle>')
        out.append(f'<line x1="{min(xs):.1f}" y1="{y}" x2="{max(xs):.1f}" y2="{y}" stroke="#cbd5e1" stroke-width="2"/>')
        out.extend(markers)
    for i, (_, label, color) in enumerate(fields):
        x = left + i * 190
        out.append(f'<circle cx="{x}" cy="{height-18}" r="5" fill="{color}"/><text x="{x+10}" y="{height-14}" class="legend">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def timeline_section(result: Result) -> str:
    count = len(result.timeline_info[:len(result.instructions)])
    return (f'<section class="condition"><h3>{esc(condition_title(result))}</h3><p class="muted">{esc(result.cpu)} · '
            f'first instruction sequence in llvm-mca TimelineView ({count} rows where available).</p>{timeline_svg(result)}</section>')


def build_html(results: list[Result], experiment: str) -> str:
    valid = [r for r in results if r.status == "valid"]
    optimized = [r for r in results if r.status == "optimized"]
    invalid = [r for r in results if r.status == "invalid"]
    cards = "".join(stat_card(*item) for item in (
        ("Experiment", experiment, "MCA visualization"),
        ("JSON files", str(len(results)), "Files discovered in mca/json"),
        ("Analyzable", str(len(valid)), "Used in metric comparisons"),
        ("Optimized away", str(len(optimized)), "Excluded from performance comparisons"),
    ))
    status_rows = []
    for result in optimized:
        status_rows.append(f'<tr><td>{esc(condition_title(result))}</td><td><span class="status optimized">Optimized away</span></td><td>{esc(result.reason)}</td></tr>')
    for result in invalid:
        status_rows.append(f'<tr><td>{esc(condition_title(result))}</td><td><span class="status invalid">Invalid / incomplete</span></td><td>{esc(result.reason)}</td></tr>')
    statuses = ('<div class="status-table-wrap"><table class="data-table"><thead><tr><th>Condition</th><th>Status</th><th>Details</th></tr></thead><tbody>' +
                "".join(status_rows) + '</tbody></table></div>') if status_rows else '<p class="empty-note">Every discovered JSON file contains a usable code region.</p>'
    charts = "".join(svg_bar_chart(valid, *metric) for metric in METRICS)
    note = '<p class="muted">Empty JSON files and conditions missing the CGX-MCA-BEGIN assembly marker are classified as optimized away and excluded from metric charts.</p>'
    instructions = "".join(instructions_section(r) for r in valid) or '<p class="empty-note">No usable instructions found.</p>'
    pressure = "".join(pressure_section(r) for r in valid) or '<p class="empty-note">No resource-pressure data found.</p>'
    timeline = "".join(timeline_section(r) for r in valid) or '<p class="empty-note">No timeline data found.</p>'
    css = """
:root{--ink:#172033;--muted:#64748b;--line:#dbe3ee;--paper:#f4f7fb;--card:#fff;--blue:#2774c8}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,"Segoe UI",Arial,sans-serif;font-size:15px;line-height:1.45}
.sheet{width:1600px;padding:38px 42px 44px;margin:0 auto;background:var(--paper)}
.header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #cbd5e1;padding-bottom:22px;margin-bottom:24px}
.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.14em;font-weight:800;color:var(--blue)}h1{font-size:32px;line-height:1.1;margin:5px 0 0;letter-spacing:-.03em}h2{font-size:23px;margin:0 0 15px;letter-spacing:-.02em}h3{font-size:18px;margin:0 0 5px}p{margin:7px 0}.muted,.chart-heading p,.chart-card .direction{color:var(--muted);font-size:12px}.page-title{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:800}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0 28px}.stat-card,.chart-card,.condition{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 3px 12px rgba(25,50,80,.035)}.stat-title{font-size:12px;color:var(--muted);font-weight:700}.stat-value{font-size:27px;font-weight:800;line-height:1.3;margin:5px 0;overflow-wrap:anywhere}.stat-detail{font-size:11px;color:var(--muted)}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.chart-card{padding:18px 18px 12px;min-width:0}.chart-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}.chart-heading p{max-width:380px;text-align:right;margin:2px 0}.chart{width:100%;height:auto;display:block;margin-top:10px}.gridline{stroke:#e8edf4;stroke-width:1}.axisline{stroke:#94a3b8;stroke-width:1.2}.tick{font-size:11px;fill:#64748b}.barvalue{font-size:11px;fill:#334155;font-weight:700}.xlabel{font-size:10px;fill:#475569}.direction{margin:0 0 2px}
.status-table-wrap,.heat-wrap{overflow:hidden;border:1px solid var(--line);border-radius:10px;margin-top:15px}.data-table,.heat-table{border-collapse:collapse;width:100%;font-size:12px;background:white}.data-table th,.data-table td{border-bottom:1px solid #e8edf4;padding:9px 10px;text-align:left;vertical-align:top}.data-table thead th{background:#edf2f8;color:#475569;font-size:10px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}.data-table tbody tr:last-child td{border-bottom:0}.data-table tbody tr:nth-child(even){background:#fafcff}.asm code,.row-label code{font-family:Consolas,"Cascadia Code",monospace;font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}.num{width:40px;color:var(--muted);font-variant-numeric:tabular-nums}.asm{width:48%}.status{display:inline-block;border-radius:5px;padding:3px 7px;font-size:10px;font-weight:800;white-space:nowrap}.optimized{color:#854d0e;background:#fef3c7}.invalid{color:#991b1b;background:#fee2e2}
.condition{margin-top:16px;break-inside:avoid;padding:18px}.condition h3{font-size:17px}.heat-table th,.heat-table td{border-bottom:1px solid #e8edf4;border-right:1px solid #eef2f7;padding:5px 4px;text-align:center;white-space:nowrap;font-size:10px;font-variant-numeric:tabular-nums}.heat-table thead th{background:#edf2f8;writing-mode:vertical-rl;height:125px;max-width:30px;vertical-align:bottom}.heat-table thead th:first-child{writing-mode:horizontal-tb;max-width:none;min-width:300px;height:auto;text-align:left}.heat-table .row-label{text-align:left;white-space:normal;min-width:300px;max-width:390px;background:#f8fafc}.row-label span{display:inline-block;color:var(--muted);width:24px;font-size:10px}.heat-table td{min-width:43px}
.timeline-svg{display:block;width:100%;height:auto;margin-top:8px}.timeline-label{font-size:11px;fill:#334155}.legend{font-size:12px;fill:#475569}.empty-note{padding:18px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;color:#9a3412;font-size:13px}.footer{margin-top:25px;padding-top:14px;border-top:1px solid var(--line);font-size:10px;color:var(--muted);display:flex;justify-content:space-between}
"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CGX MCA · {esc(experiment)}</title><style>{css}</style></head><body>
<section id="overview" class="sheet"><header class="header"><div><div class="eyebrow">Compiler Generation eXplorer</div><h1>MCA Performance Overview</h1><p class="muted">Experiment: {esc(experiment)} · llvm-mca modeled results</p></div><div class="page-title">01 / Overview</div></header>
<div class="stats">{cards}</div><h2>Condition comparison</h2>{note}<div class="chart-grid">{charts}</div><h2 style="margin-top:30px">Conditions excluded from comparison</h2>{statuses}<footer class="footer"><span>CGX · MCA visualization</span><span>Modeled estimates, not physical CPU benchmarks.</span></footer></section>
<section id="instructions" class="sheet"><header class="header"><div><div class="eyebrow">Instruction analysis</div><h1>Instruction Latency &amp; µOps</h1><p class="muted">Per-instruction properties emitted by llvm-mca</p></div><div class="page-title">02 / Instructions</div></header>{instructions}<footer class="footer"><span>CGX · MCA visualization</span><span>Latency and throughput are llvm-mca model outputs.</span></footer></section>
<section id="pressure" class="sheet"><header class="header"><div><div class="eyebrow">Execution resources</div><h1>Resource Pressure Heatmap</h1><p class="muted">Per-instruction usage by modeled processor resource</p></div><div class="page-title">03 / Resource Pressure</div></header><p class="muted">Each condition uses its own model resources; values are not directly comparable across ISAs.</p>{pressure}<footer class="footer"><span>CGX · MCA visualization</span><span>Cell intensity is scaled within each condition.</span></footer></section>
<section id="timeline" class="sheet"><header class="header"><div><div class="eyebrow">Instruction scheduling</div><h1>Instruction Timeline</h1><p class="muted">Cycle markers from the first instruction sequence in TimelineView</p></div><div class="page-title">04 / Timeline</div></header><p class="muted">Dots show dispatch, ready, issue, execute and retire markers. Rows display the first instruction sequence available, not every repeated iteration.</p>{timeline}<footer class="footer"><span>CGX · MCA visualization</span><span>Cycle markers as reported by llvm-mca JSON.</span></footer></section></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render llvm-mca JSON results to JPG images using headless Chromium.")
    parser.add_argument("experiment", nargs="?", default="float1", help="experiment folder name under data-dir/experiments (default: float1)")
    parser.add_argument("--config", default=str(ROOT / "config.json"), help="path to config.json (default: repository root/config.json)")
    parser.add_argument("--output-dir", help="JPG output directory (default: <experiment>/mca/images)")
    parser.add_argument("--width", type=int, default=1600, help="render width in CSS pixels (default: 1600)")
    parser.add_argument("--quality", type=int, default=92, help="JPG quality from 1 to 100 (default: 92)")
    args = parser.parse_args()
    if args.width < 800:
        parser.error("--width must be at least 800")
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")

    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    if not config_path.is_file():
        print(f"error: config file not found: {config_path}", file=sys.stderr)
        return 2
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: could not read config: {error}", file=sys.stderr)
        return 2
    data_dir_value = config.get("data-dir")
    if not isinstance(data_dir_value, str) or not data_dir_value.strip():
        print('error: config.json must contain a non-empty "data-dir" value', file=sys.stderr)
        return 2
    data_dir = Path(data_dir_value).expanduser()
    if not data_dir.is_absolute():
        data_dir = (config_path.parent / data_dir).resolve()
    experiment_dir = data_dir / "experiments" / args.experiment
    try:
        results = load_results(experiment_dir)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else experiment_dir / "mca" / "images"
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("error: Playwright is not installed. Run: python -m pip install -r requirements-visualize.txt", file=sys.stderr)
        return 3

    document = build_html(results, args.experiment)
    print(f"Experiment: {args.experiment}")
    print(f"MCA JSON files: {len(results)}; usable: {sum(r.status == 'valid' for r in results)}; optimized away: {sum(r.status == 'optimized' for r in results)}; invalid: {sum(r.status == 'invalid' for r in results)}")
    print(f"Output: {output_dir}")
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as first_error:
                candidates = [Path("/usr/bin/chromium")]
                for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
                    located = shutil.which(name)
                    if located:
                        candidates.insert(0, Path(located))
                browser = None
                for executable in dict.fromkeys(candidates):
                    if executable.is_file():
                        try:
                            browser = playwright.chromium.launch(headless=True, executable_path=str(executable))
                            print(f"Using installed Chromium: {executable}")
                            break
                        except Exception:
                            continue
                if browser is None:
                    raise first_error
            page = browser.new_page(viewport={"width": args.width, "height": 1200}, device_scale_factor=1)
            page.set_content(document, wait_until="load")
            page.add_style_tag(content=f".sheet {{ width: {args.width}px; }}")
            page.evaluate("() => document.fonts.ready.then(() => true)")
            for element_id, filename in (
                ("overview", "overview.jpg"),
                ("instructions", "instructions.jpg"),
                ("pressure", "resource-pressure.jpg"),
                ("timeline", "timeline.jpg"),
            ):
                page.locator(f"#{element_id}").screenshot(path=str(output_dir / filename), type="jpeg", quality=args.quality, animations="disabled")
                print(f"  created {filename}")
            browser.close()
    except Exception as error:
        if "Executable doesn't exist" in str(error) or "browserType.launch" in str(error):
            print("error: Playwright Chromium is missing. Install it once with: python -m playwright install chromium", file=sys.stderr)
        else:
            print(f"error: JPG generation failed: {error}", file=sys.stderr)
        return 4
    print("Done. Only JPG files were saved; HTML was kept in memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
