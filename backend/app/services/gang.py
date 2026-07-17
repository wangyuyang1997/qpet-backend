"""帮派管理 — 技能学习"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import info, warn

logger = logging.getLogger(__name__)


class Gang:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self) -> dict:
        """返回 {skills_learned}"""
        results = {"skills_learned": 0}

        status = await self._client.get_gang_status()
        if not status.get("success"):
            warn("乐斗", "帮派", "获取帮派状态API失败", self._account_id)
            return results

        data = status.get("data", {})

        # 技能学习
        skills = data.get("availableSkills", data.get("skills", []))
        for skill in skills:
            if skill.get("canLearn", False):
                result = await self._client.learn_gang_skill(skill.get("name", ""))
                if result.get("success"):
                    results["skills_learned"] += 1
                else:
                    warn("乐斗", "帮派", f"学习技能失败: {skill.get('name', '?')}", self._account_id)

        if results["skills_learned"]:
            info("乐斗", "帮派", f"学习帮派技能 {results['skills_learned']}个", self._account_id)

        return results
