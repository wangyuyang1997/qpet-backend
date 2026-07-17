"""QPet 游戏 API 客户端 — ECDSA 签名 + HTTP + 风控 + 静默白名单"""
import json
import time
import random
import uuid
from urllib.parse import urlencode, quote
import httpx
from app.config import settings
from app.core.crypto import (
    generate_ecdsa_keypair,
    export_private_jwk,
    export_public_jwk,
    load_key_store,
    save_key_store,
    import_private_key,
    ecdsa_sign,
)

# 已知良性失败消息，不记日志
SILENT_ERRORS = [
    "已偷过", "已偷完", "该作物已被偷完", "黑土地作物无法偷取",
    "该地块没有作物", "仅成熟作物可偷取", "体力不足",
    "你没有加入帮派", "没有可免费挑战的BOSS",
    "一键合成为会员专属", "今日送花已达上限", "没有鲜花道具",
    "已签到",
]


class QPetClient:
    """游戏 API 客户端 — 每账号一个实例"""

    def __init__(self, account_id: str, token: str, on_auth_failure=None):
        self.account_id = account_id
        self.token = token
        self.private_key = None
        self._ready = False
        self.on_auth_failure = on_auth_failure  # async callback for 401
        self.on_rate_limited = None  # 风控回调
        self._describe_cache = {}  # path → (category, module)
        self._last_api_call = ""    # 最近一次 API 调用路径，供风控日志使用

    # ——— ECDSA 管理 ———

    async def init_ecdsa(self) -> bool:
        """初始化 ECDSA 密钥：从文件加载或生成新密钥并注册"""
        store = load_key_store()
        jwk = store.get(self.account_id)
        if jwk:
            try:
                self.private_key = import_private_key(jwk)
                self._ready = True
                return True
            except Exception:
                pass

        # 生成新密钥对
        key = generate_ecdsa_keypair()
        pub_jwk = export_public_jwk(key)
        priv_jwk = export_private_jwk(key)

        # 向游戏服务器注册公钥
        result = await self._raw_request(
            "POST", "/auth/register-signing-key",
            body={"publicKey": pub_jwk},
            skip_sign=True,
        )
        if result.get("success"):
            store[self.account_id] = priv_jwk
            save_key_store(store)
            self.private_key = key
            self._ready = True
            return True

        return False

    async def ensure_ecdsa_ready(self) -> bool:
        """确保 ECDSA 就绪，未就绪则初始化"""
        if self._ready and self.private_key:
            return True
        return await self.init_ecdsa()

    def delete_key(self):
        """删除本地密钥（用于重登后重新注册）"""
        store = load_key_store()
        store.pop(self.account_id, None)
        save_key_store(store)
        self.private_key = None
        self._ready = False

    # ——— API 调用 ———

    async def api_call(self, method: str, path: str, body: dict = None, params: dict = None) -> dict:
        """带 ECDSA 签名的 API 调用"""
        body = body or {}
        params = params or {}

        timestamp = str(int(time.time() * 1000))
        nonce = _random_nonce(16)
        self._last_api_call = f"{method} {path}"
        client_request_id = str(uuid.uuid4())

        # 注入 clientRequestId（必须在签名前，验签时服务端也会包含此参数）
        if method.upper() == "GET":
            params["clientRequestId"] = client_request_id
        else:
            body["clientRequestId"] = client_request_id

        # 签名
        param_str = _build_sorted_params(body, params)
        sig_path = "/api" + path.split("?")[0].rstrip("/") or "/api"
        sign_str = method.upper() + sig_path + param_str + timestamp + nonce

        if self.private_key:
            signature = ecdsa_sign(self.private_key, sign_str)
        else:
            signature = ""

        headers = {
            "x-api-signature": signature,
            "x-api-timestamp": timestamp,
            "x-api-nonce": nonce,
            "Authorization": f"Bearer {self.token}",
        }
        if method.upper() != "GET":
            headers["Content-Type"] = "application/json"

        url = settings.game_api_base_url + path

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers, params=params)
                else:
                    resp = await client.post(url, headers=headers, json=body)

                # POST 后随机延迟
                if method.upper() != "GET":
                    delay = 0.6 + random.random() * 2.4
                    await _async_sleep(delay)

                if resp.status_code == 429:
                    if self.on_rate_limited:
                        self.on_rate_limited(self._last_api_call)
                    return {"success": False, "rateLimited": True, "message": "请求过于频繁"}

                if resp.status_code == 401:
                    return {"success": False, "message": "认证失败"}

                try:
                    data = resp.json()
                except Exception:
                    return {"success": False, "message": "服务器返回异常"}

                if not data.get("success"):
                    msg = data.get("message", "")
                    if not any(e in msg for e in SILENT_ERRORS):
                        pass  # 日志由调用方处理

                return data

        except httpx.RequestError:
            return {"success": False, "message": "网络错误"}

    async def _raw_request(self, method: str, path: str, body: dict = None, skip_sign: bool = False) -> dict:
        """无签名的原始请求（用于注册 ECDSA 公钥）"""
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        url = settings.game_api_base_url + path
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, json=body or {})
            try:
                return resp.json()
            except Exception:
                return {"success": False}

    # ——— 便捷方法：QPet 乐斗 API ———

    async def get_character(self): return await self.api_call("GET", "/qpet/character")
    async def get_profile(self): return await self.api_call("GET", "/user/profile")
    async def get_level_info(self): return await self.api_call("GET", "/user/level")
    async def get_checkin_info(self): return await self.api_call("GET", "/user/checkin")
    async def checkin(self): return await self.api_call("POST", "/user/checkin")
    async def get_chest_status(self): return await self.api_call("GET", "/qpet/collection-chest")
    async def open_chest(self): return await self.api_call("POST", "/qpet/collection-chest/open")
    async def get_inventory(self): return await self.api_call("GET", "/qpet/inventory")
    async def use_item(self, item_type: str, item_id: str, quantity: int = 1):
        return await self.api_call("POST", "/qpet/inventory/use", {"itemType": item_type, "itemId": item_id, "quantity": quantity})
    async def fight_npc(self): return await self.api_call("POST", "/qpet/battle/prepare", {"isNpc": True})
    async def settle_battle(self, battle_token: str, atk_won: bool):
        return await self.api_call("POST", "/qpet/battle/settle", {"battleToken": battle_token, "atkWon": atk_won})
    async def get_tower_status(self): return await self.api_call("GET", "/qpet/tower/status")
    async def prepare_tower(self, floor: int, use_revive: bool = False):
        return await self.api_call("POST", "/qpet/tower/prepare", {"floor": floor, "useRevive": use_revive})
    async def settle_tower(self, battle_token: str, atk_won: bool):
        return await self.api_call("POST", "/qpet/tower/settle", {"battleToken": battle_token, "atkWon": atk_won})
    async def get_gang_boss_status(self): return await self.api_call("GET", "/qpet/social/gang/boss/status")
    async def prepare_gang_boss(self, boss_id): return await self.api_call("POST", "/qpet/social/gang/boss/prepare", {"bossId": boss_id})
    async def settle_gang_boss(self, battle_token: str, atk_won: bool):
        return await self.api_call("POST", "/qpet/social/gang/boss/settle", {"battleToken": battle_token, "atkWon": atk_won})
    async def get_class_info(self): return await self.api_call("GET", "/qpet/class/info")
    async def get_class_guide(self): return await self.api_call("GET", "/qpet/class/guide")
    async def select_class(self, class_id: str): return await self.api_call("POST", "/qpet/class/select", {"classId": class_id})
    async def get_skill_tree(self): return await self.api_call("GET", "/qpet/class/skill-tree")
    async def allocate_skill(self, skill_id: str): return await self.api_call("POST", "/qpet/class/skill/allocate", {"skillId": skill_id})
    async def awaken_class(self): return await self.api_call("POST", "/qpet/class/awaken")
    async def get_bead_inventory(self): return await self.api_call("GET", "/qpet/beads/inventory")
    async def auto_merge_beads(self, bead_type: str, target_level: int):
        return await self.api_call("POST", "/qpet/beads/auto-merge", {"beadType": bead_type, "targetLevel": target_level})
    async def merge_beads(self, bead_type: str, target_level: int):
        return await self.api_call("POST", "/qpet/beads/merge", {"beadType": bead_type, "targetLevel": target_level})
    async def get_equipment(self): return await self.api_call("GET", "/qpet/equipment")
    async def equip_item(self, equipment_id): return await self.api_call("POST", "/qpet/equipment/equip", {"equipmentId": equipment_id})
    async def get_shop_status(self): return await self.api_call("GET", "/qpet/shop/status")
    async def buy_item(self, item_id: str): return await self.api_call("POST", "/qpet/shop/buy", {"itemId": item_id})
    async def get_ad_stamina_status(self): return await self.api_call("GET", "/qpet/ad-stamina/status")
    async def claim_ad_stamina(self): return await self.api_call("POST", "/qpet/ad-stamina/claim")
    async def get_marriage_status(self): return await self.api_call("GET", "/qpet/social/marriage/status")
    async def prepare_marriage_boss(self): return await self.api_call("POST", "/qpet/social/marriage/boss/prepare")
    async def settle_marriage_boss(self, battle_token: str, atk_won: bool):
        return await self.api_call("POST", "/qpet/social/marriage/boss/settle", {"battleToken": battle_token, "atkWon": atk_won})
    async def send_gift(self, friend_id): return await self.api_call("POST", "/qpet/social/marriage/gift", {"friendId": friend_id})
    async def get_friend_intimacy(self): return await self.api_call("GET", "/qpet/social/friend/intimacy")
    async def propose_marriage(self): return await self.api_call("POST", "/qpet/social/marriage/propose")
    async def respond_marriage(self, accept: bool): return await self.api_call("POST", "/qpet/social/marriage/respond", {"accept": accept})
    async def send_friend_flower(self, target_user_id): return await self.api_call("POST", "/qpet/social/friend/flower", {"targetUserId": target_user_id})
    async def get_friends(self): return await self.api_call("GET", "/qpet/friends")
    async def get_fightable_friends(self): return await self.api_call("GET", "/qpet/battle/friends")
    async def get_friend_requests(self): return await self.api_call("GET", "/qpet/social/friends/requests")
    async def accept_friend(self, user_id): return await self.api_call("POST", f"/qpet/social/friends/accept/{user_id}")
    async def request_friend(self, user_id): return await self.api_call("POST", f"/qpet/social/friends/request/{user_id}")
    async def get_auction_listings(self, page: int = 1, page_size: int = 50, sort_by: str = "created_at", order: str = "DESC"):
        return await self.api_call("GET", "/qpet/auction/listings", params={"page": page, "pageSize": page_size, "sortBy": sort_by, "order": order})
    async def buy_auction(self, listing_id): return await self.api_call("POST", "/qpet/auction/buy", {"listingId": listing_id})
    async def get_tournament_status(self): return await self.api_call("GET", "/qpet/tournament/status")
    async def get_ranking(self): return await self.api_call("GET", "/qpet/ranking")
    async def get_gang_status(self): return await self.api_call("GET", "/qpet/social/gang/status")
    async def get_gang_list(self): return await self.api_call("GET", "/qpet/social/gang/list")
    async def gang_donate(self, amount: int): return await self.api_call("POST", "/qpet/social/gang/donate", {"amount": amount})
    async def learn_gang_skill(self, skill_name: str): return await self.api_call("POST", "/qpet/social/gang/skill/learn", {"skillName": skill_name})
    async def get_furnace_shop(self): return await self.api_call("GET", "/qpet/furnace/shop")
    async def get_territory(self): return await self.api_call("GET", "/qpet/territory")
    async def get_equipment_enhance(self): return await self.api_call("GET", "/qpet/equipment-enhance")
    async def get_exhibition_chest(self): return await self.api_call("GET", "/qpet/exhibition-hall/chest-status")
    async def open_exhibition_chest(self): return await self.api_call("POST", "/qpet/exhibition-hall/chest-open")

    # ——— Farm API ———
    async def farm_get_status(self): return await self.api_call("GET", "/farm")
    async def farm_plant(self, slot: int, crop_id: str): return await self.api_call("POST", f"/farm/slots/{slot}/plant", {"cropId": crop_id})
    async def farm_harvest(self, slot: int): return await self.api_call("POST", f"/farm/slots/{slot}/harvest")
    async def farm_harvest_all(self): return await self.api_call("POST", "/farm/actions/harvest-all")
    async def farm_remove(self, slot: int): return await self.api_call("POST", f"/farm/slots/{slot}/remove")
    async def farm_care(self, slot: int): return await self.api_call("POST", f"/farm/slots/{slot}/care")
    async def farm_use_item(self, slot: int, item_id: str): return await self.api_call("POST", f"/farm/slots/{slot}/item", {"itemId": item_id})
    async def farm_claim_visit(self): return await self.api_call("POST", "/farm/visit")
    async def farm_get_friend(self, friend_id): return await self.api_call("GET", f"/farm/friend/{friend_id}")
    async def farm_help_friend(self, friend_id, slot: int): return await self.api_call("POST", f"/farm/friend/{friend_id}/slots/{slot}/help")
    async def farm_steal(self, friend_id, slot: int, mouse_trail: list):
        return await self.api_call("POST", f"/farm/friend/{friend_id}/slots/{slot}/steal", {"mouseTrail": mouse_trail})
    async def farm_get_ad_status(self): return await self.api_call("GET", "/farm/ad-bonus/status")
    async def farm_claim_ad(self): return await self.api_call("POST", "/farm/ad-bonus/claim")

    # ——— Farm 翻地 ———
    async def farm_explore_all(self): return await self.api_call("POST", "/farm/actions/explore-all")
    async def farm_explore(self, slot: int): return await self.api_call("POST", f"/farm/slots/{slot}/explore")
    async def farm_explore_friend(self, friend_id, slot: int): return await self.api_call("POST", f"/farm/friend/{friend_id}/slots/{slot}/explore")

    # ——— Farm 土地升级 ———
    async def farm_upgrade_land(self, slot: int): return await self.api_call("POST", f"/farm/slots/{slot}/upgrade-land")

    # ——— Farm 批量操作 ———
    async def farm_plant_all(self, crop_id: str): return await self.api_call("POST", "/farm/actions/plant-all", {"cropId": crop_id})
    async def farm_double_exp_all(self): return await self.api_call("POST", "/farm/actions/double-exp-all")
    async def farm_protect_all(self): return await self.api_call("POST", "/farm/actions/protect-all")
    async def farm_remove_all(self): return await self.api_call("POST", "/farm/actions/remove-all")
    async def farm_accelerate_all(self): return await self.api_call("POST", "/farm/actions/accelerate-all")

    # ——— Farm 查询 ———
    async def farm_get_steal_log(self, page: int = 1, limit: int = 30): return await self.api_call("GET", f"/farm/steal-log?page={page}&limit={limit}")
    async def farm_get_steal_rank(self, limit: int = 20): return await self.api_call("GET", f"/farm/steal-rank?limit={limit}")

    # ——— Community API ———
    async def community_get_ad_status(self): return await self.api_call("GET", "/community/ad-reward/status")
    async def community_claim_ad(self): return await self.api_call("POST", "/community/ad-reward/claim")


# ——— 工具函数 ———

def _random_nonce(length: int = 16) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def _build_sorted_params(body: dict, params: dict) -> str:
    """按 key 字母序排列的 key=encodeURIComponent(value)&..."""
    merged = {}
    if params:
        merged.update(params)
    if body:
        merged.update(body)
    parts = []
    for k in sorted(merged):
        v = merged[k]
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            parts.append(f"{k}={quote(json.dumps(v, separators=(',', ':')))}")
        elif isinstance(v, bool):
            parts.append(f"{k}={quote('true' if v else 'false')}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}={v}")
        else:
            parts.append(f"{k}={quote(str(v))}")
    return "&".join(parts)


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
