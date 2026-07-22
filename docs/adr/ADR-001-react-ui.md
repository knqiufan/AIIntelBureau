# ADR-001：React 作为正式 UI

背景：需要操作端与 1080p 只读大屏同步展示事件证据。

选择：React + TypeScript + Vite；HTTP/SSE 是唯一后端通道。

后果：可控布局、键盘访问与双端状态恢复；前端不实现任何记忆可见性规则。

回退：P0/P1 API 与 smoke 工具仍可独立演示。
