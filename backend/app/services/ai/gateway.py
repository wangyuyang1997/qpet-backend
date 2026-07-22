"""AI 核心网关 — 消息组装、缓存、流式响应、日志"""
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from collections import OrderedDict
from typing import AsyncGenerator, Callable

from .deepseek import chat_stream, MODEL_CHAT, MODEL_REASONER
from .tools import run_tools
from app.config import settings

logger = logging.getLogger("qpet.ai.gateway")

COMPLEX_KW = ["分析", "策略", "怎么", "为什么", "对比", "比较", "推荐", "建议", "规划",
              "方案", "评估", "优先级", "怎么选", "哪个好", "如何", "应该", "值不值得",
              "优缺点", "接下来", "下一步", "发展", "搭配", "配置", "最优", "毕业",
              "怎么打", "选什么", "好不好", "值得吗", "划算", "怎么升", "怎么玩"]

def _is_complex(question: str) -> bool:
    """判断问题是否复杂，需要深度推理"""
    q = question.strip()
    if q.count("？") + q.count("?") >= 2:
        return True
    if len(q) > 60:
        return True
    if "\n" in q:
        return True
    if sum(1 for k in COMPLEX_KW if k in q) >= 2:
        return True
    return False


CORE_KW = ["技能", "装备", "武器", "战斗", "等级", "战力", "职业", "重开", "爬塔", "帮派", "帮会",
           "农场", "作物", "魂珠", "拍卖", "副本", "塔", "BOSS", "加点", "属性", "套装", "词缀",
           "护甲", "秘境", "远征"]
DANGER_KW = ["密码", "token", "密钥", "数据库", "IP", "端口", "加密", "哈希", "删库", "注入",
             "admin", "api", "config", "ssh", "root", "private", "key", "secret"]

TAG_RULES = [
    {"tag": "重开评估", "kw": ["重开", "值不值得练", "技能评估", "要不要练", "成了没", "废了", "能玩吗", "洗技能", "洗点"]},
    {"tag": "装备咨询", "kw": ["装备", "穿了什么", "头盔", "护甲", "护腕", "腰带", "鞋子", "项链", "套装", "词缀", "强化", "贴膜", "熔炉", "余烬", "炉心"]},
    {"tag": "技能分析", "kw": ["技能", "技能树", "加点", "SP", "觉醒", "被动", "学什么", "哪个技能"]},
    {"tag": "战斗策略", "kw": ["战斗", "打不过", "怎么打", "策略", "配队", "技能搭配", "输出", "伤害", "秒杀"]},
    {"tag": "农场相关", "kw": ["农场", "种地", "作物", "图鉴", "浇水", "偷菜", "播种", "收获", "种植", "收菜", "成熟", "种什么"]},
    {"tag": "爬塔副本", "kw": ["爬塔", "塔", "楼层", "副本", "秘境", "BOSS", "远征", "安图恩", "斗神塔"]},
    {"tag": "职业选择", "kw": ["职业", "转职", "练什么", "哪个职业", "剑魂", "狂战", "圣骑", "气功", "散打", "元素", "刺客", "枪手"]},
    {"tag": "拍卖交易", "kw": ["拍卖", "交易", "上架", "竞拍", "价格", "买", "卖", "行情"]},
    {"tag": "帮派咨询", "kw": ["帮派", "帮会", "帮主", "帮战", "BOSS", "贡献", "帮派技能", "守护神", "捐献", "帮派列表"]},
    {"tag": "数据查询", "kw": ["背包", "物品", "有几个", "还有多少", "数量", "状态", "剩余", "签到", "体力", "还魂", "元宝", "金币"]},
    {"tag": "账号评估", "kw": ["分析", "看看账号", "怎么样", "优缺点", "帮我看看", "什么水平", "值多少"]},
    {"tag": "社交相关", "kw": ["好友", "结婚", "师徒", "师傅", "徒弟", "夫妻", "求婚", "离婚", "拜师", "收徒", "送花"]},
    {"tag": "排行地盘", "kw": ["排行", "排名", "地盘", "占领", "战力", "第几名"]},
]

HERE = Path(__file__).resolve().parent
CACHE_TTL = 30 * 60  # 30 min
CACHE_MAX = 200


def _analyze_question(question: str) -> dict:
    q = question.lower()
    core = 1 if any(k in q for k in CORE_KW) else 2
    danger = 1 if any(k in q for k in DANGER_KW) else 2
    tags = [r["tag"] for r in TAG_RULES if any(k in q for k in r["kw"])]
    return {"isCore": core, "isDanger": danger, "tags": tags}


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cn = len(re.findall(r"[一-鿿]", text))
    en = len(text) - cn
    return int(cn / 1.5 + en / 4)


class AIService:
    def __init__(self):
        self.system_prompt = ""
        self.knowledge_base = ""
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._ready = False

    def init(self) -> bool:
        """加载 system prompt 和知识库。成功返回 True。"""
        if not settings.deepseek_api_key:
            logger.warning("[ai] DeepSeek API key 未配置，AI 功能禁用")
            return False

        # 加载 system.md
        sp = HERE / "system.md"
        if sp.exists():
            self.system_prompt = sp.read_text(encoding="utf-8")

        # 加载知识库
        kb_dir = HERE / "knowledge"
        parts = []
        if kb_dir.is_dir():
            for f in sorted(kb_dir.iterdir()):
                if f.suffix == ".md":
                    parts.append(f.read_text(encoding="utf-8"))
        self.knowledge_base = "\n\n---\n\n".join(parts)
        total = sum(len(p) for p in parts)
        logger.info(f"[ai] 知识库加载完成: {len(parts)} 文件, {total / 1024:.1f}KB")

        self._ready = True
        return True

    @property
    def is_ready(self) -> bool:
        return self._ready and bool(settings.deepseek_api_key)

    async def chat(
        self,
        message: str,
        account_id: str = "",
        char_data: dict | None = None,
        *,
        history: list[dict] | None = None,
        tool_results: list[dict] | None = None,
        user_id: int = 0,
        username: str = "",
        log_callback: Callable | None = None,
    ) -> AsyncGenerator[dict, None]:
        """async generator: yield {"chunk": str} | {"cached": True, "content": str} | {"error": str}"""
        actual_model = settings.deepseek_model  # 可能在模型路由中改为 reasoner
        question = message.strip()
        if not question or not self.is_ready:
            yield {"error": "empty message" if not question else "AI not configured"}
            return

        # ── 构建 messages ──
        messages = [{"role": "system", "content": self.system_prompt + "\n\n" + self.knowledge_base}]

        # 角色上下文
        char = char_data or {}
        skills = ", ".join(f"{s.get('name', '?')} Lv{s.get('level', 0)}" for s in (char.get("skills", []) or []))
        user_ctx = (
            f"## 当前角色\n"
            f"- 账号: {char.get('name') or char.get('nickname') or account_id}\n"
            f"- 等级: Lv{char.get('level', 0)}\n"
            f"- 职业: {char.get('className', '未知')}\n"
            f"- 战力: {char.get('combatPower', '?')}\n"
            f"- 已有技能: {skills or '无'}"
        )
        messages.append({"role": "user", "content": user_ctx})

        # 历史对话
        hist = history or []
        if hist:
            for m in hist[-12:]:
                messages.append({"role": m.get("role", "user"), "content": (m.get("content", ""))[:2000]})

        # 工具数据
        tools_used_str = None
        tools_data_size = 0
        if not tool_results:
            # Router can pass pre-fetched results; if not, skip (no client here)
            tool_results = []
        if tool_results:
            lines = ["\n\n以下是你通过API获取到的实时游戏数据。这些数据是真实可信的，你必须基于这些数据回答用户问题，不要说你没有数据或无法查询。\n"]
            for r in tool_results:
                d = r.get("data", {})
                hint = ""
                if r.get("tool") == "farm" and isinstance(d, dict) and d.get("collection"):
                    col = d["collection"]
                    hint = f"\n[摘要: Lv{d.get('level')}农场, {d.get('unlockedSlots')}块地, 图鉴{col.get('total')}条({col.get('uniqueCrops')}/{col.get('totalCrops')}种, {col.get('fullCollected')}种全收集), VIP={d.get('isPremium')}, {len(col.get('notCollected',[]))}种未收集]"
                elif r.get("tool") == "inventory" and isinstance(d, dict):
                    hint = f"\n[摘要: 背包{d.get('total', 0)}件物品]"
                lines.append(f"### {r['tool']} ({r.get('endpoint', '')}){hint}\n{json.dumps(d, ensure_ascii=False)}")
            tool_ctx = "\n\n".join(lines)
            messages.append({"role": "user", "content": tool_ctx})
            tools_used_str = ",".join(r.get("tool", "") for r in tool_results)
            tools_data_size = sum(len(json.dumps(r.get("data", {}))) for r in tool_results)

        messages.append({"role": "user", "content": question})

        # ── 缓存检查 ──
        cache_key = _cache_key(account_id, question)
        cached = await self._cache_get(cache_key)
        if cached:
            yield {"cached": True, "content": cached}
            # 异步写日志
            if log_callback:
                try:
                    await log_callback({
                        "user_id": user_id, "username": username, "account_id": account_id,
                        "question": question, "answer": cached,
                        "model": actual_model,
                        "is_core_related": _analyze_question(question)["isCore"],
                        "is_dangerous": 0, "is_strategy_matched": 0, "satisfied": 0,
                        "tools_used": None, "tools_data_size": 0,
                        "prompt_tokens": 0, "completion_tokens": 0,
                        "elapsed_ms": 0, "from_cache": True, "tags": None,
                    })
                except Exception:
                    pass
            return

        # ── 模型路由 ──
        is_reroll = any(k in question for k in ["重开", "值不值得练", "技能评估", "要不要练", "成了没", "废了", "能玩吗"])
        is_complex = _is_complex(question)

        if is_reroll or is_complex:
            model = MODEL_REASONER
            max_tokens = 8192
            temperature = 0.0  # reasoner ignores this
            timeout = 120
        else:
            model = settings.deepseek_model  # deepseek-v4-pro (fast)
            max_tokens = 4096
            temperature = 0.6
            timeout = 60

        start_time = time.time()
        full_content = ""
        actual_model = model

        try:
            async for chunk in chat_stream(
                settings.deepseek_api_key,
                model,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            ):
                full_content += chunk
                yield {"chunk": chunk}
        except Exception as e:
            msg = str(e)
            if "timeout" in msg.lower():
                yield {"error": "AI 响应超时，请稍后重试"}
            else:
                yield {"error": f"AI 服务异常: {msg[:100]}"}
            return

        elapsed_ms = int((time.time() - start_time) * 1000)

        # ── 缓存 + 写日志 ──
        if full_content:
            await self._cache_set(cache_key, full_content)

        if log_callback:
            try:
                analysis = _analyze_question(question)
                await log_callback({
                    "user_id": user_id, "username": username, "account_id": account_id,
                    "question": question, "answer": full_content,
                    "model": actual_model,
                    "is_core_related": analysis["isCore"],
                    "is_dangerous": analysis["isDanger"],
                    "is_strategy_matched": 1 if analysis["isCore"] == 1 else 2,
                    "satisfied": 0,
                    "tools_used": tools_used_str,
                    "tools_data_size": tools_data_size,
                    "prompt_tokens": _estimate_tokens(self.system_prompt + self.knowledge_base + user_ctx + question),
                    "completion_tokens": _estimate_tokens(full_content) if full_content else 0,
                    "elapsed_ms": elapsed_ms,
                    "from_cache": False,
                    "tags": ",".join(analysis["tags"]) or None,
                })
            except Exception:
                pass

    # ── 缓存（内存 LRU + Redis）──

    async def _cache_get(self, key: str) -> str | None:
        # 先查内存
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < CACHE_TTL:
                self._cache.move_to_end(key)
                return val
            del self._cache[key]
        # 再查 Redis
        try:
            from app.core.redis import cache_get
            val = await cache_get(f"ai:cache:{key}")
            if val:
                self._cache[key] = (time.time(), val)
                return val
        except Exception:
            pass
        return None

    async def _cache_set(self, key: str, value: str):
        # 写内存
        if len(self._cache) >= CACHE_MAX:
            self._cache.popitem(last=False)
        self._cache[key] = (time.time(), value)
        # 写 Redis
        try:
            from app.core.redis import cache_set
            await cache_set(f"ai:cache:{key}", value, CACHE_TTL)
        except Exception:
            pass


def _cache_key(account_id: str, question: str) -> str:
    raw = f"{account_id}::{question.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


# 全局单例
service = AIService()
