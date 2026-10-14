#!/usr/bin/env python3
"""
qlchat 武汉-6元 渠道日报生成器（量级速览风格）
读取 data/ 下的 raw_*.json，生成 publish/ 下的 index.html + push_content.html

风格参考：简知分销日报（量级速览 + 昨日vs今日 + 渠道分解 + 合计 + chips + 查看完整看板）
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "channel_config.json"
DATA_DIR = SCRIPT_DIR / "data"
PUBLISH_DIR = SCRIPT_DIR / "publish"
PUBLISH_DIR.mkdir(exist_ok=True)

# 字段顺序（与UI一致）
FIELD_ORDER = [
    "assign_num", "friend_num", "friend_rate",
    "group_num", "group_rate",
    "enter_class1_rate", "finish_class1_rate",
    "delete_friend_num", "delete_friend_rate",
]
NUM_FIELDS = ["assign_num", "friend_num", "group_num", "delete_friend_num"]
RATE_FIELDS = ["friend_rate", "group_rate", "enter_class1_rate", "finish_class1_rate", "delete_friend_rate"]


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_raw(start: str, end: str, is_summary: str = "N"):
    """加载指定区间的原始数据"""
    fname = f"raw_{start}_{end}_{is_summary}.json"
    fpath = DATA_DIR / fname
    if not fpath.exists():
        return []
    with open(fpath, "r", encoding="utf-8") as f:
        d = json.load(f)
    return d.get("data") or []


def aggregate_by_channel(records, fields=NUM_FIELDS):
    """按渠道汇总（明细行，channel_name_ != '-'）"""
    out = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r.get("channel_name_") == "-":
            continue
        name = r["channel_name_"]
        for f in fields:
            v = r.get(f, 0)
            try:
                out[name][f] += int(float(v))
            except (ValueError, TypeError):
                if isinstance(v, str) and v.endswith("%"):
                    try:
                        out[name][f] += int(float(v.rstrip("%")))
                    except ValueError:
                        pass
    return dict(out)


def aggregate_total(records, fields=NUM_FIELDS):
    """总合计（明细行汇总，跳过 '-'）"""
    out = defaultdict(int)
    for r in records:
        if r.get("channel_name_") == "-":
            continue
        for f in fields:
            v = r.get(f, 0)
            try:
                out[f] += int(float(v))
            except (ValueError, TypeError):
                if isinstance(v, str) and v.endswith("%"):
                    try:
                        out[f] += int(float(v.rstrip("%")))
                    except ValueError:
                        pass
    return dict(out)


def fmt_num(n):
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n) if n else "0"


def fmt_change(yest, tod):
    """变化百分比与样式"""
    if yest == 0 and tod == 0:
        return "—", "#64748b"
    if yest == 0:
        return "+∞", "#22c55e" if tod > 0 else "—"
    pct = (tod - yest) / yest * 100
    if pct > 0:
        return f"+{pct:.0f}%", "#22c55e"
    elif pct < 0:
        return f"{pct:.0f}%", "#ef4444"
    else:
        return "0%", "#64748b"


def weekday_cn(date_str):
    """2026-10-13 -> 周二"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[d.weekday()]


def build_daily_push(cfg, yest_date, tod_date, yest_data, tod_data, is_empty, history_note=""):
    """生成 简知风格 量级速览 推送卡片"""
    metric = cfg["dailyPush"]["metric"]
    metric_name = cfg["dailyPush"]["metricName"]
    top_n = cfg["dailyPush"]["topChannelsInChips"]
    channel_name = cfg.get("channelName", "qlchat 渠道")
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    yest_w = weekday_cn(yest_date)
    tod_w = weekday_cn(tod_date)

    # 按渠道汇总
    yest_ch = aggregate_by_channel(yest_data)
    tod_ch = aggregate_by_channel(tod_data)

    # 总计
    yest_total = sum(c.get(metric, 0) for c in yest_ch.values())
    tod_total = sum(c.get(metric, 0) for c in tod_ch.values())

    # 所有出现过的渠道（昨日 ∪ 今日）
    all_channels = sorted(set(yest_ch.keys()) | set(tod_ch.keys()),
                          key=lambda n: -(yest_ch.get(n, {}).get(metric, 0) + tod_ch.get(n, {}).get(metric, 0)))

    change_text, change_color = fmt_change(yest_total, tod_total)

    # 表格行
    if is_empty:
        rows_html = "<tr><td colspan='4' style='text-align:center;color:#64748b;padding:14px'>暂无数据</td></tr>"
    else:
        rows = []
        for ch in all_channels:
            y_v = yest_ch.get(ch, {}).get(metric, 0)
            t_v = tod_ch.get(ch, {}).get(metric, 0)
            c_txt, c_col = fmt_change(y_v, t_v)
            rows.append(
                f"<tr>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #334155;font-size:12px'>{ch}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #334155;text-align:right;font-size:12px'>{fmt_num(y_v)}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #334155;text-align:right;font-size:12px'>{fmt_num(t_v)}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #334155;text-align:right;font-size:12px;color:{c_col}'>{c_txt}</td>"
                f"</tr>"
            )
        # 合计行
        rows.append(
            f"<tr style='background:rgba(255,255,255,.04)'>"
            f"<td style='padding:9px 10px;font-size:12px;font-weight:700'>合计</td>"
            f"<td style='padding:9px 10px;text-align:right;font-size:13px;font-weight:700'>{fmt_num(yest_total)}</td>"
            f"<td style='padding:9px 10px;text-align:right;font-size:13px;font-weight:700'>{fmt_total := fmt_num(tod_total)}</td>"
            f"<td style='padding:9px 10px;text-align:right;font-size:12px;font-weight:700;color:{change_color}'>{change_text}</td>"
            f"</tr>"
        )
        rows_html = "".join(rows)

    # chips（取 metric 累计 top_n）
    chip_pool = []
    for ch in all_channels:
        v = yest_ch.get(ch, {}).get(metric, 0) + tod_ch.get(ch, {}).get(metric, 0)
        if v > 0:
            chip_pool.append((ch, v))
    chip_pool.sort(key=lambda x: -x[1])
    if chip_pool:
        chips_html = "".join(
            f"<span style='display:inline-block;background:rgba(59,130,246,.12);color:#93c5fd;"
            f"padding:4px 10px;border-radius:12px;font-size:11px;margin:2px 3px'>{ch} {fmt_num(v)}</span>"
            for ch, v in chip_pool[:top_n]
        )
    else:
        chips_html = ""

    # 警示条（如果空数据）
    if is_empty:
        alert_html = (
            f"<div style='background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.3);"
            f"color:#fbbf24;padding:8px 12px;border-radius:6px;font-size:11px;margin-bottom:10px'>"
            f"⚠️ {channel_name} 今日暂无数据{('，' + history_note) if history_note else ''}"
            f"</div>"
        )
    else:
        alert_html = ""

    # 整张卡片
    return f"""<div style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:600px;margin:0 auto;background:#0f172a;color:#e2e8f0;border-radius:12px;overflow:hidden;border:1px solid #334155'>
  <div style='background:linear-gradient(135deg,#1e40af,#7c3aed);padding:16px 20px'>
    <div style='font-size:17px;font-weight:700;text-align:center'>📊 量级速览</div>
    <div style='font-size:11px;opacity:.85;text-align:center;margin-top:4px'>{channel_name} · {yest_date[:7]} · 更新于 {update_time}</div>
  </div>
  <div style='padding:14px 18px'>
    {alert_html}
    <div style='font-size:12px;color:#94a3b8;margin-bottom:6px'>{metric_name}对比（{yest_date} {yest_w} → {tod_date} {tod_w}）</div>
    <table style='width:100%;border-collapse:collapse;background:#1e293b;border-radius:6px;overflow:hidden;margin-bottom:10px'>
      <thead>
        <tr style='background:rgba(255,255,255,.04)'>
          <th style='padding:8px 10px;text-align:left;font-size:11px;color:#94a3b8;font-weight:600'>渠道</th>
          <th style='padding:8px 10px;text-align:right;font-size:11px;color:#94a3b8;font-weight:600'>{yest_date[-5:]} {yest_w}</th>
          <th style='padding:8px 10px;text-align:right;font-size:11px;color:#94a3b8;font-weight:600'>{tod_date[-5:]} {tod_w}</th>
          <th style='padding:8px 10px;text-align:right;font-size:11px;color:#94a3b8;font-weight:600'>变化</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    {f"<div style='font-size:11px;color:#94a3b8;margin-bottom:10px'>渠道累计 {metric_name} Top {top_n}</div>" if chip_pool else ""}
    {f"<div style='margin-bottom:12px'>{chips_html}</div>" if chips_html else ""}
    <div style='text-align:center;margin-top:8px'>
      <a href='https://jnc121314.github.io/qlchat-dashboard/' style='display:inline-block;background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;padding:9px 22px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600'>🔗 查看完整看板</a>
    </div>
  </div>
  <div style='background:rgba(0,0,0,.25);padding:8px 18px;font-size:10px;color:#64748b;text-align:center'>
    qlchat 渠道日报 · powered by WorkBuddy
  </div>
</div>"""


def build_full_page(cfg, range_start, range_end, range_records, yest_data, tod_data, yest_date, tod_date):
    """生成完整 HTML 报告页"""
    channel_name = cfg.get("channelName", "qlchat 渠道")
    field_names = cfg["fieldNames"]
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    metric = cfg["dailyPush"]["metric"]
    metric_name = cfg["dailyPush"]["metricName"]

    # 区间数据：按渠道汇总
    range_ch = aggregate_by_channel(range_records)
    range_total = aggregate_total(range_records)
    # 区间按日
    by_date = defaultdict(lambda: defaultdict(int))
    for r in range_records:
        if r.get("channel_name_") == "-":
            continue
        d = r.get("statdate", "")
        for f in NUM_FIELDS:
            try:
                by_date[d][f] += int(float(r.get(f, 0) or 0))
            except (ValueError, TypeError):
                pass

    # 昨日今日汇总
    yest_ch = aggregate_by_channel(yest_data)
    tod_ch = aggregate_by_channel(tod_data)
    yest_total = sum(c.get(metric, 0) for c in yest_ch.values())
    tod_total = sum(c.get(metric, 0) for c in tod_ch.values())
    change_text, change_color = fmt_change(yest_total, tod_total)

    # 渠道表行
    if range_ch:
        sorted_ch = sorted(range_ch.items(), key=lambda x: -x[1].get("assign_num", 0))
        ch_rows = []
        for name, rec in sorted_ch:
            ch_rows.append(
                f"<tr><td style='padding:8px 10px;font-size:12px'>{name}</td>"
                + "".join(f"<td style='padding:8px 10px;text-align:right;font-size:12px'>{fmt_num(rec.get(f,0))}</td>" for f in NUM_FIELDS)
                + "</tr>"
            )
        ch_table = "\n".join(ch_rows)
    else:
        ch_table = "<tr><td colspan='5' style='text-align:center;color:#64748b;padding:20px'>暂无渠道数据</td></tr>"

    # 每日明细行
    if by_date:
        day_rows = []
        for d in sorted(by_date.keys(), reverse=True):
            rec = by_date[d]
            day_rows.append(
                f"<tr><td style='padding:8px 10px;font-size:12px'>{d}</td>"
                + "".join(f"<td style='padding:8px 10px;text-align:right;font-size:12px'>{fmt_num(rec.get(f,0))}</td>" for f in NUM_FIELDS)
                + "</tr>"
            )
        day_table = "\n".join(day_rows)
    else:
        day_table = "<tr><td colspan='5' style='text-align:center;color:#64748b;padding:20px'>暂无每日数据</td></tr>"

    # 字段表头
    num_headers = "".join(f"<th style='padding:9px 10px;text-align:right;font-size:11px;color:#94a3b8;font-weight:600'>{field_names.get(f,f)}</th>" for f in NUM_FIELDS)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{channel_name} · 渠道数据看板</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;--accent:#3b82f6;--success:#22c55e;--warn:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:20px 24px;max-width:1280px;margin:0 auto}}
.header{{text-align:center;padding:18px 0 14px}}
.header h1{{font-size:22px;margin-bottom:4px}}
.header p{{color:var(--muted);font-size:12px}}
.badge{{display:inline-block;background:linear-gradient(135deg,#1e40af,#7c3aed);color:#fff;padding:5px 14px;border-radius:20px;font-size:11px;margin-top:10px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:18px}}
.kpi{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;text-align:center}}
.kpi-icon{{font-size:22px;margin-bottom:4px}}
.kpi-value{{font-size:24px;font-weight:700;color:var(--accent)}}
.kpi-label{{font-size:11px;color:var(--muted);margin-top:3px}}
.kpi-change{{font-size:11px;margin-top:4px;font-weight:600}}
.section{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:14px}}
.section h2{{font-size:13px;color:var(--muted);margin-bottom:10px;font-weight:600}}
.alert{{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);color:#fbbf24;padding:10px 14px;border-radius:8px;font-size:12px;margin-bottom:14px}}
.table-wrap{{overflow-x:auto;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}}
th{{background:rgba(255,255,255,.04);color:var(--muted);font-weight:600}}
td.num,th{{text-align:right}}
tr:hover{{background:rgba(255,255,255,.02)}}
.footer{{text-align:center;color:var(--muted);font-size:11px;padding:20px 0}}
</style>
</head>
<body>
<div class="header">
  <h1>📊 {channel_name} · 渠道数据看板</h1>
  <p>数据区间: {range_start} 至 {range_end}</p>
  <div class="badge">🕐 更新于 {update_time}</div>
</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-icon">📈</div>
    <div class="kpi-value">{fmt_num(yest_total)}</div>
    <div class="kpi-label">昨日 {metric_name}</div>
  </div>
  <div class="kpi">
    <div class="kpi-icon">📊</div>
    <div class="kpi-value">{fmt_num(tod_total)}</div>
    <div class="kpi-label">今日 {metric_name}</div>
  </div>
  <div class="kpi">
    <div class="kpi-icon">🔄</div>
    <div class="kpi-value" style="color:{change_color}">{change_text}</div>
    <div class="kpi-label">变化</div>
  </div>
  <div class="kpi">
    <div class="kpi-icon">🗂️</div>
    <div class="kpi-value">{fmt_num(range_total.get('assign_num', 0))}</div>
    <div class="kpi-label">区间累计线索数</div>
  </div>
</div>

{f'<div class="alert">⚠️ 当日/昨日 渠道暂无数据，请确认渠道是否正确或数据是否未上报</div>' if (yest_total == 0 and tod_total == 0) else ''}

<div class="section">
  <h2>🏆 渠道汇总（区间 {range_start} ~ {range_end}）</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th style="padding:9px 10px;text-align:left;font-size:11px;color:#94a3b8;font-weight:600">渠道</th>
        {num_headers}
      </tr></thead>
      <tbody>
        {ch_table}
      </tbody>
    </table>
  </div>
</div>

<div class="section">
  <h2>📅 每日明细（区间 {range_start} ~ {range_end}）</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th style="padding:9px 10px;text-align:left;font-size:11px;color:#94a3b8;font-weight:600">日期</th>
        {num_headers}
      </tr></thead>
      <tbody>
        {day_table}
      </tbody>
    </table>
  </div>
</div>

<div class="footer">qlchat 渠道数据 · powered by WorkBuddy</div>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="今日日期 (YYYY-MM-DD)，默认今天")
    args = parser.parse_args()

    cfg = load_config()
    today = args.today or datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    # 加载昨日/今日数据
    yest_data = load_raw(yesterday, yesterday, "N")
    tod_data = load_raw(today, today, "N")

    # 区间数据：找最新有数据的 range 文件
    range_records = []
    range_files = sorted([f for f in DATA_DIR.glob("raw_*_*_N.json") if "_" + yesterday not in f.stem and "_" + today not in f.stem], reverse=True)
    for rf in range_files:
        try:
            d = load_raw(*rf.stem.replace("raw_", "").replace("_N", "").rsplit("_", 1)[0:2] if False else (rf.stem.split("_")[1], rf.stem.split("_")[2]), "N")
            if d:
                range_records = d
                range_start = rf.stem.split("_")[1]
                range_end = rf.stem.split("_")[2]
                break
        except Exception:
            continue
    if not range_records:
        # 退化：尝试直接找最大区间的
        for rf in range_files:
            d = load_raw(rf.stem.split("_")[1], rf.stem.split("_")[2], "N")
            if d:
                range_records = d
                range_start = rf.stem.split("_")[1]
                range_end = rf.stem.split("_")[2]
                break
    if not range_records:
        range_start = range_end = today

    print(f"📅 今日 {today}, 昨日 {yesterday}")
    print(f"📅 区间参考 {range_start} ~ {range_end}, {len(range_records)} 条")

    is_empty = (len(yest_data) == 0 and len(tod_data) == 0)
    history_note = ""
    if is_empty and range_records:
        # 找有数据的最近日期
        dates = sorted({r.get("statdate", "") for r in range_records if r.get("statdate")}, reverse=True)
        if dates:
            history_note = f"最近有数据 {dates[0]}（{len(range_records)} 条）"
    elif is_empty:
        history_note = "历史无数据"

    push_html = build_daily_push(cfg, yesterday, today, yest_data, tod_data, is_empty, history_note)
    full_html = build_full_page(cfg, range_start, range_end, range_records, yest_data, tod_data, yesterday, today)

    push_path = PUBLISH_DIR / "push_content.html"
    page_path = PUBLISH_DIR / "index.html"
    with open(push_path, "w", encoding="utf-8") as f:
        f.write(push_html)
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"✅ 推送卡片: {push_path} ({push_path.stat().st_size} bytes)")
    print(f"✅ 完整页面: {page_path} ({page_path.stat().st_size} bytes)")
    if is_empty:
        print("⚠️  昨日/今日均无数据，已生成空报告+警示条")


if __name__ == "__main__":
    main()
