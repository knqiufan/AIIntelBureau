# P1-012：依赖供应链与容器构建加固不足

- 状态：Closed（2026-07-23）
- 分类：软件供应链 / 容器安全
- 优先级：P1

## 已证实证据

- `backend/requirements.lock` 仅固定直接依赖；`backend/Dockerfile:6-8`
  先 `pip install .` 再安装该文件，未固定传递依赖或 hash。
- `web/package.json` 使用 `^` 版本，虽有 `package-lock.json`，但没有 audit、
  SBOM、许可证或自动更新治理。
- 无 `.dockerignore`；Docker build context 会携带 `.env`、Git 元数据和日志，
  即使当前 Dockerfile 没有 `COPY .`。
- Dockerfile 使用浮动基础镜像标签，未设非 root `USER`；Compose 的 `deploy.resources`
  在普通 Compose 下可能不生效。

## 影响

依赖解析和基础镜像可随时间漂移，难以复现或审计；未来 Dockerfile 改动可能把敏感上下文
写入镜像层；默认 root 进程扩大容器逃逸后的影响。

## 修复方案

1. 采用 `uv lock`/`pip-tools` 等生成全传递依赖与 hash 的 Python 锁文件，CI 验证
   `pyproject` 和 lock 同步；前端始终使用 `npm ci`。
2. 增加 Dependabot/Renovate、`pip-audit`/OSV、`npm audit`、许可证策略与
   CycloneDX/SPDX SBOM 生成。
3. 新增 `.dockerignore`，排除 `.env`、`.git`、日志、数据、node_modules、测试结果；
   用镜像构建测试证明敏感文件不可见。
4. 以 digest 固定基础镜像，创建最小权限用户，添加只读文件系统/capability 限制，
   并通过 Trivy/Grype 扫描。

## 验收标准

- 干净环境两次构建得到相同依赖树；未更新锁文件的依赖变更被 CI 拒绝。
- release 产物附带 SBOM、许可证报告和漏洞扫描结果；Critical 风险有明确阻断规则。
- 镜像内不存在 `.env`、Git 目录、运行日志和构建工具链；运行进程不是 root。
- 部署文档明确 Compose 与 Swarm 资源限制语义差异。

## 注意

扫描结果会随漏洞数据库变化；报告需注明扫描时间、工具版本和豁免期限，不能把一次
“零漏洞”结果当作永久安全保证。

## 修复记录

`requirements.lock` 现含 156 个传递依赖和哈希，Docker/CI 强制校验；npm 使用 `npm ci`。Python/Node/Nginx 镜像固定为官方 digest，后端非 root，`.dockerignore` 排除敏感构建上下文，CI 生成 SBOM 和 audit 结果。
