# P1-003：反向代理安全基线和 SSE 存活机制缺失

- 状态：Closed（2026-07-23）
- 分类：边界防护 / 实时连接可靠性
- 优先级：P1

## 已证实证据

- `nginx.conf` 只有基础反代和 `proxy_buffering off`，没有 Content-Security-Policy、
  `X-Content-Type-Options`、点击劫持防护、TLS/HSTS 策略或显式代理超时。
- `backend/app/main.py:215-223` 在无事件时仅 `sleep(0.5)`，不会发送 SSE heartbeat。
- 常见 Nginx `proxy_read_timeout` 默认值会在长时间无数据时关闭连接；当前配置没有覆盖，
  该项需在目标镜像/代理链中实测确认。

## 影响

缺少安全头会扩大 XSS、点击劫持和内容嗅探风险；SSE 空闲断连会触发 P1-008 的全量重放，
造成大屏频繁“实时同步断开”和请求尖峰。

## 修复方案

1. 制定 Nginx 安全基线：TLS 由受信任入口终止、明确 HSTS 适用范围、CSP nonce/哈希
   策略、`nosniff`、`frame-ancestors`、Referrer-Policy 和最小缓存规则。
2. 为 `/api/cases/*/events` 配置足够长的读写超时、禁用缓冲、合理 keepalive，
   并限制单连接与总连接数。
3. 服务端在空闲周期发送 SSE comment/heartbeat，客户端识别心跳但不刷新快照。
4. 明确并验证 `X-Forwarded-*` 的可信代理边界，禁止客户端伪造后被应用当成真实来源。

## 验收标准

- 生产响应通过安全头基线检查，CSP 不破坏 Vite 构建产物与 EventSource。
- 在预期空闲时长后，SSE 仍保持连接或以可恢复游标重连；测试覆盖 Nginx 实际配置。
- 浏览器、Nginx 与 API 日志可关联连接建立、心跳、关闭原因和重连次数，不含正文。

## 依赖

安全头必须先与前端资源、第三方图片和部署入口核对，不能盲目启用 HSTS。SSE 重放修复
见 P1-008；流量配额见 P1-004。

## 修复记录

Nginx 增加 CSP、nosniff、反点击劫持、最小权限策略、请求体上限和 SSE 专用超时/禁缓冲；API 增加可配置 heartbeat，且不再信任客户端 forwarded headers。TLS/HSTS 入口责任已写入 runbook。
