# 游戏 API 参考

以下是游戏支持的 API。AI 只能引用查询类 API 的数据来回答问题，不能调用或触发任何 API。

## 角色查询（只读）
- `GET /api/qpet/character` — 角色完整信息（属性/技能/武器/装备/职业/战力）
- `GET /api/qpet/battle/friends` — 可挑战好友列表
- `GET /api/qpet/battle/reports?page=1` — 战斗记录
- `GET /api/qpet/tower/status` — 斗神塔状态（剩余次数/当前楼层）
- `GET /api/qpet/dungeon/status` — 副本状态
- `GET /api/qpet/world-boss/status` — 世界BOSS状态
- `GET /api/qpet/world-boss/battle-log?userId=N` — BOSS战斗日志
- `GET /api/qpet/class/info` — 职业信息
- `GET /api/qpet/class/skill-tree` — 技能树
- `GET /api/qpet/equipment` — 装备列表
- `GET /api/qpet/beads/inventory` — 魂珠背包
- `GET /api/qpet/inventory` — 背包物品
- `GET /api/qpet/shop/status` — 商店状态
- `GET /api/qpet/ranking` — 排行榜（公开）
- `GET /api/qpet/ad-stamina/status` — 广告体力状态
- `GET /api/qpet/home` — 首页数据聚合

## 社交查询（只读）
- `GET /api/qpet/social/gang/status` — 帮派状态
- `GET /api/qpet/social/gang/list` — 帮派列表
- `GET /api/qpet/social/gang/boss/status` — 帮派BOSS状态
- `GET /api/qpet/social/gang/boss/log?limit=N` — BOSS战斗日志
- `GET /api/qpet/social/marriage/status` — 婚姻状态
- `GET /api/qpet/social/mentor/status` — 师徒状态
- `GET /api/qpet/social/friend/intimacy` — 好友亲密度
- `GET /api/qpet/friends` — 好友列表

## 赛事查询（只读）
- `GET /api/qpet/tournament/status` — 武林大会状态
- `GET /api/qpet/tournament/bracket` — 对阵表
- `GET /api/qpet/tournament/history` — 历史记录
- `GET /api/qpet/championship/list` — 锦标赛列表
- `GET /api/qpet/championship/history` — 历史赛事
- `GET /api/qpet/auction/listings` — 拍卖列表
- `GET /api/qpet/auction/history` — 拍卖历史

## 用户查询（只读）
- `GET /api/user/profile` — 用户资料
- `GET /api/user/level` — 用户等级（博客读者等级/农场等级）
- `GET /api/user/achievements` — 成就系统
- `GET /api/user/titles` — 称号列表
- `GET /api/user/ranking` — 用户排名
- `GET /api/user/experience-logs?limit=50` — 经验日志

## 农场查询（只读）
- `GET /api/farm` — 农场完整状态（核心端点：serverTime/等级/地块/作物/Premium）
- `GET /api/farm/friend/:friendId` — 查看好友农场
- `GET /api/farm/steal-log` — 偷菜记录
- `GET /api/farm/steal-rank` — 偷菜排行榜
- `GET /api/farm/ad-bonus/status` — 广告奖励状态

## 作物目录（72种，按等级段解锁）

Lv1: 藜麦(VIP) | Lv2: 大麦/燕麦/胡萝卜/卷心菜/向日葵 | Lv3: 黑麦/番茄/黄瓜/草莓/郁金香/雏菊/巴西莓(VIP)
Lv4: 高粱/荞麦/玉米/辣椒/茄子/豌豆/芹菜/康乃馨 | Lv5: 土豆/洋葱/豆角/葡萄/西瓜/玫瑰/香荚兰(VIP)
Lv6: 南瓜/西兰花/甜瓜/苹果/梨/樱桃/百合 | Lv7: 花椰菜/桃子/薰衣草
Lv8: 芦笋/柠檬/茉莉/人参/松茸(VIP) | Lv9: 橙子/香蕉/牡丹/藏红花
Lv10: 洋蓟/芒果/菠萝/兰花/松露/金麦/冬虫夏草(VIP) | Lv11: 椰子/石榴/莲花/杨桃/黑松露(VIP)
Lv12: 火龙果/樱花/雪梨 | Lv13: 冰晶花 | Lv14: 蓝玫瑰/月光草/幽灵兰(VIP)
Lv15: 凤凰果 | Lv16: 龙珠果/昙花(VIP) | Lv17: 大王花(VIP) | Lv18: 永恒之花/天山雪莲(VIP)

品质分布: 普通28/精良22/稀有17/传说8（VIP10款全部传说）
收益计算: expReward = max(2, round(round(10*(time/60)^0.6)*rarityMult))
播种建议: 胡萝卜全场最优，Lv1用藜麦

## 副本秘境参数（7种）
| 秘境 | 层数 | 每日上限 | 体力 | EXP/层 | Boss倍率 |
|------|------|---------|------|--------|---------|
| 青铜 | 10 | 5 | 20 | 15 | 3× |
| 白银 | 15 | 4 | 25 | 25 | 3× |
| 黄金 | 20 | 4 | 30 | 40 | 3× |
| 钻石 | 20 | 3 | 35 | 60 | 3× |
| 铂金 | 25 | 3 | 40 | 90 | 3× |
| 传说 | 25 | 3 | 50 | 130 | 3× |
| 大师 | 25 | 3 | 50 | 180 | 3× |
难度倍率: stat×0.4~1.0 / hp×0.35~1.0 / exp×0.5~1.0 / drop×0.25~1.0

## 其他API
**展览馆**: GET /api/qpet/exhibition-hall/chest-status, POST /chest-open(消耗EXP)
**老虎机**: GET /api/slot/info, POST /api/slot/play(消耗EXP)
**邀请币商店**: GET /api/invite-coin-shop/items, /equipment-options, POST /purchase
**好友交易**: GET /api/qpet/friend-trade/offers, POST /create, /accept, /cancel
**收集宝箱**: GET /api/qpet/collection-chest
**突袭Raid**: GET /api/qpet/raid
