"""好友同步 — 托管账号间互加，6小时冷却"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 6 * 3600


class FriendSync:

    def __init__(self, client: QPetClient, account_id: str, peers: list[dict]):
        self._client = client
        self._account_id = account_id
        self._peers = peers

    async def run(self) -> int:
        """返回新增好友数"""
        friends = await self._client.get_friends()
        if not friends.get("success"):
            return 0
        existing_ids = {f.get("userId") or f.get("id") for f in friends.get("data", []) or []}

        # 检查待处理请求
        requests = await self._client.get_friend_requests()
        pending_ids = set()
        if requests.get("success"):
            for r in requests.get("data", {}).get("requests", []):
                uid = r.get("userId") or r.get("id")
                if uid:
                    pending_ids.add(uid)

        added = 0
        for peer in self._peers:
            peer_id = peer.get("id")
            if peer_id in existing_ids:
                continue
            if peer_id in pending_ids:
                await self._client.accept_friend(peer_id)
                added += 1
            else:
                await self._client.request_friend(peer_id)

        if added:
            logger.info(f"[{self._account_id}] 好友同步 +{added}")
        return added
