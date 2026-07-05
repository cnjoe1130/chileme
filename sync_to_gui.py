#!/usr/bin/env python3
"""
吃了么 - AI同步脚本（双备份版）
数据同时写入桌面 data/ 和 ~/.nutrition-tracker/data/

用法:
  python3 sync_to_gui.py meal "红烧肉" 450 --meal 午餐
  python3 sync_to_gui.py meal "红烧肉" 450 --meal 午餐 --date 2026-07-03
  python3 sync_to_gui.py weight 72.5
  python3 sync_to_gui.py delete "红烧肉" 450 --meal 午餐
  python3 sync_to_gui.py show          # 查看今天
  python3 sync_to_gui.py show --date 2026-07-03
  python3 sync_to_gui.py recover       # 从备份恢复桌面数据
  python3 sync_to_gui.py status        # 查看双备份状态
"""
import json, sys, argparse, os, shutil
from pathlib import Path
from datetime import datetime

# 双路径：桌面（主）+ 隐藏（备份）
DATA_DIR = Path(__file__).parent / "data"
BACKUP_DIR = Path.home() / ".nutrition-tracker" / "data"
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def today():
    return datetime.now().strftime("%Y-%m-%d")


def now_time():
    return datetime.now().strftime("%H:%M")


def load_day(date):
    """读取：桌面优先，没有则从备份恢复"""
    primary = DATA_DIR / f"{date}.json"
    backup = BACKUP_DIR / f"{date}.json"

    if primary.exists():
        return json.loads(primary.read_text(encoding="utf-8"))

    if backup.exists():
        data = json.loads(backup.read_text(encoding="utf-8"))
        # 自动恢复到桌面
        primary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"🔄 已从备份恢复 {date}.json 到桌面")
        return data

    return {"meals": [], "weights": [], "profile": {}}


def save_day(date, data):
    """写入两处：桌面+隐藏备份"""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"{date}.json").write_text(payload, encoding="utf-8")
    (BACKUP_DIR / f"{date}.json").write_text(payload, encoding="utf-8")


def cmd_meal(args):
    date = args.date or today()
    data = load_day(date)
    entry = {
        "name": args.name,
        "kcal": args.kcal,
        "meal": args.meal,
        "qty": args.qty,
        "unit": args.unit,
        "confidence": "highest",
        "time": now_time()
    }
    data["meals"].append(entry)
    save_day(date, data)
    total = sum(m["kcal"] for m in data["meals"])
    print(f"✅ {args.name} {args.kcal}kcal ({args.meal}) → {date}.json")
    print(f"   今日共 {len(data['meals'])} 条, {total}kcal")


def cmd_weight(args):
    date = args.date or today()
    data = load_day(date)
    data["weights"] = [{"date": date, "value": args.value}]
    save_day(date, data)
    print(f"✅ 体重 {args.value}kg → {date}.json")


def cmd_delete(args):
    date = args.date or today()
    data = load_day(date)
    before = len(data["meals"])
    data["meals"] = [m for m in data["meals"]
                     if not (m["name"] == args.name
                             and m.get("meal") == args.meal)]
    after = len(data["meals"])
    if before == after:
        print(f"⚠️ 未找到: {args.name} ({args.meal})")
    else:
        save_day(date, data)
        print(f"🗑️ 已删除 {before - after} 条: {args.name} ({args.meal})")


def cmd_show(args):
    date = args.date or today()
    data = load_day(date)
    meals = data.get("meals", [])
    total = sum(m["kcal"] for m in meals)
    print(f"📊 {date} — {len(meals)}条, {total}kcal")
    for m in meals:
        unit = f" {m['unit']}" if m.get("unit") else ""
        qty = f" ×{m['qty']}" if m.get("qty", 1) > 1 else ""
        print(f"  {m['meal']}: {m['name']}{unit}{qty} {m['kcal']}kcal")
    weights = data.get("weights", [])
    if weights:
        print(f"  体重: {weights[-1]['value']}kg")


def cmd_recover(args):
    """从备份恢复所有数据到桌面"""
    recovered = []
    for f in BACKUP_DIR.glob("*.json"):
        target = DATA_DIR / f.name
        if not target.exists():
            shutil.copy2(f, target)
            recovered.append(f.name)
    if recovered:
        print(f"🌟 超级人工智能帮您妙手回春！")
        print(f"   已恢复 {len(recovered)} 个文件:")
        for name in recovered:
            print(f"   ✅ {name}")
    else:
        print("✅ 桌面数据完整，无需恢复")


def cmd_status(args):
    """查看双备份状态"""
    primary = sorted(DATA_DIR.glob("*.json"))
    backup = sorted(BACKUP_DIR.glob("*.json"))
    print(f"📂 桌面数据 ({DATA_DIR}/): {len(primary)} 个文件")
    for f in primary:
        print(f"   {f.name}")
    print(f"🔒 备份数据 ({BACKUP_DIR}/): {len(backup)} 个文件")
    for f in backup:
        print(f"   {f.name}")
    # 检查差异
    p_names = {f.name for f in primary}
    b_names = {f.name for f in backup}
    missing = b_names - p_names
    if missing:
        print(f"⚠️ 桌面缺失（备份有）: {', '.join(missing)}")
    extra = p_names - b_names
    if extra:
        print(f"ℹ️ 备份缺失（桌面有）: {', '.join(extra)}")


def main():
    p = argparse.ArgumentParser(description="吃了么 - AI同步（双备份）")
    sub = p.add_subparsers(dest="cmd")

    m = sub.add_parser("meal", help="记录食物")
    m.add_argument("name")
    m.add_argument("kcal", type=int)
    m.add_argument("--meal", default="午餐")
    m.add_argument("--qty", type=float, default=1)
    m.add_argument("--unit", default="")
    m.add_argument("--date")

    w = sub.add_parser("weight", help="记录体重")
    w.add_argument("value", type=float)
    w.add_argument("--date")

    d = sub.add_parser("delete", help="删除食物")
    d.add_argument("name")
    d.add_argument("kcal", type=int, nargs="?", default=0)
    d.add_argument("--meal", default="")
    d.add_argument("--date")

    s = sub.add_parser("show", help="查看数据")
    s.add_argument("--date")

    sub.add_parser("recover", help="从备份恢复桌面数据")
    sub.add_parser("status", help="查看双备份状态")

    args = p.parse_args()
    if args.cmd == "meal":
        cmd_meal(args)
    elif args.cmd == "weight":
        cmd_weight(args)
    elif args.cmd == "delete":
        cmd_delete(args)
    elif args.cmd == "show":
        cmd_show(args)
    elif args.cmd == "recover":
        cmd_recover(args)
    elif args.cmd == "status":
        cmd_status(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
