# ADR-005：SSE 优先，持久化事件回放

背景：操作端和大屏只需要服务端向浏览器单向推送领域事件。

选择：`demo_events` 账本按 event id 持久化，SSE 以 cursor 重放；断线后前端保留当前画面并用 snapshot 重同步。

后果：单机没有 Redis 依赖，重连可恢复状态。

回退：多实例时将事件发布替换为 Redis Stream，保留服务接口。
