"""博物馆碎片交易调度器 — 每10分钟自动匹配+执行交易

流程（每账号）：
  1. 资格检查：今日翻地>=50 且 今日交易==0
  2. 处理待接受：查 museum_trade WHERE target_id=自己 AND status='pending'
     校验 unique_code → 调游戏API接受 → 扣加碎片 → 更新状态
  3. 匹配发起：查自己 surplus/deficit → 配对其他账号 → 创建交易 → 立即接受
"""
import asyncio
import logging
import uuid
from datetime import date
from sqlalchemy import select, or_, and_
from app.core.database import AsyncSessionLocal
from app.models import PlayerMuseum, MuseumTrade, MuseumCatalog
from app.models.daily_record import DailyRecord
from app.models.account import Account
from app.services.engine import get_engine

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600  # 10 分钟


async def run_museum_trade_cycle():
    """主循环：遍历所有运行中账号，执行三步流程"""
    from app.services.engine import _engines

    today = date.today()

    for account_id, engine in list(_engines.items()):
        if not engine._running:
            continue

        try:
            await _process_account(account_id, engine, today)
        except Exception as e:
            logger.error(f"[{account_id}] 博物馆交易循环异常: {e}")


async def _process_account(account_id: str, engine, today: date):
    """处理单个账号的三步流程"""

    # === Step 1: 资格检查 ===
    digs, traded = await _get_today_counts(account_id, today)
    if digs < 50:
        return
    if traded >= 1:
        return

    # === Step 2: 处理待接受 ===
    pending = await _get_pending_incoming(account_id)
    if pending:
        for trade in pending:
            ok = await _accept_trade(trade, engine, today)
            if ok:
                logger.info(f"[{account_id}] 自动接受交易 {trade.id} 成功")
                return  # 每人每天只处理一次交易
        return

    # === Step 3: 匹配发起 ===
    await _match_and_create(account_id, engine, today)


async def _get_today_counts(account_id: str, today: date) -> tuple[int, int]:
    """查询今日翻地数和交易数"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(DailyRecord).where(
                DailyRecord.account_id == account_id,
                DailyRecord.date == today,
            )
        )
        row = r.scalar_one_or_none()
        if not row:
            return 0, 0
        return row.digs or 0, row.museum_trades or 0


async def _get_pending_incoming(account_id: str) -> list[MuseumTrade]:
    """查询待接受的交易（别人发给我的）"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(MuseumTrade).where(
                MuseumTrade.target_id == account_id,
                MuseumTrade.status == "pending",
            )
            .order_by(MuseumTrade.created_at.asc())
            .limit(1)
        )
        return r.scalars().all()


async def _accept_trade(trade: MuseumTrade, engine, today: date) -> bool:
    """接受一笔交易：校验→调API→扣加碎片→更新状态"""
    # 校验 unique_code == message
    if trade.unique_code != trade.message:
        logger.warning(f"[{trade.target_id}] 交易 {trade.id} 唯一码不匹配，拒绝")
        await _update_trade_status(trade.id, "rejected")
        return False

    # 校验双方 tradeable 是否充足
    ok = await _check_tradeable_sufficient(trade)
    if not ok:
        logger.warning(f"[{trade.target_id}] 交易 {trade.id} 碎片不足，标记拒绝")
        await _update_trade_status(trade.id, "rejected")
        return False

    # 调游戏 API 接受（需要 target 方的客户端）
    target_engine = get_engine(trade.target_id)
    if not target_engine or not target_engine._running:
        logger.warning(f"[{trade.target_id}] 目标引擎未运行，跳过接受")
        return False

    if not target_engine.client or not getattr(target_engine.client, '_ready', False):
        await target_engine.client.ensure_ecdsa_ready()

    user_id = target_engine.mgr.user_id if hasattr(target_engine.mgr, 'user_id') else 0
    if not user_id:
        logger.warning(f"[{trade.target_id}] 缺少游戏 user_id，跳过接受")
        return False

    # 调游戏 API 接受
    result = await target_engine.client.accept_museum_trade(trade.game_trade_id)
    if not result.get("success"):
        logger.warning(f"[{trade.target_id}] 接受交易 API 失败: {result.get('message')}")
        return False

    # 扣加双方碎片
    await _apply_trade(trade)

    # 更新双方 daily_record
    await _set_traded(trade.initiator_id, today)
    await _set_traded(trade.target_id, today)

    # 更新 trade 状态
    await _update_trade_status(trade.id, "accepted")

    logger.info(f"交易 {trade.id} 完成: {trade.initiator_id} 提供 {trade.offer_item_id}x{trade.offer_quantity}"
                f" ↔ {trade.target_id} 提供 {trade.want_item_id}x{trade.want_quantity}")
    return True


async def _check_tradeable_sufficient(trade: MuseumTrade) -> bool:
    """校验双方剩余碎片是否充足"""
    async with AsyncSessionLocal() as db:
        # 发起方 offer 碎片
        r1 = await db.execute(
            select(PlayerMuseum).where(
                PlayerMuseum.account_id == trade.initiator_id,
                PlayerMuseum.item_id == trade.offer_item_id,
            )
        )
        init_row = r1.scalar_one_or_none()
        if not init_row or init_row.tradeable_fragments < trade.offer_quantity:
            return False

        # 目标方 want 碎片（注意：在 trade 中 want 是发起方想要的 = 目标方提供的）
        r2 = await db.execute(
            select(PlayerMuseum).where(
                PlayerMuseum.account_id == trade.target_id,
                PlayerMuseum.item_id == trade.want_item_id,
            )
        )
        target_row = r2.scalar_one_or_none()
        if not target_row or target_row.tradeable_fragments < trade.want_quantity:
            return False

        return True


async def _apply_trade(trade: MuseumTrade):
    """扣减双方 tradeable_fragments，增加对应 fragment_count"""
    async with AsyncSessionLocal() as db:
        try:
            # 扣发起方 offer
            r1 = await db.execute(
                select(PlayerMuseum).where(
                    PlayerMuseum.account_id == trade.initiator_id,
                    PlayerMuseum.item_id == trade.offer_item_id,
                )
            )
            init_row = r1.scalar_one_or_none()
            if init_row:
                init_row.tradeable_fragments -= trade.offer_quantity

            # 扣目标方 want
            r2 = await db.execute(
                select(PlayerMuseum).where(
                    PlayerMuseum.account_id == trade.target_id,
                    PlayerMuseum.item_id == trade.want_item_id,
                )
            )
            target_row = r2.scalar_one_or_none()
            if target_row:
                target_row.tradeable_fragments -= trade.want_quantity

            # 发起方获得 want 碎片
            init_want = await db.execute(
                select(PlayerMuseum).where(
                    PlayerMuseum.account_id == trade.initiator_id,
                    PlayerMuseum.item_id == trade.want_item_id,
                )
            )
            iw = init_want.scalar_one_or_none()
            if iw:
                iw.fragment_count += trade.want_quantity
                # 检查是否达成修复
                cat_r = await db.execute(
                    select(MuseumCatalog).where(MuseumCatalog.item_id == trade.want_item_id)
                )
                cat = cat_r.scalar_one_or_none()
                if cat and iw.fragment_count >= cat.fragments_needed:
                    iw.is_repaired = True
                    iw.status = "成"
                    iw.tradeable_fragments = iw.fragment_count - cat.fragments_needed

            # 目标方获得 offer 碎片
            target_offer = await db.execute(
                select(PlayerMuseum).where(
                    PlayerMuseum.account_id == trade.target_id,
                    PlayerMuseum.item_id == trade.offer_item_id,
                )
            )
            to = target_offer.scalar_one_or_none()
            if to:
                to.fragment_count += trade.offer_quantity
                cat_r = await db.execute(
                    select(MuseumCatalog).where(MuseumCatalog.item_id == trade.offer_item_id)
                )
                cat = cat_r.scalar_one_or_none()
                if cat and to.fragment_count >= cat.fragments_needed:
                    to.is_repaired = True
                    to.status = "成"
                    to.tradeable_fragments = to.fragment_count - cat.fragments_needed

            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _set_traded(account_id: str, today: date):
    """标记该账号今日已交易"""
    async with AsyncSessionLocal() as db:
        try:
            r = await db.execute(
                select(DailyRecord).where(
                    DailyRecord.account_id == account_id,
                    DailyRecord.date == today,
                )
            )
            row = r.scalar_one_or_none()
            if row:
                row.museum_trades = 1
            else:
                db.add(DailyRecord(
                    account_id=account_id,
                    date=today,
                    museum_trades=1,
                ))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _update_trade_status(trade_id: int, status: str):
    """更新交易状态"""
    async with AsyncSessionLocal() as db:
        try:
            r = await db.execute(select(MuseumTrade).where(MuseumTrade.id == trade_id))
            trade = r.scalar_one_or_none()
            if trade:
                trade.status = status
                await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _match_and_create(account_id: str, engine, today: date):
    """匹配并创建交易"""
    # 当前账号的 surplus 和 deficit
    surplus, deficit = await _get_account_surplus_deficit(account_id)
    if not surplus:
        return

    # 获取其他运行中账号的 surplus 和 deficit
    from app.services.engine import _engines
    candidates = []
    for oid, oengine in list(_engines.items()):
        if oid == account_id or not oengine._running:
            continue
        odigs, otradef = await _get_today_counts(oid, today)
        if odigs < 50 or otradef >= 1:
            continue
        # 目标账号也需要有 user_id
        ouid = oengine.mgr.user_id if hasattr(oengine.mgr, 'user_id') else 0
        if not ouid:
            continue
        osurplus, odef = await _get_account_surplus_deficit(oid)
        if not osurplus:
            continue
        candidates.append((oid, ouid, osurplus, odef))

    if not candidates:
        return

    # 两两匹配：我有余X 且 缺Y 且 X.rarity == Y.rarity
    for my_item_id, my_qty in surplus.items():
        if my_qty <= 0:
            continue

        # 查 rarity
        my_rarity = await _get_item_rarity(my_item_id)
        if not my_rarity:
            continue

        for oid, ouid, osurplus, odef in candidates:
            for their_item_id, their_qty in osurplus.items():
                if their_qty <= 0:
                    continue
                their_rarity = await _get_item_rarity(their_item_id)
                if not their_rarity or their_rarity != my_rarity:
                    continue

                # 我缺 their_item 且 对方缺 my_item
                if their_item_id not in deficit:
                    continue
                if my_item_id not in odef:
                    continue

                # 数量取 min
                quantity = min(my_qty, their_qty)

                # 创建 trade：我发起，给 my_item_id，要 their_item_id
                unique_code = f"MT-{uuid.uuid4().hex[:8].upper()}"
                game_trade_id = await _call_create_trade(
                    engine, ouid, my_item_id, quantity, their_item_id, quantity, unique_code
                )
                if not game_trade_id:
                    continue

                # 入库
                trade_id = await _save_trade(
                    account_id, oid, my_item_id, quantity,
                    their_item_id, quantity, unique_code, game_trade_id
                )

                if trade_id:
                    # 标记发起方今日已交易
                    await _set_traded(account_id, today)
                    logger.info(f"[{account_id}] 创建交易 {trade_id} (game_id={game_trade_id}): "
                                f"给 {my_item_id}x{quantity} 换 {their_item_id}x{quantity}")
                return  # 每人每天只处理一次


async def _get_account_surplus_deficit(account_id: str) -> tuple[dict[str, int], dict[str, int]]:
    """查询账号的盈余碎片和缺失碎片"""
    surplus = {}
    deficit = {}

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(PlayerMuseum, MuseumCatalog)
            .join(MuseumCatalog, PlayerMuseum.item_id == MuseumCatalog.item_id)
            .where(PlayerMuseum.account_id == account_id)
        )
        for pm, mc in rows.all():
            if pm.tradeable_fragments > 0:
                surplus[pm.item_id] = pm.tradeable_fragments
            if not pm.is_repaired:
                need = mc.fragments_needed - pm.fragment_count
                if need > 0:
                    deficit[pm.item_id] = need

    return surplus, deficit


async def _get_item_rarity(item_id: str) -> str | None:
    """查藏品稀有度"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(MuseumCatalog).where(MuseumCatalog.item_id == item_id)
        )
        cat = r.scalar_one_or_none()
        return cat.rarity if cat else None


async def _call_create_trade(
    engine, target_user_id: int,
    offer_item_id: str, offer_qty: int,
    want_item_id: str, want_qty: int,
    unique_code: str,
) -> int | None:
    """调游戏API发起交易，返回 game_trade_id"""
    if not engine.client or not getattr(engine.client, '_ready', False):
        try:
            await engine.client.ensure_ecdsa_ready()
        except Exception:
            return None

    body = {
        "offeredItemId": offer_item_id,
        "offeredQuantity": offer_qty,
        "requestedItemId": want_item_id,
        "requestedQuantity": want_qty,
        "note": unique_code,
    }

    try:
        result = await engine.client.create_museum_trade(target_user_id, body)
        if result.get("success"):
            data = result.get("data", {})
            return data.get("id")

        msg = result.get("message", "")
        logger.warning(f"[{engine.account_id}] 创建交易失败: {msg}")

        # 如果游戏提示今日已用完，标记该账号今日已交易
        if "今日" in msg and ("完成" in msg or "交易" in msg or "次数" in msg):
            from datetime import date
            await _set_traded(engine.account_id, date.today())
            logger.info(f"[{engine.account_id}] 游戏提示今日已交易，已同步到 daily_record")

        return None
    except Exception as e:
        logger.error(f"[{engine.account_id}] 创建交易异常: {e}")
        return None


def _has_accepted_trade_today(trades: list[dict], today: date) -> bool:
    """检查交易列表中是否有今天已接受的交易"""
    from datetime import datetime
    for t in trades:
        if t.get("status") == "accepted":
            accepted_at = t.get("acceptedAt", "")
            if accepted_at:
                try:
                    ad = datetime.strptime(accepted_at[:10], "%Y-%m-%d").date()
                    if ad == today:
                        return True
                except (ValueError, TypeError):
                    pass
    return False


async def _save_trade(
    initiator_id: str, target_id: str,
    offer_item_id: str, offer_qty: int,
    want_item_id: str, want_qty: int,
    unique_code: str, game_trade_id: int,
) -> int | None:
    """交易入库"""
    async with AsyncSessionLocal() as db:
        try:
            trade = MuseumTrade(
                initiator_id=initiator_id,
                target_id=target_id,
                offer_item_id=offer_item_id,
                offer_quantity=offer_qty,
                want_item_id=want_item_id,
                want_quantity=want_qty,
                unique_code=unique_code,
                status="pending",
                message=unique_code,
                game_trade_id=game_trade_id,
            )
            db.add(trade)
            await db.commit()
            await db.refresh(trade)
            return trade.id
        except Exception:
            await db.rollback()
            raise


# ——— 同步已有订单 ———


async def sync_museum_trades(account_id: str, engine) -> int:
    """启动时调用，从游戏API拉取该账号已有的交易订单并写入 museum_trade 表。
    返回新增/更新的记录数。使用独立临时客户端，不影响引擎运行的客户端。
    """
    # 用引擎客户端的 token 创建独立临时客户端
    token = engine.client.token if engine.client else ""
    if not token:
        return 0

    from app.services.qpet_client import QPetClient
    temp_client = QPetClient(account_id=account_id, token=token)
    try:
        ok = await temp_client.init_ecdsa()
        if not ok:
            logger.warning(f"[{account_id}] 临时客户端 ECDSA 初始化失败")
            return 0
    except Exception as e:
        logger.error(f"[{account_id}] 临时客户端 ECDSA 异常: {e}")
        return 0

    try:
        result = await temp_client.get_museum_trade_wishes()
    except Exception as e:
        logger.error(f"[{account_id}] 获取交易订单失败: {e}")
        return 0

    if not result.get("success"):
        logger.warning(f"[{account_id}] get_museum_trade_wishes 返回失败: {result.get('message')}")
        return 0

    data = result.get("data", {})
    incoming = data.get("incoming", [])
    outgoing = data.get("outgoing", [])
    completed_today = data.get("completedToday", 0) or 0
    logger.info(f"[{account_id}] get_museum_trade_wishes: incoming={len(incoming)} outgoing={len(outgoing)} completedToday={completed_today}")

    # 判断今日是否已交易
    from datetime import date, datetime
    today = date.today()
    has_traded_today = completed_today > 0 or _has_accepted_trade_today(incoming + outgoing, today)

    # 如果还看不出来，再查 GET /farm/museum-trades 的 match.reason
    if not has_traded_today:
        try:
            trades_resp = await temp_client.get_museum_trades()
            if trades_resp.get("success"):
                for friend_trade in trades_resp.get("data", {}).get("friends", []):
                    reason = (friend_trade.get("match") or {}).get("reason", "")
                    if "今日" in reason and ("完成" in reason or "交易" in reason):
                        has_traded_today = True
                        break
        except Exception:
            pass

    if has_traded_today:
        await _set_traded(account_id, today)
        logger.info(f"[{account_id}] 今日已交易，已同步到 daily_record")

    trades_raw = []
    for t in incoming:
        t["_direction"] = "incoming"
        trades_raw.append(t)
    for t in outgoing:
        t["_direction"] = "outgoing"
        trades_raw.append(t)

    if not trades_raw:
        return 0

    count = 0
    async with AsyncSessionLocal() as db:
        try:
            for t in trades_raw:
                game_id = t.get("id")
                if not game_id:
                    continue

                # 查是否已存在
                existing = await db.execute(
                    select(MuseumTrade).where(MuseumTrade.game_trade_id == game_id)
                )
                if existing.scalar_one_or_none():
                    continue

                # 映射 user_id → account_id
                sender_uid = t.get("senderId", 0)
                receiver_uid = t.get("receiverId", 0)
                sender_aid = await _resolve_account_id(db, sender_uid)
                receiver_aid = await _resolve_account_id(db, receiver_uid)

                # 如果收发双方都不是我们的托管账号，跳过
                if not sender_aid and not receiver_aid:
                    continue

                # 至少有一方是我们托管账号
                init_id = sender_aid or f"uid_{sender_uid}"
                target_id = receiver_aid or f"uid_{receiver_uid}"

                game_status = t.get("status", "pending")
                status_map = {"pending": "pending", "accepted": "accepted", "rejected": "rejected"}
                local_status = status_map.get(game_status, "pending")

                trade = MuseumTrade(
                    initiator_id=init_id,
                    target_id=target_id,
                    offer_item_id=t.get("offeredItem", {}).get("id", ""),
                    offer_quantity=t.get("offeredQuantity", 0),
                    want_item_id=t.get("requestedItem", {}).get("id", ""),
                    want_quantity=t.get("requestedQuantity", 0),
                    unique_code=t.get("note", ""),
                    status=local_status,
                    message=t.get("note", ""),
                    game_trade_id=game_id,
                )
                db.add(trade)
                count += 1

            if count:
                await db.commit()
                logger.info(f"[{account_id}] 同步博物馆交易订单: {count} 条")
        except Exception:
            await db.rollback()
            raise

    return count


async def _resolve_account_id(db, game_user_id: int) -> str | None:
    """通过游戏 user_id 反查托管 account_id"""
    from app.models.account import Account
    r = await db.execute(
        select(Account.id).where(Account.user_id == game_user_id)
    )
    return r.scalar_one_or_none()


# ——— 调度器注册 ———

_scheduler_task = None


async def start_museum_trade_scheduler():
    global _scheduler_task
    if _scheduler_task is not None:
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("博物馆交易调度器已启动")


async def stop_museum_trade_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("博物馆交易调度器已停止")


async def _scheduler_loop():
    while True:
        try:
            await run_museum_trade_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"博物馆交易调度器异常: {e}")
        await asyncio.sleep(INTERVAL_SECONDS)
