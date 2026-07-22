"""账号数据 API — 透传游戏 API 原始数据给 Dashboard 前端"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.core.redis import cache_get, cache_set
from app.core.logger import action, info, warn
from app.services.account_manager import list_accounts as get_all_accounts
from app.services.engine import get_engine, get_or_create_engine
from app.services.farm.query import FarmQuery
from app.core.database import AsyncSessionLocal
from app.models.account import Account
from app.models.user import User, UserAccount
import json

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

CACHE_TTL = 300  # 5 minutes


async def _redis_or_fetch(account_id: str, key: str, fetcher):
    """先从 Redis 读缓存，miss 则调游戏 API 并回写缓存"""
    cache_key = f"qpet:{account_id}:{key}"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    engine = get_engine(account_id)
    if not engine or not engine.client:
        return None

    result = await engine.cached_get(key, lambda: fetcher(engine.client))
    if result.get("success"):
        data = result.get("data", result)
        try:
            await cache_set(cache_key, json.dumps(data), CACHE_TTL)
        except Exception:
            pass
        return data
    return None


@router.get("")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    accounts = await get_all_accounts(db)

    # Filter by user: admin sees all, regular users see only their bound accounts
    role = user.get("role") or user.get("role")
    if user and role != "admin":
        user_id = user.get("user_id") or user.get("userId")
        account_ids = user.get("account_ids") or user.get("accountIds") or []
        bound_ids = set(account_ids)
        if user_id:
            result = await db.execute(
                select(UserAccount.account_id).where(UserAccount.user_id == user_id)
            )
            bound_ids |= {row[0] for row in result.fetchall()}
        accounts = [a for a in accounts if a["id"] in bound_ids]

    return {"success": True, "data": accounts}


@router.get("/{account_id}/farm")
async def get_account_farm(account_id: str, _user: dict = Depends(get_current_user)):
    cache_key = f"qpet:{account_id}:farm"

    # 先查 Redis 缓存
    cached = await cache_get(cache_key)
    if cached:
        try:
            return {"success": True, "data": json.loads(cached)}
        except Exception:
            pass

    # 农场计数统一从 daily_records 查表，与引擎是否在线无关
    from datetime import date
    from sqlalchemy import select
    from app.models.daily_record import DailyRecord
    from app.core.database import AsyncSessionLocal
    db = AsyncSessionLocal()
    try:
        r = await db.execute(
            select(DailyRecord).where(
                DailyRecord.account_id == account_id,
                DailyRecord.date == date.today(),
            )
        )
        row = r.scalar_one_or_none()
        db_counts = {
            "todayStealCount": row.steals if row else 0,
            "todayDigCount": row.digs if row else 0,
            "todayHarvestExp": row.today_harvest_exp if row else 0,
            "todayCareCount": row.waters if row else 0,
        }
    except Exception:
        db_counts = {}
    finally:
        await db.close()

    engine = get_engine(account_id)
    if not engine or not engine.farm_status:
        data = db_counts
    else:
        status = await engine.farm_status.get()
        if status:
            status.update(db_counts)
            data = status
        else:
            data = db_counts

    try:
        await cache_set(cache_key, json.dumps(data), 60)
    except Exception:
        pass
    return {"success": True, "data": data}


@router.get("/{account_id}/gang-boss")
async def get_account_gang_boss(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "gang-boss", lambda c: c.get_gang_boss_status())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取帮派BOSS失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/gang-status")
async def get_gang_status_db(account_id: str, _user: dict = Depends(get_current_user)):
    """从DB读取帮派持久化数据（帮派信息+技能+BOSS+成员）"""
    from sqlalchemy import select
    from app.models.gang_member import GangMember
    from app.models.gang_status import GangStatus
    from app.models.gang_skill import GangSkill
    from app.models.gang_skill_config import GangSkillConfig
    from app.models.gang_boss import GangBoss
    from app.models.gang_boss_config import GangBossConfig

    db = AsyncSessionLocal()
    try:
        # 先查该account对应的gang_id
        member_row = await db.execute(
            select(GangMember).where(GangMember.account_id == account_id)
        )
        member = member_row.scalar_one_or_none()
        if not member:
            return {"success": False, "message": "未加入帮派或数据未同步"}

        gid = member.gang_id

        # 帮派状态
        gang_row = await db.execute(select(GangStatus).where(GangStatus.gang_id == gid))
        gang = gang_row.scalar_one_or_none()

        # 技能
        skills_row = await db.execute(
            select(GangSkill, GangSkillConfig)
            .join(GangSkillConfig, GangSkill.skill_name == GangSkillConfig.name)
            .where(GangSkill.gang_id == gid)
            .order_by(GangSkillConfig.sort_order)
        )
        skills = [
            {"name": s.skill_name, "level": s.current_level,
             "description": cfg.description, "max_level": cfg.max_level,
             "cost_per_level": cfg.cost_per_level, "min_gang_level": cfg.min_gang_level,
             "hp_per_level": cfg.hp_per_level, "atk_per_level": cfg.atk_per_level}
            for s, cfg in skills_row.all()
        ]

        # BOSS
        bosses_row = await db.execute(
            select(GangBoss, GangBossConfig)
            .join(GangBossConfig, GangBoss.boss_id == GangBossConfig.boss_id)
            .where(GangBoss.gang_id == gid)
            .order_by(GangBossConfig.sort_order)
        )
        bosses = [
            {"boss_id": b.boss_id, "name": cfg.name, "boss_level": cfg.boss_level,
             "min_gang_level": cfg.min_gang_level,
             "unlocked": b.unlocked, "free_challenge_done": b.free_challenge_done}
            for b, cfg in bosses_row.all()
        ]

        # 成员
        members_row = await db.execute(
            select(GangMember).where(GangMember.gang_id == gid)
            .order_by(GangMember.contribution.desc())
        )
        members = [
            {"user_id": m.user_id, "nickname": m.nickname, "role": m.role,
             "contribution": m.contribution, "account_id": m.account_id}
            for m in members_row.scalars().all()
        ]

        return {"success": True, "data": {
            "gang_id": gid,
            "name": gang.name if gang else "",
            "level": gang.level if gang else 1,
            "notice": gang.notice if gang else "",
            "accumulated_contribution": gang.accumulated_contribution if gang else 0,
            "guardian_level": gang.guardian_level if gang else 0,
            "member_count": gang.member_count if gang else 0,
            "next_level": gang.next_level if gang else 0,
            "next_need_contrib": gang.next_need_contrib if gang else 0,
            "next_member_limit": gang.next_member_limit if gang else 0,
            "level_progress": gang.level_progress if gang else 0,
            "my_role": member.role,
            "my_contribution": member.contribution,
            "skills": skills,
            "bosses": bosses,
            "members": members,
        }}
    finally:
        await db.close()


@router.get("/{account_id}/equipment")
async def get_account_equipment(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "equipment", lambda c: c.get_equipment())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取装备失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/inventory")
async def get_account_inventory(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "inventory", lambda c: c.get_inventory())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取背包失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/character")
async def get_account_character(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "character", lambda c: c.get_character())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取角色失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/skill-tree")
async def get_account_skill_tree(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "skill-tree", lambda c: c.get_skill_tree())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取技能树失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/gang")
async def get_account_gang(account_id: str, _user: dict = Depends(get_current_user)):
    data = await _redis_or_fetch(account_id, "gang", lambda c: c.get_gang_status())
    if data is None:
        return {"success": False, "message": "引擎未运行或获取帮派失败"}
    return {"success": True, "data": data}


@router.get("/{account_id}/sso-data")
async def get_account_sso(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine.client:
        return {"success": False, "message": "引擎未运行"}

    jwk = getattr(engine.client, '_ecdsa_jwk', None)
    if not jwk and engine.client.private_key:
        from app.core.crypto import export_private_jwk
        engine.client._ecdsa_jwk = export_private_jwk(engine.client.private_key)
        jwk = engine.client._ecdsa_jwk

    return {"success": True, "data": {
        "token": engine.client.token or "",
        "jwk": jwk or {},
    }}


@router.post("/{account_id}/start")
async def start_account(account_id: str, _user: dict = Depends(get_current_user)):
    engine = await get_or_create_engine(account_id)
    if not engine:
        return {"success": False, "message": "账号不存在"}
    if engine._running:
        return {"success": True, "message": "已在运行中"}
    ok = await engine.start()
    if not ok:
        warn("系统", "管理", f"引擎启动失败: {account_id}", account_id)
        return {"success": False, "message": "引擎启动失败，请检查账号凭证是否有效"}
    action("系统", "管理", f"用户手动启动引擎: {account_id}", account_id)
    return {"success": True, "message": "引擎已启动"}


@router.post("/{account_id}/stop")
async def stop_account(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine._running:
        # 内存无引擎（启动失败/进程重启后状态丢失），兜底复位 DB 标志，保证能重新启动
        async with AsyncSessionLocal() as db:
            acc = await db.get(Account, account_id)
            if acc and acc.running:
                acc.running = 0
                await db.commit()
                action("系统", "管理", f"引擎状态复位(内存缺失): {account_id}", account_id)
                return {"success": True, "message": "引擎已停止(状态已复位)"}
        return {"success": False, "message": "引擎未运行"}
    await engine.stop()
    action("系统", "管理", f"用户手动停止引擎: {account_id}", account_id)
    return {"success": True, "message": "引擎已停止"}


# ——— 博物馆 / 图鉴 / 土地 ——— 从 DB 查表，不调游戏 API ———
# 注意：必须在 /{account_id}/{action} 通配路由之前注册，否则会被拦截

@router.get("/{account_id}/museum-progress")
async def get_museum_progress(account_id: str, _user: dict = Depends(get_current_user)):
    q = FarmQuery(AsyncSessionLocal)
    data = await q.museum_progress(account_id)
    return {"success": True, "data": data}


@router.get("/{account_id}/collection-progress")
async def get_collection_progress(account_id: str, _user: dict = Depends(get_current_user)):
    q = FarmQuery(AsyncSessionLocal)
    data = await q.collection_progress(account_id)
    return {"success": True, "data": data}


@router.get("/{account_id}/inventory-progress")
async def get_inventory_progress(account_id: str, _user: dict = Depends(get_current_user)):
    q = FarmQuery(AsyncSessionLocal)
    data = await q.inventory(account_id)
    return {"success": True, "data": data}


@router.get("/{account_id}/land-status")
async def get_land_status(account_id: str, _user: dict = Depends(get_current_user)):
    q = FarmQuery(AsyncSessionLocal)
    data = await q.land_status(account_id)
    if data is None:
        return {"success": False, "message": "暂无土地数据"}
    return {"success": True, "data": data}


@router.post("/{account_id}/sync-farm")
async def sync_farm_data(account_id: str, _user: dict = Depends(get_current_user)):
    """手动触发农场数据同步：调游戏API获取最新museum/collection/land，写入DB"""
    from app.services.farm.sync import FarmSync
    from app.services.farm.query import FarmQuery

    engine = get_engine(account_id)
    if not engine or not engine.farm_status:
        return {"success": False, "message": "引擎未运行，无法获取农场数据"}

    status = await engine.farm_status.get()
    if not status:
        return {"success": False, "message": "获取农场状态失败"}

    sync = FarmSync(AsyncSessionLocal)
    result = await sync.sync_all(account_id, status)

    return {
        "success": True,
        "message": f"museum:{result['museum']} collection:{result['collection']} land:{result['land']}",
        "data": result,
    }


@router.post("/{account_id}/sync-daily")
async def sync_daily_record(account_id: str, _user: dict = Depends(get_current_user)):
    """手动触发每日记录持久化：刷新角色快照+计数器写入daily_records"""
    engine = get_engine(account_id)
    if not engine or not engine._running:
        return {"success": False, "message": "引擎未运行"}

    # 确保客户端就绪
    if not getattr(engine.client, 'private_key', None):
        await engine.client.ensure_ecdsa_ready()

    diag = {}

    # 背包同步（更新深渊票等缓存）
    await engine._sync_inventory_to_db()

    # 帮派BOSS状态（更新今日次数+贡献，次数=贡献/10）
    try:
        gb = await engine.client.get_gang_boss_status()
        if gb.get("success") and gb.get("data"):
            d = gb["data"]
            contrib = sum(
                b.get("todayContribEarned", 0) or 0 for b in d.get("bossList", [])
            )
            engine.gang_boss.today_contrib = contrib
            engine.gang_boss.today_fights = contrib // 10
            engine.gang_boss.challenge_books = d.get("challengeBookCount", 0)
    except Exception:
        pass

    # 社区广告次数
    try:
        ad = await engine.client.community_get_ad_status()
        if ad.get("success") and ad.get("data"):
            engine.ad_community.today_count = ad["data"].get("todayCount", 0)
        else:
            engine.ad_community.today_count = 0
    except Exception:
        engine.ad_community.today_count = 0

    # 挑战书购买次数
    try:
        shop = await engine.client.get_shop_status()
        if shop.get("success") and shop.get("data"):
            cb = shop["data"].get("challenge_book", {}) or {}
            engine.shop_special.today_count = cb.get("used", 0) or 0
        else:
            engine.shop_special.today_count = 0
    except Exception:
        engine.shop_special.today_count = 0

    # 还魂丹（塔状态 API）
    try:
        tower = await engine.client.get_tower_status()
        if tower.get("success") and tower.get("data"):
            engine._tower_revive = tower["data"].get("reviveCount", 0)
    except Exception:
        pass

    # 仓库鲜花（商店API — flower.flowerStock）
    try:
        shop = await engine.client.get_shop_status()
        if shop.get("success") and shop.get("data"):
            flower = shop["data"].get("flower", {}) or {}
            engine.shop_special.flower_stock = flower.get("flowerStock", 0)
    except Exception:
        pass

    # 广告次数（从各广告API同步真实计数）
    try:
        sa = await engine.client.get_ad_stamina_status()
        if sa.get("success") and sa.get("data"):
            engine.ad_stamina.today_count = sa["data"].get("todayCount", 0)
    except Exception:
        pass
    try:
        fa = await engine.client.farm_get_ad_status()
        if fa.get("success") and fa.get("data"):
            engine.ad_farm.today_count = fa["data"].get("todayCount", 0)
    except Exception:
        pass
    try:
        ca = await engine.client.community_get_ad_status()
        if ca.get("success") and ca.get("data"):
            engine.ad_community.today_count = ca["data"].get("todayCount", 0)
    except Exception:
        pass

    await engine._persist_daily()
    return {"success": True, "message": "每日记录已同步", "diag": diag}


@router.post("/{account_id}/sync-gang")
async def sync_gang_data(account_id: str, _user: dict = Depends(get_current_user)):
    """手动触发帮派数据同步：拉取帮派状态+BOSS数据，写入gang_status等6表"""
    engine = get_engine(account_id)
    if not engine or not engine._running:
        return {"success": False, "message": "引擎未运行"}

    if not getattr(engine.client, 'private_key', None):
        await engine.client.ensure_ecdsa_ready()

    from app.services.gang_sync import GangSync
    from app.core.database import AsyncSessionLocal

    gang = await engine.client.get_gang_status()
    if not gang.get("success"):
        return {"success": False, "message": "获取帮派状态失败"}

    boss = await engine.client.get_gang_boss_status()

    sync = GangSync(AsyncSessionLocal)
    result = await sync.sync_all(account_id, gang.get("data", {}), boss)

    # 更新 member_count
    member_count = len(gang.get("data", {}).get("members", []))
    return {
        "success": True,
        "message": f"帮派同步完成: {result['gang']} {result['skills']}技能 {result['bosses']}BOSS {member_count}成员",
        "data": result,
    }


@router.put("/{account_id}/credentials")
async def update_credentials(account_id: str, body: dict, db: AsyncSession = Depends(get_db), _user: dict = Depends(get_current_user)):
    """更新账号的用户名和密码"""
    from app.models.account import Account
    from app.core.crypto import encrypt_password

    result = await db.execute(select(Account).where(Account.id == account_id))
    row = result.scalar_one_or_none()
    if not row:
        return {"success": False, "message": "账号不存在"}

    if body.get("username"):
        row.username = body["username"]
    if body.get("password"):
        row.password = encrypt_password(body["password"])

    await db.commit()
    info("系统", "管理", f"凭证已更新: {account_id}", account_id)

    # 如果引擎在运行，更新内存中的凭证 + 重置密钥对
    engine = get_engine(account_id)
    if engine and engine.mgr:
        engine.mgr.username = row.username
        engine.mgr.password_encrypted = row.password
        if engine.client:
            engine.client.delete_key()
            await engine.client.ensure_ecdsa_ready()

    return {"success": True, "data": {
        "username": row.username,
        "password_masked": "********" if row.password else "",
    }}


@router.post("/{account_id}/regenerate-key")
async def regenerate_key(account_id: str, _user: dict = Depends(get_current_user)):
    """重新生成 ECDSA 签名密钥（用于密钥失效时）"""
    engine = get_engine(account_id)
    if not engine or not engine.client:
        return {"success": False, "message": "引擎未运行，请先启引擎再生成密钥"}

    # 删旧密钥 + 重新生成注册
    engine.client.delete_key()
    ok = await engine.client.ensure_ecdsa_ready()
    if ok:
        action("系统", "管理", f"ECDSA密钥已重新生成: {account_id}", account_id)
        return {"success": True, "message": "ECDSA 密钥已重新生成并注册"}
    warn("系统", "管理", f"密钥生成失败: {account_id}", account_id)
    return {"success": False, "message": "密钥生成失败"}


@router.get("/{account_id}/credentials")
async def get_credentials(account_id: str, _user: dict = Depends(get_current_user)):
    """获取账号的账密信息（密码脱敏）"""
    from app.models.account import Account
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Account).where(Account.id == account_id))
        row = result.scalar_one_or_none()
        if not row:
            return {"success": False, "message": "账号不存在"}

        return {"success": True, "data": {
            "username": row.username or "",
            "has_password": bool(row.password),
        }}


@router.get("/{account_id}/chest-records")
async def get_chest_records(account_id: str, limit: int = 30, _user: dict = Depends(get_current_user)):
    """查询宝箱开启记录"""
    from sqlalchemy import select, desc
    from app.models.chest_record import ChestRecord
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(ChestRecord)
            .where(ChestRecord.account_id == account_id)
            .order_by(desc(ChestRecord.opened_at))
            .limit(min(limit, 200))
        )
        rows = r.scalars().all()
        return {"success": True, "data": [
            {
                "id": row.id,
                "opened_at": row.opened_at.isoformat(),
                "cost": row.cost,
                "drops": row.drops,
                "total_opens": row.total_opens,
                "date_key": row.date_key,
            }
            for row in rows
        ]}


@router.post("/{account_id}/refresh-marriage")
async def refresh_marriage(account_id: str, _user: dict = Depends(get_current_user)):
    """返回婚姻信息：引擎内存 → Redis缓存 → 游戏API 三级降级"""
    cache_key = f"qpet:{account_id}:marriage"
    engine = get_engine(account_id)
    if not engine or not engine._running:
        # 引擎未运行，尝试返回 Redis 缓存
        cached = await cache_get(cache_key)
        if cached:
            try:
                return {"success": True, "data": json.loads(cached)}
            except Exception:
                pass
        return {"success": False, "message": "引擎未运行"}

    # 始终走 _get_marriage_info（它内部已有 L1/L2/L3 降级）
    info = await engine._get_marriage_info()
    try:
        await cache_set(cache_key, json.dumps(info), 600)
    except Exception:
        pass
    return {"success": True, "data": info}


@router.post("/{account_id}/{action}")
async def trigger_action(account_id: str, action: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine:
        return {"success": False, "message": "引擎不存在"}
    if not engine._running:
        return {"success": False, "message": "引擎未运行"}

    if action == "cycle":
        await engine.full_auto_cycle()
    elif action == "fight":
        await engine._run_battle()
    elif action == "farm":
        await engine._run_farm()
    elif action == "checkin":
        await engine.checkin.run()
    else:
        return {"success": False, "message": f"未知操作: {action}"}

    info("系统", "管理", f"用户手动触发: {action}", account_id)
    return {"success": True, "message": f"{action} 已触发"}
