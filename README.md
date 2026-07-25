# Q宠乐斗 v5.0 Backend

为 [duanwuqiufenmao.top](https://duanwuqiufenmao.top) 的 Q宠乐斗和农场游戏提供自动化引擎和 RESTful API 的后端服务。

## 这是什么

这是一个游戏自动化后端，托管多个游戏账号，通过调用游戏 API 实现自动挂机：

- **乐斗自动化**：自动 NPC/好友对战、爬塔、帮派 BOSS、秘境副本、世界 BOSS
- **农场自动化**：自动播种/收获/翻地/偷菜/浇水/升级土地
- **婚姻自动化**：已婚送花+夫妻 BOSS，未婚送花求婚一条龙
- **智能军师**：装备评分推荐、技能加点方案、拍卖行比价
- **AI 助手小黑羊**：基于 DeepSeek 的对话式游戏咨询
- **Web Dashboard**：实时状态面板、日志流、配置管理、用户系统

## 技术栈

| 层 | 技术 |
|----|------|
| 框架 | Python 3.12+ / FastAPI |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 消息队列 | RabbitMQ |
| 定时调度 | APScheduler |
| 认证 | JWT + ECDSA P-256 签名 |
| AI | DeepSeek API / SSE 流式响应 |
| 部署 | Docker Compose + GitHub Actions |

## 项目结构

```
backend/
├── app/
│   ├── main.py               # FastAPI 入口（生命周期/中间件/路由注册）
│   ├── config.py              # 配置管理（环境变量 + .env）
│   │
│   ├── core/                  # 基础设施层
│   │   ├── database.py        # SQLAlchemy async engine + session
│   │   ├── redis.py           # Redis 连接池（缓存/分布式锁）
│   │   ├── rabbitmq.py        # RabbitMQ 生产者/消费者
│   │   ├── auth_middleware.py # JWT 认证中间件
│   │   ├── crypto.py          # AES-256-GCM 加解密
│   │   ├── security.py        # 密码哈希/Token 生成
│   │   └── logger.py          # 结构化日志
│   │
│   ├── models/                # SQLAlchemy ORM（15+ 张表）
│   │   ├── account.py         # 账号表
│   │   ├── daily_record.py    # 每日统计
│   │   ├── log.py             # 操作日志
│   │   ├── user.py            # 用户系统
│   │   ├── config_definition.py  # 功能配置定义
│   │   ├── auction_snapshot.py   # 拍卖行快照
│   │   ├── gang_*.py          # 帮派相关（5 张表）
│   │   └── ...                # 农场/背包/博物馆等
│   │
│   ├── schemas/               # Pydantic 请求/响应模型
│   │
│   ├── routers/               # API 路由层（薄）
│   │   ├── accounts.py        # 账号管理 CRUD
│   │   ├── auth.py            # 登录/注册
│   │   ├── config.py          # 配置读写
│   │   ├── ai.py              # AI 对话
│   │   ├── logs.py            # 日志查询
│   │   ├── auction.py         # 拍卖数据
│   │   ├── preload.py         # 首页预加载
│   │   └── tampermonkey.js    # 辅助脚本代理
│   │
│   └── services/              # 业务逻辑层
│       ├── engine.py          # 核心引擎（循环调度）
│       ├── engine_account.py  # 单账号引擎实例
│       ├── scheduler.py       # 定时任务管理
│       ├── auth.py            # 游戏 API 认证
│       ├── inventory.py       # 通用道具层
│       ├── supply.py          # 背包补给检测
│       ├── shop.py            # 商店自动购买
│       ├── farm/              # 农场模块
│       ├── marriage/          # 婚姻模块
│       ├── gang/              # 帮派模块
│       └── service_*.py       # 各游戏模块
│
├── alembic/                   # 数据库迁移
│   └── versions/
│
├── Dockerfile                 # 多阶段构建
├── pyproject.toml
└── start.sh                   # 启动脚本
```

## 引擎架构

每个账号独立 Engine 实例，互不干扰：

```
Scheduler（全局调度器）
  ├── AccountManager（账号生命周期）
  │   ├── Engine #1（账号 A）
  │   │   └── 循环：farm → shop → marriage → fight → tower → gang → class → ...
  │   ├── Engine #2（账号 B）
  │   └── Engine #3（账号 C）
  └── 定时任务
      ├── 拍卖行快照（每小时）
      ├── AI 日报（凌晨）
      └── 数据库维护
```

引擎循环（`fullAutoCycle`）每 30 分钟执行一次完整周期，农场有独立的 15 秒快速轮询。

## 设计决策

1. **分层架构**：routers(薄) → schemas(校验) → services(业务) → models(ORM) → core(基础设施)，每层只依赖下层
2. **引擎隔离**：每账号独立 Engine 实例，解决旧版多账号互斥问题
3. **连接池控制**：禁止 `--reload` 启动（双进程双倍连接池撑爆 PG）
4. **Redis 缓存**：游戏 API 响应缓存 30-600s，减少重复请求
5. **婚姻两套逻辑**：已婚=送花 5 次/天+大色魔，未婚=送花 10 次/天+100 亲密度求婚
6. **道具系统**：通用 inventory.py 层，各业务模块按需调用

## 启动方式

```bash
# 本地开发
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 3456

# 生产（Docker）
docker compose up -d backend
```

> **禁止加 `--reload`**，原因见设计决策第 3 条。

## 部署

Push 到 `master` 分支触发 GitHub Actions 自动部署到京东云服务器。

详见 [v5-deploy-github-actions.md](../duanwuqiufenmao/docs/v5-deploy-github-actions.md)。
