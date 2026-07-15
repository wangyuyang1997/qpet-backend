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
from app.services.class_upgrade import ClassUpgrade
from app.services.friend_sync import FriendSync
from app.services.gang import Gang
from app.services.equip import Equip
from app.services.upgrade import Upgrade
from app.services.world_boss import WorldBoss
from app.services.battle.npc import NpcBattle
from app.services.battle.friend import FriendBattle
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
        self.friend_battle = None
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

    def _init_services(self):
        """创建所有 service 实例（client 就绪后调用）"""
        c = self.client = self.mgr.client
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
        self.friend_battle = FriendBattle(c, aid)
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

        await self._init_sync()

        self._tasks.append(asyncio.create_task(self._fight_loop()))
        self._tasks.append(asyncio.create_task(self._farm_loop()))
        self._tasks.append(asyncio.create_task(self._flower_loop()))
        self._tasks.append(asyncio.create_task(self._ad_poll_loop()))
        self._tasks.append(asyncio.create_task(self._main_cycle_loop()))

        logger.info(f"[{self.account_id}] 引擎已启动")
        return True

    async def stop(self):
        self._running = False
        _engines.pop(self.account_id, None)

        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

        await self.mgr.stop()
        try:
            await self.db.close()
        except Exception:
            pass
        logger.info(f"[{self.account_id}] 引擎已停止")

    # ——— 初始化 ———

    async def _init_sync(self):
        try:
            char = await self.client.get_character()
            if char.get("success"):
                self._character_cache = char.get("data", {})
                self._marriage_partner_id = self._character_cache.get("marriagePartnerId")

            await self._run_marriage()

            async def retry():
                await asyncio.sleep(5)
                await self._run_marriage()
            asyncio.create_task(retry())

        except Exception as e:
            logger.error(f"[{self.account_id}] 初始化同步失败: {e}")

    async def _refresh_character(self):
        char = await self.client.get_character()
        if char.get("success"):
            self._character_cache = char.get("data", {})

    # ——— 主循环 ———

    async def _main_cycle_loop(self):
        while self._running:
            try:
                await self.full_auto_cycle()
            except Exception as e:
                logger.error(f"[{self.account_id}] 主循环异常: {e}")
            await asyncio.sleep(1800 + random.randint(0, 60))

    async def full_auto_cycle(self):
        start_time = time.time()

        await self._refresh_character()
        level = self._character_cache.get("level", 0)
        stamina = self._character_cache.get("stamina", 0)
        exp = self._character_cache.get("experience", 0)
        is_premium = self._character_cache.get("isPremium", False)

        await self.exp_boost.ensure()
        await self.supply.ensure("revive", 0)
        await self.supply.ensure("challenge_book", 0)

        await self.checkin.run()
        await self.chest.run()

        await self.ad_stamina.run(stamina)
        await self.ad_farm.run()
        await self.ad_community.run()
        await self.shop_special.run()
        await self.shop_stamina.run(exp)

        await self.npc.fight_one()
        target = await self.friend_battle.pick_target(level)
        if target:
            await self.friend_battle.fight_one(target)

        await self.tower.run()
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
        logger.info(f"[{self.account_id}] 主循环完成 ({elapsed:.1f}s)")
        await self._persist_daily()

    async def _persist_daily(self):
        """将当前角色快照 + 关键计数写入 daily_records"""
        from datetime import date
        from sqlalchemy.dialects.postgresql import insert
        from app.models.daily_record import DailyRecord

        char = self._character_cache
        if not char:
            return

        today = date.today()
        # Gather available status data
        tower_status = {}
        gang_boss_status = {}
        farm_status = {}
        try:
            tower_status = await self.tower.get_status() or {}
            gang_boss_status = await self.gang.get_boss_status() or {}
            farm_status = await self.farm_status.get() or {}
        except Exception:
            pass

        vals = {
            "account_id": self.account_id,
            "date": today,
            "level": char.get("level", 0),
            "class_name": char.get("className", ""),
            "combat_power": char.get("combatPower", 0),
            "current_exp": char.get("experience", 0),
            "level_exp": char.get("exp", 0),
            "level_exp_max": char.get("expToNext", 0),
            "stamina": char.get("stamina", 0),
            "max_stamina": char.get("max_stamina") or char.get("maxStamina", 0),
            # Incremental counters — these accumulate per service call
            "npc_fights": getattr(self.npc, "today_count", 0) if self.npc else 0,
            "friend_fights": getattr(self.friend_battle, "today_count", 0) if self.friend_battle else 0,
            "tower_floors": tower_status.get("todayFloors", 0),
            "tower_max": tower_status.get("maxFloor", 0),
            "gang_contribution": gang_boss_status.get("todayContribution", 0),
            "harvests": farm_status.get("todayHarvests", 0),
            "steals": farm_status.get("todaySteals", 0),
            "digs": farm_status.get("todayDigs", 0),
            "stamina_ads": getattr(self.ad_stamina, "today_count", 0) if self.ad_stamina else 0,
            "community_ads": getattr(self.ad_community, "today_count", 0) if self.ad_community else 0,
        }

        stmt = insert(DailyRecord).values(**vals).on_conflict_do_update(
            index_elements=["account_id", "date"],
            set_=vals,
        )
        try:
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as e:
            logger.error(f"[{self.account_id}] daily_record 写入失败: {e}")

    # ——— 子循环 ———

    async def _fight_loop(self):
        while self._running:
            try:
                result = await self.npc.fight_one()
                await asyncio.sleep(3 if result.get("ok") else 10)
            except Exception:
                await asyncio.sleep(10)

    async def _farm_loop(self):
        while self._running:
            try:
                await self._run_farm()
            except Exception:
                pass
            await asyncio.sleep(60)

    async def _flower_loop(self):
        while self._running:
            try:
                status = await self.marriage_status.get()
                if not status.get("married") and self._marriage_partner_id:
                    intimacy = status.get("intimacy", 0)
                    if intimacy < 100:
                        await self.supply.ensure("flowers", 0)
                        await self.marriage_flowers.run(self._marriage_partner_id, intimacy)
            except Exception:
                pass
            await asyncio.sleep(15)

    async def _ad_poll_loop(self):
        while self._running:
            try:
                await self.ad_stamina.run()
                await self.ad_community.run()
            except Exception:
                pass
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
                await self.supply.ensure("flowers", 0)
                result = await self.marriage_flowers.run(self._marriage_partner_id, intimacy)
                intimacy = result.get("intimacy", intimacy)
                if intimacy >= 100:
                    await self.marriage_proposal.run(status)
        except Exception as e:
            logger.error(f"[{self.account_id}] 婚姻流程异常: {e}")

    async def _run_farm(self, is_premium: bool = False):
        try:
            status = await self.farm_status.get()
            if not status:
                return

            slots = status.get("slots", [])
            crops = status.get("cropConfig", [])
            collection = status.get("collection", [])
            tasks = status.get("dailyTasks", [])
            exp_val = status.get("experience", 0)
            vip_slot = status.get("vipSlotIndex", -1)

            await self.farm_harvest.remove_withered(slots)

            # 翻地：成熟作物先翻地再收获，好友农场先翻地再偷菜
            await self.farm_dig.run(slots, is_premium)

            await self.farm_harvest.run(slots, is_premium)
            await self.farm_plant.run(slots, crops, collection, exp_val, is_premium, vip_slot, tasks)

            self._farm_cycle_index += 1
            if self._farm_cycle_index % 2 == 0:
                await self.farm_care.water_own(slots)
            elif self.peers:
                peer = self.peers[0]
                await self.farm_dig.dig_friend(peer["id"])
                await self.farm_steal.run(peer["id"])
                await self.farm_care.water_friend(peer["id"])

            # 土地升级：检查 canUpgrade，每次只升一块
            await self.farm_land.run(slots)

            await self.farm_visit.run()
        except Exception as e:
            logger.error(f"[{self.account_id}] 农场异常: {e}")
