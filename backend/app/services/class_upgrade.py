"""职业/技能/觉醒"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class ClassUpgrade:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, level: int = 0) -> dict:
        """返回 {selected, skills_allocated, awakened}"""
        results = {"selected": False, "skills_allocated": 0, "awakened": False}

        info = await self._client.get_class_info()
        if not info.get("success"):
            return results

        data = info.get("data", {})

        # 选择职业
        if not data.get("className"):
            guide = await self._client.get_class_guide()
            classes = guide.get("data", {}).get("available", [])
            if classes:
                result = await self._client.select_class(classes[0].get("id"))
                if result.get("success"):
                    results["selected"] = True
                    logger.info(f"[{self._account_id}] 选择职业: {classes[0].get('name')}")

        # 分配技能
        tree = await self._client.get_skill_tree()
        if tree.get("success"):
            nodes = tree.get("data", {}).get("nodes", [])
            for node in nodes:
                if node.get("canAllocate", False):
                    result = await self._client.allocate_skill(node.get("id"))
                    if result.get("success"):
                        results["skills_allocated"] += 1

        if results["skills_allocated"]:
            logger.info(f"[{self._account_id}] 分配技能 {results['skills_allocated']}个")

        # 觉醒
        if level >= 40 and data.get("canAwaken", False):
            result = await self._client.awaken_class()
            if result.get("success"):
                results["awakened"] = True
                logger.info(f"[{self._account_id}] 职业觉醒成功")

        return results
