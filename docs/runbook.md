# 现场故障手册

| 现象 | 操作 | 主持人话术 |
|---|---|---|
| LLM 黄灯 | 保持 `DEMO_MODE=degrade`，继续剧本 A | “现在我们只看真实检索结果，隔离依然成立。” |
| API 未就绪 | 查看 `GET /api/healthz` 的 seekdb/PowerMem 项，修正 `.env` 后重启 api | “我们换一份新档案继续。” |
| 大屏没更新 | 刷新 `/stage/<case_id>`；页面会读取 snapshot 并重新订阅 SSE | “公告板以案件记录为准，画面正在同步。” |
| 重复公开 | 不需处理；返回原公告板副本且不会新增卡片 | “同一条情报只会登记一次。” |
| 网络或 LLM 不可用 | 切换/保持 degrade；不要在现场改隔离规则 | “这个演示的核心不依赖云端回答。” |

## 活动后清理

先 dry run，只读取本地账本中的案件数和同一 case 作用域内的 PowerMem 卡片数：

```powershell
cd docs/my/demo/ai_intel_bureau/backend
python -m app.clear_demo_data
```

确认输出无误后，下面的命令会先删除远端或嵌入式 PowerMem/SeekDB 中同一批 case 的卡片，再清空本地案件、事件和会话账本。远端删除失败时，账本会保留以便安全重试：

```powershell
python -m app.clear_demo_data --confirm
```

只有明确要保留远端卡片时，才使用 `--confirm --local-only`。
