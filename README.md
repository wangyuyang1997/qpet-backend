# Q宠乐斗 v5.0 Backend

Python FastAPI 后端，为 Q宠乐斗游戏提供自动化引擎和 API 服务。

## 技术栈

- Python 3.11+ / FastAPI / SQLAlchemy 2.0 + Alembic
- PostgreSQL / Redis / RabbitMQ
- APScheduler / JWT / ECDSA 签名

## 启动

```bash
cp backend/.env.example backend/.env   # 编辑配置
docker compose up -d                   # 一键启动全家桶
```

或手动启动后端：

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 3456
```

> 禁止 `--reload`，会导致双进程双倍连接池撑满 PG。

## 部署

Push `v5.0-dev` 分支即触发 GitHub Actions 自动构建镜像并部署到云服。

## 项目结构

```
backend/
├── app/
│   ├── main.py           # FastAPI 入口
│   ├── core/             # 基础设施 (DB/Redis/JWT)
│   ├── models/           # SQLAlchemy ORM
│   ├── routers/          # API 路由
│   └── services/         # 业务逻辑 + 游戏引擎
├── alembic/              # 数据库迁移
└── Dockerfile
```
