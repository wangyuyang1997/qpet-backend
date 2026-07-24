#!/bin/bash
# v5.0 后端启动脚本 — 单进程，禁止 reload 避免双倍连接池
cd "$(dirname "$0")/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 3456
