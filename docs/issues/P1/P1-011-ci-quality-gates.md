# P1-011：没有实际 CI 和质量门禁

- 状态：Closed（2026-07-23）
- 分类：持续集成 / 文档准确性
- 优先级：P1

## 已证实证据

- 仓库不存在 `.github/workflows` 或其他 CI 配置。
- `docs/VALIDATION.md:49` 写有“Docker Compose 的 YAML/构建文件已准备并由 CI
  覆盖构建步骤”，与仓库事实不符。
- 后端 pytest、前端 Vitest/TypeScript、Playwright、离线 smoke/rehearse 都只能
  由 README 中的手工命令触发；`web/playwright.config.ts` 虽读取 `CI`，没有 workflow
  注入它。

## 影响

主分支和 PR 可在未执行构建、测试、安全扫描或镜像检查的情况下合并；文档误导维护者
以为存在保护，P0/P1 修复无法持续防回归。

## 修复方案

1. 新增 GitHub Actions 最小工作流，分别运行：
   backend 安装与 pytest、web `npm ci`/unit test/lint/build、Playwright、
   `docker compose build`。
2. 使用最小权限 token、固定 action SHA/受信任版本、依赖缓存和产物保留策略。
3. 将安全扫描、依赖锁校验和秘密扫描接入必需检查；耗时 E2E 可分层但不可静默跳过。
4. 修正 `VALIDATION.md`，在 workflow 落地前明确“本机已验证、CI 待接入”。
5. 配置分支保护，要求成功检查、禁止直接绕过；发布工作流与 PR 工作流分权。

## 验收标准

- fork/PR/push 均可见可复现检查结果；故意破坏后端、前端或 Compose 构建会使对应 job 失败。
- 失败日志不打印 `.env`、环境密钥或测试凭据。
- 主分支保护要求核心 job 成功；文档链接到真实 workflow badge/运行记录。
- CI 上运行的测试矩阵、Node/Python 版本和缓存 key 有文档说明。

## 依赖

P1-012 的供应链检查与 P2-004 的安全回归用例应成为 workflow 的增量 job。不要以
“本地跑过”替代合并门禁。

## 修复记录

新增后端锁定依赖/pytest、前端 npm ci/lint/unit/build/Playwright、Compose build、SBOM、依赖审计和失败产物 CI job；增加 Dependabot。分支保护所需检查与禁止绕过已写入发布治理文档。
