"""游戏引擎 — 每账号实例，编排所有 service 的执行顺序"""
import asyncio
import logging
import random
import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.account_manager import AccountManager
from app.services.config_service import ConfigService
from app.services.inventory import Inventory
from app.services.item_supply import ItemSupply
from app.services.exp_boost import ExpBoost
from app.services.checkin import Checkin
from app.services.chest import Chest
from app.services.tower import Tower
from app.services.tournament import Tournament
from app.core.logger import info, warn, action, error as log_error
from app.services.class_upgrade import ClassUpgrade
from app.services.friend_sync import FriendSync
from app.services.gang import Gang
from app.services.equip import Equip
from app.services.upgrade import Upgrade
from app.services.world_boss import WorldBoss
from app.services.battle.npc import NpcBattle
from app.services.battle.gang_boss import GangBoss
from app.services.ad.stamina import AdStamina
from app.services.ad.farm import AdFarm
from app.services.ad.community import AdCommunity
from app.services.shop.special import ShopSpecial
from app.services.shop.stamina import ShopStamina
from app.services.marriage.status import MarriageStatus
from app.services.marriage.gift import MarriageGift
from app.services.marriage.flowers import MarriageFlowers
from app.services.marriage.boss import MarriageBoss
from app.services.marriage.proposal import MarriageProposal
from app.services.farm.status import FarmStatus
from app.services.farm.harvest import FarmHarvest
from app.services.farm.plant import FarmPlant
from app.services.farm.care import FarmCare
from app.services.farm.steal import FarmSteal
from app.services.farm.visit import FarmVisit
from app.services.farm.dig import FarmDig
from app.services.farm.land import FarmLand

logger = logging.getLogger(__name__)

_engines: dict[str, "GameEngine"] = {}


def get_engine(account_id: str):
    return _engines.get(account_id)


async def get_or_create_engine(account_id: str) -> "GameEngine | None":
    """获取已有引擎，不存在则从数据库加载创建"""
    if account_id in _engines:
        return _engines[account_id]
    from app.core.database import AsyncSessionLocal
    # Create a long-lived session for the engine
    db = AsyncSessionLocal()
    try:
        mgr = AccountManager(account_id, db)
        try:
            await mgr.load_from_db()
        except ValueError:
            await db.close()
            return None
        engine = GameEngine(mgr, db)
        return engine
    except Exception:
        await db.close()
        raise


class GameEngine:
    """单个游戏账号的自动化引擎"""

    def __init__(self, account_manager: AccountManager, db: AsyncSession):
        self.mgr = account_manager
        self.account_id = account_manager.id
        self.db = db
        self.peers: list[dict] = []
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._initialized = False

        # 这些在 _init_services() 中创建（需要 client 就绪）
        self.client = None
        self.config = None
        self.inventory = None
        self.supply = None
        self.exp_boost = None
        self.checkin = None
        self.chest = None
        self.tower = None
        self.tournament = None
        self.class_upgrade = None
        self.friend_sync = None
        self.gang = None
        self.equip = None
        self.upgrade = None
        self.world_boss = None
        self.npc = None
        self.gang_boss = None
        self.ad_stamina = None
        self.ad_farm = None
        self.ad_community = None
        self.shop_special = None
        self.shop_stamina = None
        self.marriage_status = None
        self.marriage_gift = None
        self.marriage_flowers = None
        self.marriage_boss = None
        self.marriage_proposal = None
        self.farm_status = None
        self.farm_harvest = None
        self.farm_plant = None
        self.farm_care = None
        self.farm_steal = None
        self.farm_visit = None
        self.farm_dig = None
        self.farm_land = None

        self._character_cache: dict = {}
        self._marriage_partner_id: str | None = None
        self._farm_cycle_index = 0
        # 风控检测 对齐旧引擎 checkRateLimited / setFarmRateLimit
        self._rate_limit_hits = 0
        self._rate_limit_until = 0.0

    def _init_services(self):
        """创建所有 service 实例（client 就绪后调用）"""
        c = self.client = self.mgr.client
        c.on_rate_limited = lambda api: self._check_rate_limited({"rateLimited": True, "api": api})
        aid = self.account_id
        cfg = self.config = ConfigService(self.db)
        inv = self.inventory = Inventory(c)
        sup = self.supply = ItemSupply(c, inv, cfg, aid)

        self.exp_boost = ExpBoost(c, inv, cfg, aid)
        self.checkin = Checkin(c, aid)
        self.chest = Chest(c, aid)
        self.tower = Tower(c, cfg, sup, aid)
        self.tournament = Tournament(c, aid)
        self.class_upgrade = ClassUpgrade(c, aid)
        self.friend_sync = FriendSync(c, aid, self.peers)
        self.gang = Gang(c, aid)
        self.equip = Equip(c, aid)
        self.upgrade = Upgrade(c, sup, aid)
        self.world_boss = WorldBoss(c, aid)
        self.npc = NpcBattle(c, aid)
        self.gang_boss = GangBoss(c, cfg, sup, aid)
        self.ad_stamina = AdStamina(c, aid)
        self.ad_farm = AdFarm(c, aid)
        self.ad_community = AdCommunity(c, aid)
        self.shop_special = ShopSpecial(c, aid)
        self.shop_stamina = ShopStamina(c, aid)
        self.marriage_status = MarriageStatus(c)
        self.marriage_gift = MarriageGift(c, sup, aid)
        self.marriage_flowers = MarriageFlowers(c, sup, aid)
        self.marriage_boss = MarriageBoss(c, aid)
        self.marriage_proposal = MarriageProposal(c, aid)
        self.farm_status = FarmStatus(c)
        self.farm_harvest = FarmHarvest(c, aid)
        self.farm_plant = FarmPlant(c, aid)
        self.farm_care = FarmCare(c, aid)
        self.farm_steal = FarmSteal(c, aid)
        self.farm_visit = FarmVisit(c)
        self.farm_dig = FarmDig(c, aid)
        self.farm_land = FarmLand(c, aid)
        self._initialized = True

    async def cached_get(self, key: str, fetcher):
        """缓存30秒，避免穿透游戏API重复请求"""
        now = __import__("time").time()
        if not hasattr(self, '_cache'):
            self._cache = {}
        if key in self._cache:
            ts, val = self._cache[key]
            if now - ts < 30:
                return val
        result = await fetcher()
        self._cache[key] = (now, result)
        return result

    # ——— 启停 ———

    async def start(self) -> bool:
        if self._running:
            return False

        ok = await self.mgr.start()
        if not ok:
            return False

        self.peers = await self.mgr.get_peers()
        self._init_services()
        self._running = True
        _engines[self.account_id] = self
        await self.mgr._save_running(1)

        await self._init_sync()

        self._tasks.append(asyncio.create_task(self._fight_loop()))
        self._tasks.append(asyncio.create_task(self._farm_loop()))
        self._tasks.append(asyncio.create_task(self._flower_loop()))
        self._tasks.append(asyncio.create_task(self._ad_poll_loop()))
        self._tasks.append(asyncio.create_task(self._main_cycle_loop()))

        action("系统", "引擎", "自动挂机已启动", self.account_id)
        return True

    async def stop(self):
        self._running = False
        _engines.pop(self.account_id, None)

        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

        await self.mgr._save_running(0)
        await self.mgr.stop()
        try:
            await self.db.close()
        except Exception:
            pass
        action("系统", "引擎", "自动挂机已停止", self.account_id)

    # ——— 初始化 ———

    async def _init_sync(self):
        try:
            char = await self.client.get_character()
            if char.get("success"):
                self._character_cache = char.get("data", {})
                self._marriage_partner_id = self._character_cache.get("marriagePartnerId")
                self.mgr.nickname = self._character_cache.get("nickname", self.mgr.nickname)
                self.mgr.level = self._character_cache.get("level", self.mgr.level)
                self.mgr.class_name = self._character_cache.get("className", self.mgr.class_name)
                await self.mgr._save_info()
                info("系统", "引擎", f"角色 {self.mgr.nickname} Lv.{self.mgr.level} 已同步", self.account_id)
            else:
                warn("系统", "引擎", "初始化获取角色信息失败", self.account_id)

            # 从 daily_records 恢复今日已完成状态，重启不丢
            await self._restore_daily_state()

            await self._run_marriage()

            async def retry():
                await asyncio.sleep(5)
                await self._run_marriage()

            asyncio.create_task(retry())

            # 启动后延迟30s执行首轮，避免启动风暴触发风控
            await asyncio.sleep(30)
            await self.full_auto_cycle()

        except Exception as e:
            log_error("系统", "引擎", f"初始化同步失败: {e}", self.account_id)

    async def _refresh_character(self):
        char = await self.client.get_character()
        if char.get("success"):
            self._character_cache = char.get("data", {})
            self.mgr.nickname = self._character_cache.get("nickname", self.mgr.nickname)
            self.mgr.level = self._character_cache.get("level", self.mgr.level)
            self.mgr.class_name = self._character_cache.get("className", self.mgr.class_name)
            await self.mgr._save_info()
        else:
            warn("系统", "引擎", "角色刷新API返回失败", self.account_id)

    async def _sync_inventory_to_db(self):
        """同步背包数据入库（先删后插）"""
        try:
            inv = await self.client.get_inventory()
            if not inv.get("success"):
                warn("系统", "引擎", "背包同步API失败", self.account_id)
                return
            items = inv.get("data", {}).get("items", [])
            if not items:
                info("系统", "引擎", "背包为空，跳过同步", self.account_id)
                return
            from app.services.farm.sync import FarmSync
            from app.core.database import AsyncSessionLocal
            sync = FarmSync(AsyncSessionLocal)
            await sync._sync_inventory(self.account_id, items)
            info("系统", "引擎", f"背包同步完成 ({len(items)}件)", self.account_id)
        except Exception as e:
            log_error("系统", "引擎", f"背包同步异常: {e}", self.account_id)

    # ——— 主循环 ———

    async def _main_cycle_loop(self):
        while self._running:
            try:
                await self.full_auto_cycle()
            except Exception as e:
                log_error("系统", "引擎", f"主循环异常: {e}", self.account_id)
            await asyncio.sleep(1800 + random.randint(0, 60))

    async def full_auto_cycle(self):
        start_time = time.time()
        info("系统", "引擎", "开始完整自动循环", self.account_id)

        await self._refresh_character()
        await self._sync_inventory_to_db()
        level = self._character_cache.get("level", 0)
        stamina = self._character_cache.get("stamina", 0)
        exp = self._character_cache.get("experience", 0)
        is_premium = self._character_cache.get("isPremium", False)

        await self.exp_boost.ensure()  # 经验药水，用完才补
        await self.supply.ensure("revive", 0)
        await self.supply.ensure("challenge_book", 0)

        await self.checkin.run()
        await self.chest.run()

        await self.ad_stamina.run(stamina)
        await self.ad_farm.run()
        await self.ad_community.run()
        await self.shop_special.run()
        await self.shop_stamina.run(exp)

        if level < 100:
            await self.npc.fight_one()
            await self.tower.run()
        else:
            action("系统", "引擎", f"角色Lv.{level}，跳过NPC/爬塔", self.account_id)
        await self.gang_boss.run()
        await self.world_boss.run()

        await self._run_marriage()

        await self.friend_sync.run()
        await self.gang.run()
        await self.class_upgrade.run(level)
        await self.upgrade.run(is_premium)
        await self.equip.run()

        await self.tournament.run(level)
        await self._run_farm(is_premium)

        elapsed = time.time() - start_time
        action("系统", "引擎", f"执行完整自动循环... ({elapsed:.1f}s)", self.account_id)
        await self._persist_daily()
        await self._warm_api_caches()

    async def _warm_api_caches(self):
        """将引擎循环中已获取的数据写入 Redis，让前端 API 永远命中缓存。
        覆盖 character / equipment / inventory / skill-tree / gang / farm 共 6 个接口。
        每 30 分钟调用一次，额外开销可忽略。
        """
        try:
            from app.core.redis import cache_set
            import json

            async def cache(key: str, fetcher, ttl: int = 600):
                try:
                    result = await fetcher()
                    if result.get("success"):
                        data = result.get("data", result)
                        await cache_set(f"qpet:{self.account_id}:{key}", json.dumps(data), ttl)
                except Exception:
                    pass

            # 按前端页面分组，每个接口一个 key

            # character → /accounts/{id}/character
            await cache("character", lambda: self.client.get_character())

            # equipment → /accounts/{id}/equipment
            await cache("equipment", lambda: self.client.get_equipment())

            # inventory → /accounts/{id}/inventory
            await cache("inventory", lambda: self.client.get_inventory())

            # skill-tree → /accounts/{id}/skill-tree
            await cache("skill-tree", lambda: self.client.get_skill_tree())

            # gang → /accounts/{id}/gang
            await cache("gang", lambda: self.client.get_gang_status())

            # farm → /accounts/{id}/farm
            await cache("farm", lambda: self._fetch_farm_data())

        except Exception:
            pass

    async def _fetch_farm_data(self):
        """获取农场数据并合并 DB 计数"""
        from datetime import date
        from sqlalchemy import select
        from app.models.daily_record import DailyRecord
        from app.core.database import AsyncSessionLocal

        db = AsyncSessionLocal()
        try:
            r = await db.execute(
                select(DailyRecord).where(
                    DailyRecord.account_id == self.account_id,
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
        finally:
            await db.close()

        status = await self.farm_status.get()
        if status:
            status.update(db_counts)
        return {"success": True, "data": status or db_counts}

    async def _persist_steals(self):
        """只更新偷菜计数，不覆盖其他字段"""
        from datetime import date
        from sqlalchemy.dialects.postgresql import insert
        from app.models.daily_record import DailyRecord
        count = await self._get_steal_count()
        vals = {"account_id": self.account_id, "date": date.today(), "steals": count}
        stmt = insert(DailyRecord).values(**vals).on_conflict_do_update(
            index_elements=["account_id", "date"], set_={"steals": count},
        )
        try:
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            log_error("系统", "引擎", f"偷菜计数入库失败: {e}", self.account_id)

    async def _get_gang_contrib(self) -> int:
        """从帮派BOSS API取今日贡献，对齐旧引擎"""
        try:
            gb = await self.client.get_gang_boss_status()
            if gb.get("success") and gb.get("data"):
                total = 0
                for boss in gb["data"].get("bossList", []):
                    total += boss.get("todayContribEarned", 0) or 0
                return total
        except Exception as e:
            warn("系统", "引擎", f"获取帮贡异常: {e}", self.account_id)
        return 0

    async def _get_steal_count(self) -> int:
        """从好友农场取真实偷菜计数，对齐旧引擎 engine.js:1929"""
        try:
            friends = await self.client.get_fightable_friends()
            if friends.get("success") and friends.get("data"):
                for f in friends["data"]:
                    fid = f.get("user_id") or f.get("userId")
                    if not fid:
                        continue
                    r = await self.client.farm_get_friend(fid)
                    if r.get("success") and r.get("data"):
                        return r["data"].get("visitorTodayStealCount") or r["data"].get("todayStealCount") or 0
        except Exception as e:
            warn("系统", "引擎", f"获取偷菜计数失败: {e}", self.account_id)
        return 0

    async def _restore_daily_state(self):
        """从 daily_records 恢复今天已完成的一次性操作状态"""
        try:
            from datetime import date
            from sqlalchemy import select
            from app.models.daily_record import DailyRecord
            today = date.today()
            r = await self.db.execute(
                select(DailyRecord).where(
                    DailyRecord.account_id == self.account_id,
                    DailyRecord.date == today,
                )
            )
            row = r.scalar_one_or_none()
            if row:
                if row.checkin_done and self.checkin:
                    self.checkin._done_date = today.isoformat()
                if row.chest_done and self.chest:
                    self.chest._done_date = today.isoformat()
                if row.exp_boost_checked and self.exp_boost:
                    self.exp_boost._failed_date = today.isoformat()
        except Exception:
            pass

    async def _persist_daily(self):
        """将当前角色快照 + 关键计数写入 daily_records"""
        from datetime import date
        from sqlalchemy.dialects.postgresql import insert
        from app.models.daily_record import DailyRecord

        char = self._character_cache
        if not char:
            warn("系统", "引擎", "角色缓存为空，跳过每日记录持久化", self.account_id)
            return

        today = date.today()
        # Gather available status data
        tower_status = {}
        gang_boss_status = {}
        farm_status = {}
        try:
            tower_status = await self.client.get_tower_status()
            tower_status = tower_status.get("data", {}) if tower_status.get("success") else {}
        except Exception as e:
            warn("系统", "引擎", f"获取爬塔状态失败: {e}", self.account_id)
        try:
            gang_boss_status = await self.client.get_gang_boss_status()
            gang_boss_status = gang_boss_status.get("data", {}) if gang_boss_status.get("success") else {}
        except Exception as e:
            warn("系统", "引擎", f"获取帮派BOSS状态失败: {e}", self.account_id)
        try:
            farm_status = await self.farm_status.get() or {}
        except Exception as e:
            warn("系统", "引擎", f"获取农场状态失败: {e}", self.account_id)

        # 计数器（始终写入，这些是今日累积值）
        counters = {
            "npc_fights": getattr(self.npc, "today_count", 0) if self.npc else 0,
            "tower_floors": tower_status.get("todayFloors", 0),
            "tower_max": tower_status.get("maxFloor", 0),
            "gang_contribution": await self._get_gang_contrib(),
            "plants": getattr(self.farm_plant, "_planted", 0) if self.farm_plant else 0,
            "harvests": farm_status.get("todayHarvests", 0),
            "steals": await self._get_steal_count(),
            "waters": farm_status.get("todayCareCount", 0),
            "help_waters": getattr(self.farm_care, "helped", 0) if self.farm_care else 0,
            "digs": (farm_status.get("explorationStatus", {}) or {}).get("todayCount", 0),
            "land_upgrades": getattr(self.farm_land, "today_count", 0) if self.farm_land else 0,
            "stamina_ads": getattr(self.ad_stamina, "today_count", 0) if self.ad_stamina else 0,
            "community_ads": getattr(self.ad_community, "today_count", 0) if self.ad_community else 0,
            "farm_ads": getattr(self.ad_farm, "today_count", 0) if self.ad_farm else 0,
            "challenge_books": getattr(self.shop_special, "today_count", 0) if self.shop_special else 0,
            "today_harvest_exp": farm_status.get("todayHarvestExp", 0),
            "exp_battle": getattr(self.npc, "today_exp", 0) if self.npc else 0,
            # 每日一次性操作完成标记
            "checkin_done": getattr(self.checkin, "_done_date", "") == today.isoformat() and 1 or 0,
            "chest_done": getattr(self.chest, "_done_date", "") == today.isoformat() and 1 or 0,
            "supply_checked": getattr(self.supply, "_failed", {}) and 1 or 0,
            "exp_boost_checked": getattr(self.exp_boost, "_failed_date", "") == today.isoformat() and 1 or 0,
        }

        # 角色快照（仅在 character_cache 有效时写入，防止脏覆盖）
        char_fields = {}
        if char.get("level", 0) > 0:
            char_fields.update({
                "level": char.get("level", 0),
                "class_name": char.get("className", ""),
                "combat_power": char.get("combatPower", 0),
                "current_exp": char.get("experience", 0),
                "level_exp": char.get("exp", 0),
                "level_exp_max": char.get("expToNext", 0),
                "stamina": char.get("stamina", 0),
                "max_stamina": char.get("max_stamina") or char.get("maxStamina", 0),
            })

        # insert 需要全量字段，update 只覆盖 char_fields + counters
        all_vals = {"account_id": self.account_id, "date": today, **char_fields, **counters}
        update_set = {**char_fields, **counters}

        stmt = insert(DailyRecord).values(**all_vals).on_conflict_do_update(
            index_elements=["account_id", "date"],
            set_=update_set,
        )
        try:
            await self.db.execute(stmt)
            await self.db.commit()
            level = char.get("level", 0)
            info("系统", "引擎", f"每日记录已持久化 (Lv.{level}, NPC{counters['npc_fights']}次, 塔{counters['tower_floors']}层)", self.account_id)
        except Exception as e:
            log_error("系统", "引擎", f"daily_record 写入失败: {e}", self.account_id)

    # ——— 风控检测 对齐旧引擎 checkRateLimited / setFarmRateLimit ———

    def _is_rate_limited(self) -> bool:
        if time.time() < self._rate_limit_until:
            return True
        self._rate_limit_hits = 0
        return False

    def _check_rate_limited(self, result: dict) -> bool:
        if result and result.get("rateLimited"):
            api = result.get("api", "?")
            self._rate_limit_hits += 1
            if self._rate_limit_hits >= 2:
                warn("系统", "引擎", f"连续触发风控[{api}]，自动停止挂机！", self.account_id)
                asyncio.create_task(self.stop())
                return True
            cooldown = min(30 * (2 ** (self._rate_limit_hits - 1)), 600)
            self._rate_limit_until = time.time() + cooldown
            warn("系统", "引擎", f"风控[{api}] 冷却 {cooldown}s (第{self._rate_limit_hits}次)", self.account_id)
            return True
        return False

    # ——— 子循环 ———

    async def _fight_loop(self):
        while self._running:
            try:
                if self._character_cache.get("level", 0) >= 100:
                    await asyncio.sleep(60)  # 满级不刷NPC
                    continue
                if not self._is_rate_limited():
                    result = await self.npc.fight_one()
                    if result.get("no_stamina"):
                        await asyncio.sleep(300)  # 体力不足，等5分钟
                    else:
                        await asyncio.sleep(3 if result.get("ok") else 10)
                else:
                    await asyncio.sleep(30)
            except Exception as e:
                log_error("系统", "引擎", f"战斗循环异常: {e}", self.account_id)
                await asyncio.sleep(10)

    async def _farm_loop(self):
        while self._running:
            try:
                if not self._is_rate_limited():
                    self._farm_cycle_index += 1
                    if self._farm_cycle_index % 2 == 0:
                        await self._run_farm_own()
                    else:
                        if random.random() < 0.8:
                            await self._run_farm_social()
            except Exception as e:
                log_error("系统", "引擎", f"农场循环异常: {e}", self.account_id)
            await asyncio.sleep(120)

    async def _flower_loop(self):
        while self._running:
            try:
                status = await self.marriage_status.get()
                if not status.get("married") and self._marriage_partner_id:
                    intimacy = status.get("intimacy", 0)
                    if intimacy < 100:
                        await self.supply.ensure("flowers", 0)
                        await self.marriage_flowers.run(self._marriage_partner_id, intimacy)
            except Exception as e:
                log_error("系统", "引擎", f"送花循环异常: {e}", self.account_id)
            await asyncio.sleep(300)

    async def _ad_poll_loop(self):
        while self._running:
            try:
                await self.ad_stamina.run()
                await self.ad_community.run()
            except Exception as e:
                log_error("系统", "引擎", f"广告轮询异常: {e}", self.account_id)
            await asyncio.sleep(600)

    # ——— 子模块编排 ———

    async def _run_marriage(self):
        try:
            status = await self.marriage_status.get()
            if status.get("married"):
                await self.marriage_boss.run(status)
                await self.marriage_gift.run(status)
            elif self._marriage_partner_id:
                intimacy = status.get("intimacy", 0)
                info("系统", "引擎", f"未婚, 当前亲密度:{intimacy}", self.account_id)
                await self.supply.ensure("flowers", 0)
                result = await self.marriage_flowers.run(self._marriage_partner_id, intimacy)
                intimacy = result.get("intimacy", intimacy)
                if intimacy >= 100:
                    info("系统", "引擎", "亲密度已满, 尝试求婚", self.account_id)
                    await self.marriage_proposal.run(status)
            else:
                pass  # 无伴侣，正常跳过
        except Exception as e:
            log_error("系统", "引擎", f"婚姻流程异常: {e}", self.account_id)

    async def _run_farm(self, is_premium: bool = False):
        """完整农场流程（主循环用）"""
        await self._run_farm_own()
        await self._run_farm_social()

    async def _run_farm_own(self):
        """自己农场：翻地+收获+播种+照料+广告+土地升级。对齐旧引擎 autoFarm()"""
        try:
            await self.farm_visit.run()

            status = await self.farm_status.get()
            if not status:
                warn("农场", "农场", "获取农场状态失败，跳过此轮", self.account_id)
                return

            is_premium = status.get("isPremium", False)
            slots = status.get("slots", [])
            crops = status.get("cropConfig", [])
            collection = status.get("collection", [])
            tasks = status.get("dailyTasksWithProgress", [])
            exp_val = status.get("experience", 0)
            farm_level = status.get("level", 1)
            vip_slot = status.get("vipSlotIndex", -1)
            unlocked = status.get("unlockedSlots", len(slots))

            info("农场", "农场", f"Lv.{farm_level}, {unlocked}/{len(slots)}格, premium={is_premium}", self.account_id)

            # 1. Dig mature crops FIRST
            await self.farm_dig.run(slots, is_premium)

            # 2. Harvest
            ready = [s for s in slots if s.get("canHarvest")]
            harvested_count = 0
            if ready:
                if len(ready) == unlocked and is_premium:
                    r = await self.client.farm_harvest_all()
                    if r.get("success"):
                        harvested_count = len(ready)
                        info("农场", "农场", f"一键收获 {len(ready)}块", self.account_id)
                    else:
                        warn("农场", "农场", "一键收获API失败，回退单块收", self.account_id)
                        for slot in ready:
                            r = await self.client.farm_harvest(slot["slotIndex"])
                            if r.get("success"):
                                harvested_count += 1
                            await asyncio.sleep(0.8)
                else:
                    for slot in ready:
                        r = await self.client.farm_harvest(slot["slotIndex"])
                        if r.get("success"):
                            harvested_count += 1
                        await asyncio.sleep(0.8)
                info("农场", "农场", f"收获完成: {harvested_count}/{len(ready)}块", self.account_id)

            # 3. Remove withered
            withered = [s for s in slots if s.get("state") == "withered"]
            for slot in withered:
                await self.client.farm_remove(slot["slotIndex"])
                await asyncio.sleep(0.6)
            if withered:
                info("农场", "农场", f"铲除 {len(withered)} 个枯萎作物", self.account_id)

            # 4. Water own farm (daily limit: 5)
            care_done = status.get("todayCareCount", 0)
            if care_done < 5:
                dry = [s for s in slots if s.get("canCare")][:5 - care_done]
                for slot in dry:
                    await self.client.farm_care(slot["slotIndex"])
                    await asyncio.sleep(0.5)
                if dry:
                    info("农场", "农场", f"浇水 {len(dry)}块 (今日{care_done + len(dry)}/5)", self.account_id)

            # 5. Smart plant
            empty = [s for s in slots if s.get("canPlant") or (s.get("state") in ("empty", None) and not s.get("cropId"))]
            if empty:
                info("农场", "农场", f"播种 {len(empty)}个空位", self.account_id)
                await self.farm_plant.run(slots, crops, collection, exp_val, is_premium, vip_slot, tasks, farm_level, self.db)

            # 6. Ad bonus
            ad = await self.client.farm_get_ad_status()
            if ad.get("success") and ad.get("data", {}).get("canClaim"):
                await self.client.farm_claim_ad()
                info("农场", "农场", "农场广告奖励已领取", self.account_id)

            # 7. Land upgrade
            await self.farm_land.run(status)

        except Exception as e:
            log_error("系统", "引擎", f"农场异常: {e}", self.account_id)

    async def _run_farm_social(self):
        """社交：翻地+偷菜+帮浇水。对齐旧引擎 autoSteal() + autoHelpFriends()
        旧代码遍历好友列表直到找到可偷/可浇的，而非固定第一个。
        """
        try:
            friends = await self.client.get_fightable_friends()
            if not friends.get("success"):
                warn("农场", "社交", "获取好友列表API失败", self.account_id)
                return
            if not friends.get("data"):
                return
            friend_list = friends["data"]

            stolen_total = 0
            dug_total = 0
            watered_count = 0

            for f in friend_list:
                fid = f.get("user_id") or f.get("userId")
                if not fid:
                    continue

                # 翻地
                dug = await self.farm_dig.dig_friend(fid)
                if dug:
                    dug_total += dug

                # 偷菜（最多2块，对齐旧代码）
                if stolen_total < 2:
                    stolen = await self.farm_steal.run(fid)
                    if stolen:
                        stolen_total += stolen
                        await self._persist_steals()

                # 帮浇水（最多3次，对齐旧代码）
                if watered_count < 3:
                    w = await self.farm_care.water_friend(fid)
                    if w:
                        watered_count += w

                if stolen_total >= 2 and watered_count >= 3:
                    break

            if stolen_total or dug_total or watered_count:
                info("农场", "社交",
                     f"社交完成: 翻地{dug_total}块 偷菜{stolen_total}次 浇水{watered_count}次 (共{len(friend_list)}位好友)",
                     self.account_id)

        except Exception as e:
            log_error("系统", "引擎", f"社交异常: {e}", self.account_id)
