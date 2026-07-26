# Q宠乐斗 Backend 数据字典

> 数据库: PostgreSQL 36.151.150.252:5432 (京东云 Docker)  
> ORM: SQLAlchemy 2.0 + Alembic  
> 更新: 2026-07-14

## 表关系图

```
users ──< user_accounts >── accounts ──< account_configs
  │                               │
  ├── ai_conversations             ├── daily_records
  ├── ai_daily_summary             ├── dungeon_configs
  │                                ├── dungeon_strategies
  │                                ├── dungeon_templates
  │                                ├── dungeon_history
  │                                └── dungeon_sessions
  │
config_definitions (无外键)
crop_cache (无外键)
auction_snapshots (无外键)
logs + logs_history (无外键)
```

---

## 1. users — 系统用户

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | 用户ID |
| `username` | String(64) | UNIQUE, NOT NULL | 用户名 |
| `password_hash` | Text | NOT NULL | bcrypt 密码哈希 |
| `role` | String(16) | DEFAULT 'user' | 角色: admin / user |
| `phone` | String(20) | NULL | 手机号 |
| `email` | String(128) | NULL | 邮箱 |
| `wechat_openid` | String(128) | UNIQUE, NULL | 微信 OpenID |
| `wechat_unionid` | String(128) | NULL | 微信 UnionID |
| `wechat_nickname` | String(64) | NULL | 微信昵称 |
| `wechat_avatar` | Text | NULL | 微信头像 URL |
| `created_at` | DateTime(tz) | DEFAULT NOW() | 创建时间 |
| `last_login` | DateTime(tz) | NULL | 最后登录时间 |

---

## 2. accounts — 游戏角色

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | String(12) | PK | token SHA256 前12位 hex |
| `nickname` | String(64) | DEFAULT '' | 角色昵称 |
| `level` | Integer | DEFAULT 0 | 乐斗等级 |
| `class_name` | String(32) | DEFAULT '' | 职业名称 |
| `token` | Text | DEFAULT '' | 游戏 API Bearer Token |
| `running` | Integer | DEFAULT 0 | 引擎状态: 1=运行中 0=已停止 |
| `automation` | JSONB | DEFAULT {} | 自动化开关配置 |
| `username` | String(64) | DEFAULT '' | 游戏登录账号 |
| `password` | Text | DEFAULT '' | 游戏登录密码(AES加密) |
| `user_id` | Integer | DEFAULT 0 | 绑定 Dashboard 用户 ID |
| `is_premium` | Integer | DEFAULT 0 | VIP 状态: 1=VIP 0=普通 |
| `premium_expires_at` | DateTime(tz) | NULL | VIP 到期时间 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | 创建时间 |
| `updated_at` | DateTime(tz) | DEFAULT NOW() | 更新时间 |

---

## 3. user_accounts — 用户-角色绑定

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `user_id` | Integer | PK, FK→users.id CASCADE | 用户ID |
| `account_id` | String(12) | PK, FK→accounts.id CASCADE | 角色ID |

唯一约束: (`user_id`, `account_id`)

---

## 4. daily_records — 每日统计

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | NOT NULL | 角色ID |
| `date` | Date | NOT NULL | 统计日期 |
| `level` | Integer | DEFAULT 0 | 当日等级 |
| `class_name` | String(32) | DEFAULT '' | 当日职业 |
| `combat_power` | Integer | DEFAULT 0 | 当日战力 |
| `npc_fights` | Integer | DEFAULT 0 | NPC 乐斗次数 |
| `tower_floors` | Integer | DEFAULT 0 | 爬塔层数 |
| `tower_max` | Integer | DEFAULT 0 | 爬塔最高层 |
| `friend_fights` | Integer | DEFAULT 0 | 好友乐斗次数 |
| | | | **农场统计** |
| `harvests` | Integer | DEFAULT 0 | 收获次数 |
| `plants` | Integer | DEFAULT 0 | 播种次数 |
| `steals` | Integer | DEFAULT 0 | 偷菜次数 |
| `waters` | Integer | DEFAULT 0 | 浇水次数 |
| `help_waters` | Integer | DEFAULT 0 | 帮好友浇水次数 |
| `digs` | Integer | DEFAULT 0 | 翻地次数 (v4.4 新增) |
| `land_upgrades` | Integer | DEFAULT 0 | 土地升级次数 (v4.4 新增) |
| `research_points_earned` | Integer | DEFAULT 0 | 获得研究点 (v4.4 新增) |
| `research_points_spent` | Integer | DEFAULT 0 | 消耗研究点 (v4.4 新增) |
| `farm_ads` | Integer | DEFAULT 0 | 农场广告次数 |
| `diversity` | Integer | DEFAULT 0 | 当日种植品种数 |
| `coll_crops` | Integer | DEFAULT 0 | 图鉴收集作物数 |
| `coll_slots` | Integer | DEFAULT 0 | 图鉴收集槽位数 |
| `exp_visit` | Integer | DEFAULT 0 | 访问经验 |
| `today_harvest_exp` | Integer | DEFAULT 0 | 今日收获经验 |
| | | | **通用统计** |
| `stamina_ads` | Integer | DEFAULT 0 | 体力广告次数 |
| `community_ads` | Integer | DEFAULT 0 | 社区广告次数 |
| `current_exp` | Integer | DEFAULT 0 | 当前经验 |
| `exp_battle` | Integer | DEFAULT 0 | 战斗获得经验 |
| `stamina` | Integer | DEFAULT 0 | 当前体力 |
| `max_stamina` | Integer | DEFAULT 0 | 最大体力 |
| `level_exp` | Integer | DEFAULT 0 | 当前等级经验 |
| `level_exp_max` | Integer | DEFAULT 0 | 升级所需经验 |
| `updated_at` | DateTime(tz) | DEFAULT NOW() | 更新时间 |

唯一约束: (`account_id`, `date`)

---

## 5. logs — 运行日志（当日）

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `timestamp` | DateTime(tz) | NOT NULL | 日志时间 |
| `level` | String(16) | DEFAULT 'info' | 级别 |
| `category` | String(32) | DEFAULT '' | 分类: 农场/乐斗/系统 |
| `module` | String(64) | DEFAULT '' | 模块: harvest/plant/steal 等 |
| `message` | Text | DEFAULT '' | 日志内容 |
| `data` | Text | NULL | 附加数据 JSON |
| `account` | String(12) | DEFAULT '' | 角色ID |

---

## 6. logs_history — 运行日志（历史）

结构同 `logs`。每日凌晨自动从 `logs` 迁移 7 天前的数据到此表。

---

## 7. crop_cache — 作物目录缓存

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | String(64) | PK | 作物 ID (如 carrot/vanilla) |
| `name` | String(64) | DEFAULT '' | 中文名 |
| `category` | String(32) | DEFAULT '' | 分类: grain/vegetable/fruit/flower/special/vip |
| `rarity` | String(16) | DEFAULT 'normal' | 品质: normal/fine/rare/legend |
| `growth_minutes` | Integer | DEFAULT 0 | 生长时间(分钟) |
| `level_required` | Integer | DEFAULT 1 | 种植所需等级 |
| `exp_reward` | Integer | DEFAULT 0 | 收获经验 |
| `seed_cost` | Integer | DEFAULT 0 | 种子价格(经验) |
| `profit` | Integer | DEFAULT 0 | 净收益 (exp_reward - seed_cost) |
| `ppm` | Double | DEFAULT 0.0 | 利润/分钟 |
| `double_cost` | Integer | DEFAULT 0 | 双倍道具成本 |
| `double_profit` | Integer | DEFAULT 0 | 双倍后净收益 |
| `double_ppm` | Double | DEFAULT 0.0 | 双倍后利润/分钟 |
| `is_vip` | Integer | DEFAULT 0 | VIP 专享: 1=是 |
| `updated_at` | DateTime(tz) | DEFAULT NOW() | 更新时间 |

---

## 8. config_definitions — 配置项定义

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `key` | String(64) | UNIQUE, NOT NULL | 配置键名 |
| `value_type` | String(16) | DEFAULT 'bool' | 值类型 |
| `default_value` | Text | DEFAULT '' | 默认值 |
| `description` | Text | DEFAULT '' | 说明 |
| `category` | String(32) | DEFAULT 'general' | 分类: battle/buff/supply/daily/ad/shop/role/social |
| `created_at` | DateTime(tz) | DEFAULT NOW() | 创建时间 |

种子数据 (27 条): tower_use_revive, exp_boost_enabled, supply_revive/challenge_book/flowers/beads, auto_checkin/chest/ad_stamina/farm/community, auto_shop_stamina/challenge_book, auto_npc_fight/tower/gang_boss/world_boss/tournament, auto_class_upgrade/upgrade/equip, auto_marriage_boss/gift/flowers/proposal, auto_friend_sync, auto_gang_donate

---

## 9. account_configs — 角色配置值

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE, NOT NULL | 角色ID |
| `config_key` | String(64) | NOT NULL | 配置键名 |
| `value` | Text | DEFAULT '' | 配置值 |
| `updated_at` | DateTime(tz) | DEFAULT NOW(), ON UPDATE | 更新时间 |

唯一约束: (`account_id`, `config_key`)

---

## 10. dungeon_configs — 副本开关

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE | 角色ID |
| `dungeon_type` | String(32) | | 副本类型 |
| `difficulty` | String(16) | DEFAULT 'normal' | 难度 |
| `enabled` | Boolean | DEFAULT True | 是否启用 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |
| `updated_at` | DateTime(tz) | DEFAULT NOW() | |

唯一约束: (`account_id`, `dungeon_type`, `difficulty`)

---

## 11. dungeon_strategies — 副本策略

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE | 角色ID |
| `name` | String(64) | | 策略名称 |
| `dungeon_type` | String(32) | | 副本类型 |
| `difficulty` | String(16) | DEFAULT 'normal' | 难度 |
| `use_revive` | Boolean | DEFAULT False | 使用复活 |
| `target_floor` | Integer | DEFAULT 0 | 目标层数 |
| `auto_repeat` | Boolean | DEFAULT False | 自动重复 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |

---

## 12. dungeon_templates — 副本模板

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE | 角色ID |
| `name` | String(64) | | 模板名称 |
| `strategy_ids` | JSONB | DEFAULT [] | 关联策略 ID 列表 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |

---

## 13. dungeon_history — 副本记录

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE | 角色ID |
| `dungeon_type` | String(32) | | 副本类型 |
| `difficulty` | String(16) | | 难度 |
| `floors_cleared` | Integer | DEFAULT 0 | 通关层数 |
| `exp_gained` | Integer | DEFAULT 0 | 获得经验 |
| `items_dropped` | JSONB | DEFAULT [] | 掉落物品 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |

---

## 14. dungeon_sessions — 副本会话

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `account_id` | String(12) | FK→accounts.id CASCADE, UNIQUE | 角色ID (每角色最多一个活跃会话) |
| `dungeon_type` | String(32) | | 副本类型 |
| `difficulty` | String(16) | | 难度 |
| `current_floor` | Integer | DEFAULT 1 | 当前层 |
| `status` | String(16) | DEFAULT 'idle' | idle/running/paused/done |
| `started_at` | DateTime(tz) | DEFAULT NOW() | |

唯一约束: (`account_id`)

---

## 15. auction_snapshots — 拍卖快照

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `batch_id` | String(32) | NULL | 批次ID |
| `snapshot_at` | DateTime(tz) | DEFAULT NOW() | 快照时间 |
| `item_id` | Text | DEFAULT '' | 物品ID |
| `name` | String(128) | DEFAULT '' | 物品名称 |
| `slot` | String(32) | DEFAULT '' | 装备槽位 |
| `quality` | String(16) | DEFAULT '' | 品质 |
| `item_level` | Integer | DEFAULT 0 | 物品等级 |
| `price` | Integer | DEFAULT 0 | 价格(经验) |
| `seller_name` | String(64) | DEFAULT '' | 卖家昵称 |
| `enhance_level` | Integer | DEFAULT 0 | 强化等级 |
| `growth_level` | Integer | DEFAULT 0 | 成长等级 |
| `class_required` | String(64) | DEFAULT '' | 职业要求 |
| `armor_type` | String(32) | DEFAULT '' | 护甲类型 |
| `set_info` | Text | NULL | 套装信息 JSON |
| `base_stats` | Text | NULL | 基础属性 JSON |
| `affixes` | Text | NULL | 词缀 JSON |
| `raw_data` | Text | NULL | 原始数据 JSON |

---

## 16. ai_conversations — AI 对话日志

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `user_id` | Integer | FK→users.id CASCADE | 用户ID |
| `username` | String(64) | DEFAULT '' | 用户名 |
| `account_id` | String(12) | NULL | 关联角色ID |
| `question` | Text | NOT NULL | 用户问题 |
| `answer` | Text | NULL | AI 回答 |
| `model` | String(32) | DEFAULT 'deepseek-v4-pro' | 模型 |
| `is_core_related` | SmallInteger | DEFAULT 0 | 核心相关 |
| `is_dangerous` | SmallInteger | DEFAULT 0 | 危险内容 |
| `is_strategy_matched` | SmallInteger | DEFAULT 0 | 策略匹配 |
| `satisfied` | SmallInteger | DEFAULT 0 | 满意度 |
| `tools_used` | Text | NULL | 使用的工具 JSON |
| `tools_data_size` | Integer | NULL | 工具数据大小 |
| `prompt_tokens` | Integer | NULL | Prompt tokens |
| `completion_tokens` | Integer | NULL | Completion tokens |
| `elapsed_ms` | Integer | NULL | 耗时(毫秒) |
| `from_cache` | Boolean | DEFAULT False | 是否缓存命中 |
| `tags` | Text | NULL | 标签 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |

---

## 17. ai_daily_summary — AI 日总结

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | Integer | PK, 自增 | |
| `date` | Date | NOT NULL | 统计日期 |
| `user_id` | Integer | FK→users.id CASCADE | 用户ID |
| `username` | String(64) | DEFAULT '' | 用户名 |
| `total_questions` | Integer | DEFAULT 0 | 总问题数 |
| `total_tokens` | Integer | DEFAULT 0 | 总 tokens |
| `total_elapsed_ms` | Integer | DEFAULT 0 | 总耗时 |
| `cache_hits` | Integer | DEFAULT 0 | 缓存命中数 |
| `core_related_count` | Integer | DEFAULT 0 | 核心相关数 |
| `core_related_rate` | Numeric(5,2) | DEFAULT 0 | 核心相关率 |
| `dangerous_count` | Integer | DEFAULT 0 | 危险内容数 |
| `strategy_matched_count` | Integer | DEFAULT 0 | 策略匹配数 |
| `strategy_matched_rate` | Numeric(5,2) | DEFAULT 0 | 策略匹配率 |
| `satisfied_count` | Integer | DEFAULT 0 | 满意数 |
| `satisfied_rate` | Numeric(5,2) | DEFAULT 0 | 满意率 |
| `tools_total_calls` | Integer | DEFAULT 0 | 工具调用总数 |
| `tools_top` | Text | NULL | 热门工具 TOP N |
| `top_tags` | Text | NULL | 热门标签 |
| `sample_questions` | Text | NULL | 抽样问题 |
| `created_at` | DateTime(tz) | DEFAULT NOW() | |

唯一约束: (`date`, `user_id`)
