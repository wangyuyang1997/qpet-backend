"""账号管理器 — 多账号生命周期、启停、重登、ECDSA 管理"""
import asyncio
import hashlib
import logging
from typing import Callable, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.account import Account
from app.core.crypto import encrypt_password, decrypt_password
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)

# 重登互斥锁（防止并发重登）
_relogin_locks: dict[str, bool] = {}
# 全局管理器注册表
_managers: dict[str, "AccountManager"] = {}


def get_manager(account_id: str) -> "AccountManager | None":
    return _managers.get(account_id)


def generate_account_id(token: str) -> str:
    """token SHA256 前12位 hex 作为账号ID"""
    return hashlib.sha256(token.encode()).hexdigest()[:12]


class AccountManager:
    """管理单个游戏账号的完整生命周期"""

    def __init__(self, account_id: str, db: AsyncSession):
        self.id = account_id
        self.db = db
        self.running = False
        self.config: dict = {}
        self.client: Optional[QPetClient] = None

        # 缓存
        self.nickname = ""
        self.level = 0
        self.class_name = ""
        self.is_premium = False
        self.premium_expires_at = None
        self.username = ""
        self.password_encrypted = ""

    # ——— 初始化 / 启停 ———

    async def load_from_db(self):
        """从数据库加载账号信息"""
        result = await self.db.execute(select(Account).where(Account.id == self.id))
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError(f"账号 {self.id} 不存在")

        self.nickname = row.nickname
        self.level = row.level
        self.class_name = row.class_name
        self.running = bool(row.running)
        self.config = row.automation or {}
        self.username = row.username or ""
        self.password_encrypted = row.password or ""
        self.is_premium = bool(row.is_premium)
        self.premium_expires_at = row.premium_expires_at

        # 创建 API 客户端
        self.client = QPetClient(
            account_id=self.id,
            token=row.token,
            on_auth_failure=self._handle_auth_failure,
        )

    async def start(self) -> bool:
        await self.load_from_db()
        if not self.username or not self.password_encrypted:
            logger.error(f"[{self.id}] 无账密，无法启动")
            return False

        # 强制重登 + 全新ECDSA
        if not await self.relogin():
            logger.error(f"[{self.id}] 重登失败")
            return False
        self.client.delete_key()
        await asyncio.sleep(1)
        if not await self.client.init_ecdsa():
            logger.error(f"[{self.id}] ECDSA初始化失败")
            return False

        # 测试连接
        result = await self.client.get_character()
        if not result.get("success"):
            logger.error(f"[{self.id}] 无法连接: {result.get('message')}")
            return False

        data = result.get("data", {})
        if data:
            self.nickname = data.get("nickname", "")
            self.level = data.get("level", 0)
            self.class_name = data.get("className", "")

        self.running = True
        _managers[self.id] = self
        return True

    async def stop(self):
        """停止账号引擎（不修改 running 状态，由 engine.stop() 统一管理）"""
        self.running = False
        _managers.pop(self.id, None)

    # ——— 重登 ———

    async def relogin(self) -> bool:
        """使用存储的账密重新登录游戏"""
        if not self.username or not self.password_encrypted:
            return False

        password = decrypt_password(self.password_encrypted)
        if not password:
            return False

        import httpx
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                f"https://api.duanwuqiufenmao.top/api/auth/login",
                json={"username": self.username, "password": password},
            )
            data = resp.json() if resp.status_code == 200 else {}

        if data.get("success"):
            new_token = data.get("data", {}).get("token", "")
            if new_token:
                # 更新 token
                self.client.token = new_token
                self.client.delete_key()
                self.client._ready = False
                # 持久化
                try:
                    acc = await self.db.get(Account, self.id)
                    if acc:
                        acc.token = new_token
                        await self.db.commit()
                except Exception:
                    try: await self.db.rollback()
                    except Exception: pass
                return True

        return False

    async def _handle_auth_failure(self, account_id: str):
        """401 认证失败回调"""
        if _relogin_locks.get(account_id):
            return
        _relogin_locks[account_id] = True
        try:
            if self.username and self.password_encrypted:
                ok = await self.relogin()
                if ok:
                    await self.client.ensure_ecdsa_ready()
                    await asyncio.sleep(1)
                    logger.info(f"[{self.id}] 重登成功")
                else:
                    logger.error(f"[{self.id}] 重登失败")
            else:
                logger.warning(f"[{self.id}] 无账密，无法自动重登")
        finally:
            _relogin_locks[account_id] = False

    # ——— 持久化辅助 ———

    async def _save_running(self, running: int):
        try:
            acc = await self.db.get(Account, self.id)
            if acc:
                acc.running = running
                await self.db.commit()
        except Exception as e:
            logger.error(f"[{self.id}] _save_running 失败: {e}")
            try: await self.db.rollback()
            except Exception: pass

    async def _save_info(self):
        try:
            acc = await self.db.get(Account, self.id)
            if acc:
                acc.nickname = self.nickname
                acc.level = self.level
                acc.class_name = self.class_name
                await self.db.commit()
        except Exception as e:
            logger.error(f"[{self.id}] _save_info 失败: {e}")
            try: await self.db.rollback()
            except Exception: pass

    # ——— 获取同行账号（同用户的托管账号） ———

    async def get_peers(self) -> list[dict]:
        """返回同用户下其他托管账号"""
        result = await self.db.execute(
            select(Account.id, Account.nickname, Account.user_id)
            .where(Account.user_id > 0, Account.id != self.id)
        )
        return [{"id": r[0], "nickname": r[1], "user_id": r[2]} for r in result.fetchall()]


async def list_accounts(db: AsyncSession) -> list[dict]:
    """返回所有账号摘要（供 Dashboard API 使用）"""
    from app.services.engine import _engines
    result = await db.execute(select(Account).order_by(Account.sort_order, Account.id))
    rows = result.scalars().all()
    accounts = []
    for row in rows:
        engine = _engines.get(row.id)
        accounts.append({
            "id": row.id,
            "name": row.nickname or row.id[:8],
            "level": row.level,
            "class_name": row.class_name,
            "sort_order": row.sort_order,
            "running": bool(row.running),
            "user_id": row.user_id,
            "has_credentials": bool(row.username and row.password),
            "is_premium": bool(row.is_premium),
            "premium_expires_at": str(row.premium_expires_at) if row.premium_expires_at else None,
            "today_exp_gained": 0,
            "stats": {},
            "farm_stats": {},
        })
    return accounts
