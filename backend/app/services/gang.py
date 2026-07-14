"""帮派管理 — 捐赠+技能学习"""
import logging
from app.services.qpet_client import QPetClient

logger = logging.getLogger(__name__)


class Gang:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> dict:
        """返回 {donated, skills_learned}"""
        results = {"donated": False, "skills_learned": 0}

        status = await self._client.get_gang_status()
        if not status.get("success"):
            return results

        data = status.get("data", {})

        # 捐赠
        if data.get("canDonate", False):
            result = await self._client.gang_donate(500)
            if result.get("success"):
                results["donated"] = True
                logger.info(f"[{self._account_id}] 帮派捐赠")

        # 技能学习
        skills = data.get("availableSkills", data.get("skills", []))
        for skill in skills:
            if skill.get("canLearn", False):
                result = await self._client.learn_gang_skill(skill.get("name", ""))
                if result.get("success"):
                    results["skills_learned"] += 1

        if results["skills_learned"]:
            logger.info(f"[{self._account_id}] 学习帮派技能 {results['skills_learned']}个")

        return results
