# P1-001：会话口令留存与 CORS 策略过宽

- 状态：Closed（2026-07-23）
- 分类：会话安全 / 浏览器边界
- 优先级：P1

## 已证实证据

- `web/src/api.ts:38-49,62-69` 将活动口令写入 `sessionStorage`，且即使
  `/api/session` 已建立 HttpOnly Cookie，后续请求仍携带原始口令 Header。
- `backend/app/main.py:59` 使用 `allow_credentials=True`、`allow_methods=["*"]`
  和 `allow_headers=["*"]`；允许源由自由文本环境变量解析。
- `main.py:141-148` Cookie 是 HttpOnly/SameSite=Lax，但没有显式过期、登出或
  会话撤销模型。

## 影响

任意 XSS 能读取并长期复用口令；配置错误的 CORS 源、方法或 Header 会放大跨站攻击面。
共享口令本身不是用户身份，因此不能用 Cookie 的存在替代授权设计。

## 修复方案

1. 口令验证成功并收到 Cookie 后立即清除内存和 `sessionStorage` 中的原始口令；
   之后只使用 Cookie。错误口令也不得保留。
2. 将 CORS 改为环境校验后的精确源、最小方法集合和最小 Header 集合；production
   禁止 `*`、HTTP 源和意外端口。
3. 定义受控会话生命周期：签名/服务端会话 ID、TTL、显式登出与口令轮换失效。
4. 对 Cookie 认证的变更请求评估 CSRF 防护；若跨站嵌入确有需求，使用 CSRF token
   而不是降低 SameSite。

## 验收标准

- 浏览器完成登录后，`sessionStorage`、localStorage 和请求 Header 均没有原始口令。
- 生产配置使用未批准 CORS 源或通配符时启动失败。
- 会话过期、登出、口令轮换、跨源写请求和 SSE 重连都有自动化测试。
- 日志与错误响应不输出 Cookie、Header 或口令内容。

## 依赖与观测

该 issue 不能代替 P0-002 的角色授权。新增指标应只统计会话创建、过期、登出和 CORS
拒绝数量；审计事件可记录匿名会话/调用者类型，不得记录凭据。

## 修复记录

服务端随机会话已具备 TTL、撤销和角色隔离；口令只用于会话交换。前端不存储口令，写操作校验 CSRF，CORS 使用启动期验证的精确白名单。复测：后端会话/CSRF 测试和完整 pytest。
