# 邀请币商店

## 基本规则

- 独立于主站经验的另一套货币体系
- 通过邀请好友获得邀请币
- 可兑换装备、道具等物品

## 相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/user/invite-coins/balance | 邀请币余额 |
| GET | /api/user/invite-coins/logs?page=N&limit=N | 邀请币日志 |
| GET | /api/invite-coin-shop/items | 商品列表 |
| GET | /api/invite-coin-shop/equipment-options | 装备选项 |
| POST | /api/invite-coin-shop/purchase | 购买 |
