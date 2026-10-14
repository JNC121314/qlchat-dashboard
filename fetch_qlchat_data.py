#!/usr/bin/env python3
"""
qlchat 武汉-6元 渠道数据提取
用法:
  python fetch_qlchat_data.py --date 2026-10-13              # 提取单日数据
  python fetch_qlchat_data.py --start 2026-09-01 --end 2026-09-30  # 提取范围
  python fetch_qlchat_data.py --auto                          # 默认昨日
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "channel_config.json"
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_data(sa_token: str, cfg: dict, start: str, end: str, is_summary: str = "N") -> dict:
    """
    is_summary:
      - N  明细(按渠道+按天)
      - Y  汇总(按渠道+按天汇总, channel_name_='-')
      - D  每日合计(按天, 所有渠道合一行)
    """
    body = {
        "startTime": f"{start} 00:00:00",
        "endTime": f"{end} 23:59:59",
        "id": cfg["channelId"],
        "isSummary": is_summary,
        "channelIds": cfg["channelIds"],
        "dataFields": cfg["dataFields"],
    }
    req = urllib.request.Request(
        f"{cfg['apiBase']}/admin/statdata/channelReport/list",
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "sa-token": sa_token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"state": {"code": e.code, "msg": str(e)}, "data": None}
    except Exception as e:
        return {"state": {"code": -1, "msg": str(e)}, "data": None}
    if result.get("state", {}).get("code") != 0:
        sys.stderr.write(f"⚠️ API错误: {result.get('state')}\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="单日 (YYYY-MM-DD)")
    parser.add_argument("--start", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--auto", action="store_true", help="默认昨日")
    parser.add_argument("--isSummary", default="N", choices=["N", "Y", "D"], help="N明细/Y汇总/D每日合计")
    parser.add_argument("--token", help="sa-token (默认从环境变量QLCHAT_SA_TOKEN读取)")
    args = parser.parse_args()

    cfg = load_config()
    sa_token = args.token or os.environ.get("QLCHAT_SA_TOKEN")
    if not sa_token:
        sys.stderr.write("❌ 缺少 sa-token！通过 --token 或环境变量 QLCHAT_SA_TOKEN 提供\n")
        sys.exit(1)

    if args.auto:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start = end = yesterday
    elif args.date:
        start = end = args.date
    elif args.start and args.end:
        start, end = args.start, args.end
    else:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start = end = yesterday

    is_summary_label = {"N": "明细", "Y": "汇总", "D": "每日合计"}[args.isSummary]
    print(f"📅 查询 {start} 至 {end} ({is_summary_label})")

    result = fetch_data(sa_token, cfg, start, end, args.isSummary)
    if result.get("state", {}).get("code") != 0:
        print(f"❌ 提取失败: {result.get('state')}")
        sys.exit(1)

    data = result.get("data") or []
    print(f"✅ 成功获取 {len(data)} 条记录")

    out_name = f"raw_{start}_{end}_{args.isSummary}.json"
    out_path = DATA_DIR / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存: {out_path}")


if __name__ == "__main__":
    main()
