# ADR-002：公告板使用副本而非改变原卡可见性

背景：必须向观众证明共享是显式、可审计且可追溯的操作。

选择：复制原文到 `bulletin_board`，记录 `source_agent_id` 与 `source_memory_id`。

后果：私有原件永不消失；重复公开按源卡幂等。

回退：P4 才能在独立 Gateway 中试验原生 share_memory。
