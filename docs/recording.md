# 离线录屏

此录屏完全使用本地 in-memory 后端和确定性证据模式；不需要 SeekDB、PowerMem Server 或 LLM 凭据。

```powershell
cd docs/my/demo/ai_intel_bureau/web
npm run record:demo
```

命令会运行“加载 A 剧本 → 侦探空命中 → 线人私有命中 → 显式公开 → 侦探只命中公告栏副本”的四幕流程，并把 WebM 输出到 `web/test-results/`。该目录已被 Git 忽略，方便主持人在离线现场播放或重新录制，不会把临时录像、密钥或浏览器状态提交进仓库。

录制前可设置 `VITE_DEMO_DATA_SOURCE=mock` 以只使用 P1 JSON fixture；默认 `api` 则由该脚本自行启动内存后端，验证真实 HTTP 与 SSE 集成。
