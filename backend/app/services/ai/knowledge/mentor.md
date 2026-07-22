# 师徒系统

## 基本规则

- 收徒上限：5名
- 生命加成：每收1名徒弟 +10 生命，最多计2名（上限 +20 生命）
- 收徒条件：须先在普通乐斗中打败对方，才能发出收徒邀请
- 叛逃师门：主动断绝师徒后，7天内不能拜师

## 师徒乐斗

- 每日1次
- 经验 ×1.5 倍
- 师傅驾到技能：危急时刻师傅助力，恢复生命 + 下次攻击必中

## 相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/qpet/social/mentor/status | 师徒状态 |
| POST | /api/qpet/social/mentor/recruit | 招募徒弟 |
| POST | /api/qpet/social/mentor/respond | 回应招募 |
| POST | /api/qpet/social/mentor/dissolve | 断绝师徒 |
| POST | /api/qpet/social/mentor/fight/prepare | 师徒战斗准备 |
| POST | /api/qpet/social/mentor/fight/settle | 师徒战斗结算 |
