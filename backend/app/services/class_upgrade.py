"""职业/技能/觉醒"""
import logging
from app.services.qpet_client import QPetClient
from app.core.logger import action as log_action, warn, info

logger = logging.getLogger(__name__)


class ClassUpgrade:

    def __init__(self, client: QPetClient, account_id: str):
        self._client = client
        self._account_id = account_id

    async def run(self, level: int = 0) -> dict:
        results = {"selected": False, "skills_allocated": 0, "awakened": False}

        info = await self._client.get_class_info()
        if not info.get("success"):
            warn("乐斗", "修炼", "获取职业信息API失败", self._account_id)
            return results

        data = info.get("data", {})

        # 不自动选职业 — 用户手动选

        # 分配技能 — 对齐旧引擎：先看有没有SP → 被动优先 → 低tier优先 → 低cost优先
        sp = data.get("skillPoints", 0)
        if sp <= 0:
            return results

        tree = await self._client.get_skill_tree()
        if tree.get("success"):
            nodes = tree.get("data", {}).get("skillTree", [])
            remaining = tree.get("data", {}).get("skillPoints", sp)
            if remaining > 0 and nodes:
                allocatable = [n for n in nodes if n.get("canAllocate", False)]
                allocatable.sort(key=lambda n: (
                    0 if n.get("type") == "passive" else 1,
                    n.get("tier", 99),
                    n.get("spCost", 1),
                ))
                for node in allocatable:
                    if remaining <= 0:
                        break
                    cost = node.get("spCost", 1)
                    if remaining < cost:
                        continue
                    result = await self._client.allocate_skill(node.get("id"))
                    if result.get("success"):
                        remaining -= cost
                        results["skills_allocated"] += 1
                        name = node.get("name", "?")
                        log_action("乐斗", "修炼", f"分配技能点: {name}" + (f" ({cost}SP)" if cost > 1 else ""), self._account_id)
                    else:
                        warn("乐斗", "修炼", f"分配技能失败: {node.get('name', '?')}", self._account_id)
        else:
            warn("乐斗", "修炼", "获取技能树API失败", self._account_id)

        # 觉醒
        if level >= 40 and data.get("canAwaken", False):
            result = await self._client.awaken_class()
            if result.get("success"):
                results["awakened"] = True
                log_action("乐斗", "修炼", "职业觉醒成功", self._account_id)
            else:
                warn("乐斗", "修炼", "职业觉醒失败", self._account_id)

        if results["skills_allocated"]:
            info("乐斗", "修炼", f"技能分配完成: {results['skills_allocated']}点", self._account_id)

        return results
