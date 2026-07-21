"""油猴脚本服务 — 提供最新的 Q宠乐斗辅助脚本"""
import os
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from app.core.auth_middleware import get_current_user

router = APIRouter(prefix="/api/tampermonkey", tags=["tampermonkey"])

# 脚本存放路径（与 main-server 共用同一份 user.js）
# routers → app → backend → qpet-backend → duanwuqiufenmao → main-server/
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                           "main-server", "qpet-sso-helper.user.js")


@router.get("/script")
async def get_script(_user: dict = Depends(get_current_user)):
    """返回油猴脚本（来自 main-server/qpet-sso-helper.user.js）"""
    try:
        abs_path = os.path.abspath(SCRIPT_PATH)
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = '// 脚本文件未找到，请联系管理员'
    return Response(
        content=content,
        media_type="application/javascript; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=qpet-sso-helper.user.js"},
    )
