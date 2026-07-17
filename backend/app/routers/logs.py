"""运行日志 API"""
from fastapi import APIRouter, Depends, Query
from app.core.auth_middleware import get_current_user
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def get_logs(
    account: str | None = Query(default=None),
    date: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=500),
    _user: dict = Depends(get_current_user),
):
    conditions = []
    params = {}

    if account:
        conditions.append("account = :account")
        params["account"] = account
    if category:
        conditions.append("category = :category")
        params["category"] = category
    if date:
        conditions.append("timestamp >= :d1 AND timestamp < :d2")
        params["d1"] = f"{date} 00:00:00"
        params["d2"] = f"{date} 23:59:59"

    where = " AND ".join(conditions)
    where_clause = f"WHERE {where}" if where else ""

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(f"SELECT timestamp, level, category, module, message, account "
                 f"FROM logs {where_clause} ORDER BY timestamp DESC LIMIT :limit"),
            {**params, "limit": limit},
        )
        raw = rows.fetchall()

    logs = [
        {
            "created_at": r[0],
            "level": r[1] or "INFO",
            "category": r[2] or "",
            "module": r[3] or "",
            "message": r[4] or "",
            "account_name": r[5] or "",
        }
        for r in raw
    ]

    return {"success": True, "data": logs, "logs": logs}


@router.get("/stats")
async def get_logs_stats(_user: dict = Depends(get_current_user)):
    from datetime import date
    today = date.today().isoformat()

    async with AsyncSessionLocal() as db:
        today_count = await db.execute(
            text("SELECT count(*) FROM logs WHERE timestamp >= :t1"),
            {"t1": f"{today} 00:00:00"},
        )
        total = await db.execute(text("SELECT count(*) FROM logs"))

    return {
        "success": True,
        "data": {
            "today": today_count.scalar() or 0,
            "history": total.scalar() or 0,
        },
    }
