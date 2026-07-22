# 称号系统

## 基本规则

- 称号提供属性加成和战力评分
- 12 生肖主题称号可合成
- 无称号战力分 = 0，普通称号 = 420，至尊称号 = 1300

## 战力评分

| 称号等级 | 战力分 |
|---------|--------|
| 无称号 | 0 |
| 普通 | 420 |
| 至尊 | 1300 |

## 相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/user/titles | 称号列表 |
| GET | /api/user/titles/equipped | 当前佩戴称号 |
| POST | /api/qpet/equipment/title/equip | 穿戴称号 |
| POST | /api/qpet/equipment/title/unequip | 卸下称号 |
| POST | /api/qpet/equipment/title/synthesize | 称号合成 |
