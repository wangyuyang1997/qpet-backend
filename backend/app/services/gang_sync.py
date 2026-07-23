"""帮派数据同步 — 从游戏 API 拉取，写入 gang_status/skills/bosses/members 四表"""
import logging
from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import GangStatus, GangSkillConfig, GangBossConfig, GangSkill, GangBoss, GangMember

logger = logging.getLogger(__name__)


class GangSync:

    def __init__(self, db_session_factory):
        self._sf = db_session_factory

    async def sync_all(self, account_id: str, gang_data: dict, boss_data: dict = None) -> dict:
        result = {"gang": False, "skills": 0, "bosses": 0, "members": 0}
        gang_id = gang_data.get("gang", {}).get("id", 0)
        result["gang"] = await self._sync_status(account_id, gang_data)
        result["skills"] = await self._sync_skills(gang_id, gang_data)
        result["bosses"] = await self._sync_bosses(gang_id, boss_data)
        result["members"] = await self._sync_members(account_id, gang_id, gang_data)
        return result

    # ——— 帮派状态 ———

    async def _sync_status(self, account_id: str, data: dict) -> bool:
        info = data.get("gang", {})
        gang_id = info.get("id", 0)
        if not gang_id:
            return False

        nxt = data.get("nextGangLevel", {}) or {}
        row = dict(
            gang_id=gang_id,
            name=info.get("name", ""),
            level=info.get("level", 1),
            notice=info.get("notice", ""),
            accumulated_contribution=info.get("accumulated_contribution", 0),
            guardian_level=info.get("guardian_level", 0),
            member_count=len(data.get("members", [])),
            next_level=nxt.get("level", 0),
            next_need_contrib=nxt.get("needContrib", 0),
            next_member_limit=nxt.get("memberLimit", 0),
            level_progress=data.get("levelProgress", 0),
            avatar=info.get("avatar", ""),
            updated_at=datetime.now(timezone.utc),
        )

        async with self._sf() as db:
            try:
                stmt = pg_insert(GangStatus).values(**row).on_conflict_do_update(
                    constraint="gang_status_pkey",
                    set_={k: v for k, v in row.items() if k != "gang_id"},
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"[{account_id}] 帮派状态同步完成: {info.get('name', '?')} Lv.{info.get('level', '?')}")
        return True

    # ——— 技能静态 + 关联 ———

    async def _sync_skills(self, gang_id: int, data: dict) -> int:
        configs = data.get("gangSkillsConfig", {})
        levels = data.get("mySkills", {})
        if not configs:
            return 0

        async with self._sf() as db:
            try:
                count = 0
                for i, (name, cfg) in enumerate(configs.items()):
                    # 静态配置（首次写入，后续忽略）
                    stmt_cfg = pg_insert(GangSkillConfig).values(
                        name=name,
                        description=cfg.get("desc", ""),
                        max_level=cfg.get("maxLevel", 20),
                        cost_per_level=cfg.get("costPerLevel", 0),
                        min_gang_level=cfg.get("minGangLevel", 1),
                        hp_per_level=cfg.get("hpPerLevel", 0),
                        atk_per_level=cfg.get("atkPerLevel", 0),
                        sort_order=i,
                    ).on_conflict_do_nothing()
                    await db.execute(stmt_cfg)

                    # 关联技能等级
                    if gang_id:
                        lv = levels.get(name, 0)
                        stmt_skill = pg_insert(GangSkill).values(
                            gang_id=gang_id,
                            skill_name=name,
                            current_level=lv,
                            updated_at=datetime.now(timezone.utc),
                        ).on_conflict_do_update(
                            constraint="gang_skills_gang_id_skill_name_key",
                            set_=dict(current_level=lv, updated_at=datetime.now(timezone.utc)),
                        )
                        await db.execute(stmt_skill)
                    count += 1
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"帮派技能同步: {count}项")
        return count

    # ——— BOSS静态 + 关联 ———

    async def _sync_bosses(self, gang_id: int, boss_data: dict) -> int:
        if not boss_data or not boss_data.get("success") or not gang_id:
            return 0

        data = boss_data.get("data", {})
        bosses = data.get("bossList", [])
        if not bosses:
            return 0

        async with self._sf() as db:
            try:
                count = 0
                for i, b in enumerate(bosses):
                    stmt_cfg = pg_insert(GangBossConfig).values(
                        boss_id=b.get("id"),
                        name=b.get("name", ""),
                        boss_level=b.get("level", 0),
                        min_gang_level=b.get("gangLevel", 1),
                        sort_order=i,
                    ).on_conflict_do_nothing()
                    await db.execute(stmt_cfg)

                    stmt_boss = pg_insert(GangBoss).values(
                        gang_id=gang_id,
                        boss_id=b.get("id"),
                        unlocked=b.get("unlocked", False),
                        free_challenge_done=b.get("freeChallengeDone", False),
                        updated_at=datetime.now(timezone.utc),
                    ).on_conflict_do_update(
                        constraint="gang_bosses_gang_id_boss_id_key",
                        set_=dict(
                            unlocked=b.get("unlocked", False),
                            free_challenge_done=b.get("freeChallengeDone", False),
                            updated_at=datetime.now(timezone.utc),
                        ),
                    )
                    await db.execute(stmt_boss)
                    count += 1
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"帮派BOSS同步: {count}个")
        return count

    # ——— 成员 ———

    async def _sync_members(self, account_id: str, gang_id: int, data: dict) -> int:
        members = data.get("members", [])
        if not members or not gang_id:
            return 0

        # 从 peers + 当前角色匹配 account_id
        from app.services.engine import _engines
        engine = _engines.get(account_id)
        peer_map = {}
        if engine and engine.peers:
            for p in engine.peers:
                uid = str(p.get("user_id") or p.get("id") or "")
                if uid:
                    peer_map[uid] = p.get("id", "")
        # 当前角色自己
        my_uid = str(engine._character_cache.get("user_id", "")) if engine else ""
        if my_uid:
            peer_map[my_uid] = account_id

        async with self._sf() as db:
            try:
                count = 0
                for m in members:
                    uid = m.get("user_id", 0)
                    acct_id = peer_map.get(str(uid), None)
                    joined_str = m.get("joined_at", "")
                    joined = parse_dt(joined_str) if joined_str else None
                    stmt = pg_insert(GangMember).values(
                        gang_id=gang_id,
                        account_id=acct_id,
                        user_id=uid,
                        nickname=m.get("nickname", ""),
                        role=m.get("role", "member"),
                        contribution=m.get("contribution", 0),
                        joined_at=joined,
                        updated_at=datetime.now(timezone.utc),
                    ).on_conflict_do_update(
                        constraint="gang_members_gang_id_user_id_key",
                        set_=dict(
                            nickname=m.get("nickname", ""),
                            role=m.get("role", "member"),
                            contribution=m.get("contribution", 0),
                            account_id=acct_id,
                            updated_at=datetime.now(timezone.utc),
                        ),
                    )
                    await db.execute(stmt)
                    count += 1
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(f"帮派成员同步: {count}人")
        return count
