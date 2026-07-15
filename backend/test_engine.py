"""测试感情刀引擎启动 → 跑一轮 → daily_records 写入"""
import asyncio, sys, logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.WARNING)

from app.services.engine import get_or_create_engine
from app.core.database import AsyncSessionLocal
from sqlalchemy import text
from datetime import date


async def main():
    account_id = "cdc14c665947"
    print(f"\n=== 测试引擎: {account_id} ===\n")

    print("[1] 创建引擎...")
    engine = await get_or_create_engine(account_id)
    if not engine:
        print("FAIL: 引擎创建失败")
        return

    print("[2] 调用 mgr.start() 完整启动流程...")
    ok = await engine.start()
    if not ok:
        print("FAIL: 启动失败")
        return
    print("    引擎已启动！")

    print("[3] 等待主循环完成 (max 120s)...")
    try:
        await asyncio.wait_for(engine.full_auto_cycle(), timeout=120)
    except asyncio.TimeoutError:
        print("WARN: 超时")

    print("[4] 检查 daily_records...")
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text("SELECT * FROM daily_records WHERE account_id=:aid AND date=:d"),
            {"aid": account_id, "d": date.today()},
        )
        row = r.fetchone()
        if row:
            cols = ["id","account_id","date","level","class_name","combat_power","npc_fights","tower_floors","tower_max",
                    "friend_fights","harvests","plants","steals","waters","help_waters","farm_ads","stamina_ads",
                    "diversity","coll_crops","coll_slots","exp_visit","current_exp","exp_battle","today_harvest_exp",
                    "stamina","max_stamina","level_exp","level_exp_max","gang_contribution","abyss_tickets","updated_at",
                    "community_ads","digs","land_upgrades","research_points_earned","research_points_spent"]
            print(f"    ✅ 写入成功:")
            for i, c in enumerate(cols):
                if i >= 3 and row[i] is not None and row[i] != 0:
                    print(f"       {c}={row[i]}")
        else:
            print("    ❌ 今日无记录")

    print("[5] 停止引擎...")
    await engine.stop()
    print("    已停止")


if __name__ == "__main__":
    asyncio.run(main())
