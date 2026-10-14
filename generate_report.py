#!/usr/bin/env python3
"""
qlchat 武汉-6元 渠道数据报表生成器
读取 data/ 下的 raw_*.json，生成 publish/ 下的 index.html + push_content.html
"""
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

FIELD_NAMES = {
    "assign_num": "分配量",
    "friend_num": "加微数",
    "friend_rate": "加微率",
    "group_num": "进群数",
    "group_rate": "进群率",
    "enter_class1_rate": "D1到课率",
    "finish_class1_rate": "D1完课率",
    "delete_friend_num": "删好友数",
    "delete_friend_rate": "删好友率",
}
NUM_FIELDS = ["assign_num", "friend_num", "group_num", "delete_friend_num"]
RATE_FIELDS = ["friend_rate", "group_rate", "enter_class1_rate", "finish_class1_rate", "delete_friend_rate"]


def load_latest_raw():
    """加载最新的明细数据 (isSummary=N)，优先选择有数据的最新文件"""
    files = sorted(DATA_DIR.glob("raw_*_N.json"), reverse=True)
    if not files:
        return None, None, None
    # 优先选择有数据的文件，找不到再返回空文件
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("data"):
                name = f.stem  # raw_2026-10-13_2026-10-13
                parts = name.split("_")
                return data, parts[1], parts[2]
        except Exception:
            continue
    # 没有有数据的文件，使用最新的（哪怕为空）
    f = files[0]
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    name = f.stem
    parts = name.split("_")
    return data, parts[1], parts[2]


def aggregate_daily(records):
    """按日汇总 (总行)"""
    by_date = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r.get("channel_name_") != "-":  # 只统计明细行
            continue
        d = r.get("statdate", "")
        if not d:
            continue
        for f in NUM_FIELDS:
            by_date[d][f] += int(r.get(f, 0) or 0)
    return dict(by_date)


def aggregate_channel(records):
    """按渠道汇总 (明细行)"""
    by_channel = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r.get("channel_name_") == "-":
            continue
        name = r["channel_name_"]
        for f in NUM_FIELDS:
            by_channel[name][f] += int(r.get(f, 0) or 0)
    return dict(by_channel)


def get_total_summary(records):
    """获取全期总合计"""
    total = defaultdict(int)
    for r in records:
        if r.get("channel_name_") != "-":
            continue
        for f in NUM_FIELDS:
            total[f] += int(r.get(f, 0) or 0)
    return dict(total)


def fmt_num(n):
    return f"{int(n):,}" if n else "0"


def render_daily_table(by_date):
    """每日明细表"""
    if not by_date:
        return "<p class='empty'>暂无数据</p>"
    rows = []
    rows.append("<table class='data-table'><thead><tr>")
    rows.append("<th>日期</th>")
    for f in ["assign_num", "friend_num", "friend_rate", "group_num", "group_rate",
              "enter_class1_rate", "finish_class1_rate", "delete_friend_num", "delete_friend_rate"]:
        rows.append(f"<th>{FIELD_NAMES[f]}</th>")
    rows.append("</tr></thead><tbody>")
    for d in sorted(by_date.keys(), reverse=True):
        rec = by_date[d]
        # 比率字段从明细行获取（rate只有一个代表性值）
        rate_rec = {f: "-" for f in RATE_FIELDS}
        rows.append("<tr>")
        rows.append(f"<td>{d}</td>")
        for f in NUM_FIELDS:
            rows.append(f"<td class='num'>{fmt_num(rec.get(f, 0))}</td>")
        for f in RATE_FIELDS:
            rows.append(f"<td class='num'>{rate_rec[f]}</td>")
        rows.append("</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_channel_table(by_channel):
    """渠道汇总表"""
    if not by_channel:
        return "<p class='empty'>暂无数据</p>"
    rows = []
    rows.append("<table class='data-table'><thead><tr>")
    rows.append("<th>渠道</th>")
    for f in ["assign_num", "friend_num", "group_num", "delete_friend_num"]:
        rows.append(f"<th>{FIELD_NAMES[f]}</th>")
    rows.append("</tr></thead><tbody>")
    sorted_channels = sorted(by_channel.items(), key=lambda x: -x[1].get("assign_num", 0))
    for name, rec in sorted_channels:
        rows.append("<tr>")
        rows.append(f"<td>{name}</td>")
        for f in ["assign_num", "friend_num", "group_num", "delete_friend_num"]:
            rows.append(f"<td class='num'>{fmt_num(rec.get(f, 0))}</td>")
        rows.append("</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_daily_with_rates(records):
    """从明细记录中按天+渠道构建完整表 (含 rate)"""
    by_date = defaultdict(list)
    for r in records:
        if r.get("channel_name_") == "-":
            continue
        by_date[r["statdate"]].append(r)

    if not by_date:
        return "<p class='empty'>暂无数据</p>"

    rows = []
    rows.append("<table class='data-table'><thead><tr>")
    rows.append("<th>日期</th><th>渠道</th>")
    for f in ["assign_num", "friend_num", "friend_rate", "group_num", "group_rate",
              "enter_class1_rate", "finish_class1_rate", "delete_friend_num", "delete_friend_rate"]:
        rows.append(f"<th>{FIELD_NAMES[f]}</th>")
    rows.append("</tr></thead><tbody>")
    for d in sorted(by_date.keys(), reverse=True):
        day_records = sorted(by_date[d], key=lambda x: -int(x.get("assign_num", 0) or 0))
        for r in day_records:
            rows.append("<tr>")
            rows.append(f"<td>{d}</td>")
            rows.append(f"<td>{r['channel_name_']}</td>")
            for f in NUM_FIELDS:
                rows.append(f"<td class='num'>{fmt_num(r.get(f, 0))}</td>")
            for f in RATE_FIELDS:
                rows.append(f"<td class='num'>{r.get(f, '-')}</td>")
            rows.append("</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_kpi_cards(total, daily_count=1):
    """核心 KPI 卡片"""
    cards = []
    for f, icon in [("assign_num", "📊"), ("friend_num", "👥"),
                    ("group_num", "🎯"), ("delete_friend_num", "❌")]:
        cards.append(f"""
        <div class='kpi'>
          <div class='kpi-icon'>{icon}</div>
          <div class='kpi-value'>{fmt_num(total.get(f, 0))}</div>
          <div class='kpi-label'>{FIELD_NAMES[f]}</div>
        </div>""")
    return "\n".join(cards)


def build_html(start, end, total, by_date, by_channel, records, channel_name="武汉-6元"):
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kpi_html = render_kpi_cards(total)
    daily_html = render_daily_with_rates(records)
    channel_html = render_channel_table(by_channel)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{channel_name} · 渠道日报</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;--accent:#3b82f6;--success:#22c55e;--warn:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;padding:16px 24px;max-width:1280px;margin:0 auto}}
.header{{text-align:center;padding:20px 0 8px}}
.header h1{{font-size:24px;margin-bottom:4px}}
.header p{{color:var(--muted);font-size:12px}}
.badge{{display:inline-block;background:linear-gradient(135deg,var(--accent),#6366f1);color:#fff;padding:5px 16px;border-radius:20px;font-size:12px;margin-top:10px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}}
.kpi{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center}}
.kpi-icon{{font-size:24px;margin-bottom:6px}}
.kpi-value{{font-size:28px;font-weight:700;color:var(--accent)}}
.kpi-label{{font-size:12px;color:var(--muted);margin-top:4px}}
.section{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:16px}}
.section h2{{font-size:14px;color:var(--muted);margin-bottom:10px;font-weight:600}}
.table-wrap{{overflow-x:auto;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}}
th{{background:rgba(255,255,255,.04);color:var(--muted);font-weight:600}}
td.num,th{{text-align:right}}
tr:hover{{background:rgba(255,255,255,.02)}}
.empty{{color:var(--muted);padding:20px;text-align:center}}
.footer{{text-align:center;color:var(--muted);font-size:11px;padding:20px 0}}
</style>
</head>
<body>
<div class="header">
  <h1>{channel_name} · 渠道日报</h1>
  <p>数据区间: {start} 至 {end}</p>
  <div class="badge">🕐 更新于 {update_time}</div>
</div>

<div class="kpi-grid">{kpi_html}</div>

<div class="section">
  <h2>📅 每日明细（含渠道与转化率）</h2>
  <div class="table-wrap">{daily_html}</div>
</div>

<div class="section">
  <h2>🏆 渠道汇总（区间累计）</h2>
  <div class="table-wrap">{channel_html}</div>
</div>

<div class="footer">powered by WorkBuddy · qlchat 渠道数据</div>
</body>
</html>"""
    return html


def build_push_content(start, end, total, by_date, channel_name="武汉-6元"):
    """PushPlus 推送 HTML 卡片"""
    update_time = datetime.now().strftime("%m-%d %H:%M")

    if by_date:
        latest_date = max(by_date.keys())
        latest = by_date[latest_date]
    else:
        latest_date = start
        latest = total

    cards = []
    for f, label in [("assign_num", "分配量"), ("friend_num", "加微"),
                     ("group_num", "进群"), ("delete_friend_num", "删友")]:
        cards.append(f"""
        <div style='flex:1;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:10px;text-align:center;min-width:70px'>
          <div style='font-size:18px;font-weight:700;color:#3b82f6'>{fmt_num(latest.get(f, 0))}</div>
          <div style='font-size:11px;color:#94a3b8'>{label}</div>
        </div>""")
    cards_html = "".join(cards)

    return f"""<div style='font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;background:#0f172a;color:#e2e8f0;border-radius:12px;overflow:hidden'>
  <div style='background:linear-gradient(135deg,#3b82f6,#6366f1);padding:14px 18px'>
    <div style='font-size:16px;font-weight:700'>📊 {channel_name} · 渠道日报</div>
    <div style='font-size:11px;opacity:.9;margin-top:2px'>{start} ~ {end} · {update_time} 更新</div>
  </div>
  <div style='padding:14px 18px'>
    <div style='font-size:12px;color:#94a3b8;margin-bottom:6px'>📅 {latest_date} 关键数据</div>
    <div style='display:flex;gap:8px;margin-bottom:14px'>{cards_html}</div>
    <div style='text-align:center;margin-top:8px'>
      <a href='https://jnc121314.github.io/qlchat-dashboard/' style='display:inline-block;background:#3b82f6;color:#fff;padding:8px 18px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600'>📈 查看完整报告</a>
    </div>
  </div>
  <div style='background:rgba(0,0,0,.2);padding:8px 18px;font-size:10px;color:#64748b;text-align:center'>
    powered by WorkBuddy
  </div>
</div>"""


def main():
    data, start, end = load_latest_raw()
    if not data:
        # 数据为空时仍生成空白报告（部署不中断）
        print("⚠️ 没有数据，生成空白报告")
        records = []
        by_date = {}
        by_channel = {}
        total = defaultdict(int)
        start = end = datetime.now().strftime("%Y-%m-%d")
    else:
        records = data.get("data") or []
        print(f"📅 数据区间: {start} ~ {end}, 共 {len(records)} 条记录")
        by_date = aggregate_daily(records)
        by_channel = aggregate_channel(records)
        total = get_total_summary(records)

    cfg_path = CONFIG_FILE
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    channel_name = cfg.get("channelName", "qlchat 渠道")

    html = build_html(start, end, total, by_date, by_channel, records, channel_name)
    push_html = build_push_content(start, end, total, by_date, channel_name)

    out_html = PUBLISH_DIR / "index.html"
    out_push = PUBLISH_DIR / "push_content.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    with open(out_push, "w", encoding="utf-8") as f:
        f.write(push_html)

    print(f"✅ HTML报告: {out_html} ({out_html.stat().st_size} bytes)")
    print(f"✅ 推送内容: {out_push} ({out_push.stat().st_size} bytes)")

    # 输出统计
    print(f"\n📊 关键数据:")
    for f, label in FIELD_NAMES.items():
        print(f"  {label}: {fmt_num(total.get(f, 0))}")


if __name__ == "__main__":
    main()
