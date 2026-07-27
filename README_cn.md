# LitMonitor 中文说明

LitMonitor 是一个面向科研人员的个人生物医学文献监控工具。它把 PubMed 检索、固定主题周报、论文去重、相关性评分、LLM 摘要、邮件推送、Web 页面和结构化报告生成整合到一个本地项目里。

当前项目适合作为单用户本地服务使用。如果要通过 Cloudflare Tunnel、反向代理或公网域名暴露访问，必须额外配置访问控制，例如 Cloudflare Access、Zero Trust、邮箱登录或其他认证层。

## 项目目的

这个项目的目标是减少重复的文献检索和人工筛选工作：

- 定期监控你关心的研究方向，例如单细胞、空间组学、肺部疾病、菌群、肺动脉高压、数据分析等。
- 从 PubMed 获取文献并保存到本地 SQLite 数据库。
- 对论文做去重、关键词匹配和相关性评分。
- 只对真正会进入邮件 digest 的论文调用 LLM，减少 token 浪费。
- 通过 QQ 邮箱或其他 SMTP 服务推送周报。
- 支持 DeepSeek、Z.AI/GLM、OpenAI-compatible API 和本地 Codex CLI 作为 LLM 后端。
- 支持单篇论文 digest 和高影响期刊 weekly report，输出结构化 `json`、`md`、`tsv` 和 `manifest.json`。

## 服务组成

项目主要包含这些服务层：

- `PubMed 检索服务`：根据关键词、期刊和时间范围检索 PubMed。
- `Profile 周报服务`：保存长期监控任务，例如每周监控肺动脉高压方向。
- `数据库服务`：使用 SQLite 保存 profile、论文、检索结果、LLM 分析和邮件 digest。
- `LLM 分析服务`：对入选邮件的论文生成摘要、方法、发现、局限性和相关性说明。
- `邮件服务`：通过 SMTP 发送 HTML/TXT digest。
- `调度服务`：Web 服务启动后可每天检查 weekly profile，满足条件时自动运行。
- `Web UI`：提供本地浏览器界面，用于搜索、查看 profile、论文和 digest。
- `报告服务`：嵌入 Bioinfor-Claw 的单篇 digest 和 high-impact weekly report 能力，统一输出到 `data/reports/...`。

## 安装

先安装 Pixi：

```bash
# 参考官方安装方式
# https://pixi.sh/latest/
```

然后在项目目录执行：

```bash
pixi install
cp .env.example .env
pixi run lit init-db
```

常用检查命令：

```bash
pixi run test
pixi run lint
pixi run lit --help
```

## 如何配置

所有密钥都应写入 `.env` 或服务器环境变量，不要提交到 Git。不要提交 SMTP 授权码、LLM API key、NCBI API key、Cloudflare 凭据、SQLite 数据库和日志文件。

基础配置示例：

```env
DATABASE_URL=sqlite:///./data/litmonitor.db
NCBI_API_KEY=

APP_HOST=127.0.0.1
APP_PORT=8000
DEFAULT_TIMEZONE=America/Chicago
SCHEDULER_ENABLED=true
```

### QQ 邮箱 SMTP

QQ 邮箱建议使用完整邮箱地址作为用户名，SMTP 授权码作为密码，SSL 端口 `465`：

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your@qq.com
SMTP_PASSWORD=your_smtp_authorization_code
SMTP_FROM=your@qq.com
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

其他 SMTP 服务通常使用：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_user
SMTP_PASSWORD=your_password
SMTP_FROM=litmonitor@example.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

### DeepSeek LLM

当前推荐 DeepSeek 配置：

```env
LLM_ENABLED=true
LLM_BACKEND=openai-compatible
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-v4-pro
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=0
LLM_THINKING_TYPE=enabled
LLM_REASONING_EFFORT=high
LLM_STREAM=false
LLM_TIMEOUT_SECONDS=120
LLM_FORCE_JSON_MODE=false
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=10
LLM_FALLBACK_BACKEND=cli
```

`LLM_FALLBACK_BACKEND=cli` 表示 DeepSeek 失败或限流时，自动尝试本地 Codex CLI。

### Z.AI / GLM

```env
LLM_ENABLED=true
LLM_BACKEND=openai-compatible
LLM_API_BASE=https://api.z.ai/api/paas/v4
LLM_API_KEY=your_glm_key
LLM_MODEL=glm-5.1
LLM_TEMPERATURE=1.0
LLM_MAX_TOKENS=4096
LLM_THINKING_TYPE=enabled
LLM_REASONING_EFFORT=
LLM_STREAM=false
LLM_FORCE_JSON_MODE=false
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=30
LLM_FALLBACK_BACKEND=cli
```

### 本地 Codex CLI

```env
LLM_ENABLED=true
LLM_BACKEND=cli
LLM_CLI_COMMAND=codex
LLM_CLI_ARGS=exec --json
LLM_CLI_TIMEOUT_SECONDS=120
```

本地 CLI 后端会把 prompt 发送给 `codex`，并解析 JSON 或 Codex JSONL 事件流中的 `agent_message`。

## Web 服务

启动开发服务：

```bash
pixi run web
```

生产风格本地服务：

```bash
pixi run web-prod
```

默认访问地址：

```text
http://127.0.0.1:8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

如果服务运行在远程服务器，浏览器打开本机的 `127.0.0.1:8000` 不会访问远程服务。可以使用：

- VS Code / SSH 端口转发
- SSH tunnel：`ssh -L 8000:127.0.0.1:8000 user@server`
- Cloudflare Tunnel，例如 `litmonitor.example.com -> http://127.0.0.1:8000`

## CLI 功能使用

初始化数据库：

```bash
pixi run lit init-db
```

查看命令：

```bash
pixi run lit --help
```

### 手动搜索 PubMed

```bash
pixi run lit search "pulmonary hypertension endothelial single-cell" --since 30d
```

限制期刊：

```bash
pixi run lit search "pulmonary hypertension endothelial" \
  --journal "Nature Medicine" \
  --journal "Circulation" \
  --since 30d
```

搜索结果会写入本地数据库。

### 创建 weekly profile

profile 是一个长期监控任务。示例：肺动脉高压方向，不限制期刊。

```bash
pixi run lit profile add \
  --name "Pulmonary arterial hypertension weekly" \
  --include "pulmonary arterial hypertension" \
  --include "pulmonary hypertension" \
  --include "PAH" \
  --include "right ventricular" \
  --include "vascular remodeling" \
  --include "endothelial" \
  --include "smooth muscle" \
  --exclude "case report" \
  --exclude "editorial" \
  --exclude "letter" \
  --schedule weekly \
  --email your@qq.com \
  --date-window 7d \
  --min-relevance-score 5 \
  --llm-enabled
```

查看 profile：

```bash
pixi run lit profile list
```

运行 profile：

```bash
pixi run lit profile run "Pulmonary arterial hypertension weekly"
```

运行并发送邮件：

```bash
pixi run lit profile run "Pulmonary arterial hypertension weekly" --send-email
```

运行、LLM 分析并发送邮件：

```bash
pixi run lit profile run "Pulmonary arterial hypertension weekly" --use-llm --send-email
```

注意：项目现在只对会进入邮件 digest 的论文调用 LLM，也就是本次新论文且达到 profile 的 `min_relevance_score`，避免对全部检索结果浪费 token。`DIGEST_MAX_PAPERS_PER_RUN=20` 用于控制每封周报最多包含 20 篇论文。

### 查看和补发 digest

预览最新 digest：

```bash
pixi run lit digest preview --profile "Pulmonary arterial hypertension weekly"
```

重新发送最新 digest：

```bash
pixi run lit digest send --profile "Pulmonary arterial hypertension weekly"
```

### 单篇论文 LLM 分析

按 PMID：

```bash
pixi run lit analyze-paper --pmid 42020743 --profile "Pulmonary arterial hypertension weekly"
```

按数据库 paper id：

```bash
pixi run lit analyze-paper --paper-id 1 --llm-backend openai-compatible
```

使用本地 Codex：

```bash
pixi run lit analyze-paper --paper-id 1 --llm-backend cli
```

### 导出文献

CSV：

```bash
pixi run lit export --profile "Pulmonary arterial hypertension weekly" --format csv
```

BibTeX：

```bash
pixi run lit export --profile "Pulmonary arterial hypertension weekly" --format bibtex
```

## 报告功能

项目已经嵌入 Bioinfor-Claw 中两个模块的核心能力：

- `paper-digest-single`：单篇论文 digest。
- `big-papers-weekly-report`：高影响期刊 weekly report。

输出默认写入：

```text
data/reports/...
```

每个报告目录会包含 `manifest.json`，方便 Web/API 或其他脚本读取。

### 单篇论文 digest

按 PMID：

```bash
pixi run lit paper digest --pmid 42020743 --topic-keyword single-cell --topic-keyword lung
```

按 DOI：

```bash
pixi run lit paper digest --doi 10.1038/s41586-026-10399-6 --output-format json
```

按已入库 paper id：

```bash
pixi run lit paper digest --paper-id 1 --output-dir data/reports/paper-digests/example
```

支持输出格式：

- `markdown`
- `json`
- `txt`

典型输出：

```text
paper_metadata_<ID>.json
paper_digest_<ID>.json
paper_digest_<ID>.md
extraction_log_<ID>.txt
manifest.json
```

### 高影响期刊 weekly report

使用默认高影响期刊范围：

```bash
pixi run lit report weekly-big \
  --date-from 2026-04-19 \
  --date-to 2026-04-26 \
  --interest-keyword single-cell \
  --interest-keyword spatial \
  --interest-keyword pulmonary
```

指定期刊：

```bash
pixi run lit report weekly-big \
  --journal "Nature" \
  --journal "Science" \
  --journal "Cell" \
  --interest-keyword "pulmonary hypertension" \
  --top-n 20
```

典型输出：

```text
weekly_big_papers.tsv
weekly_big_papers.json
weekly_big_papers.md
manifest.json
```

## 调度行为

当 `.env` 中设置：

```env
SCHEDULER_ENABLED=true
```

Web 服务启动时会创建后台调度器。调度器每天检查一次 weekly profile：

- 如果最近 7 天没有成功 run，会执行新的检索、digest 和邮件发送。
- 如果最近 run 已成功但 digest 发送失败或仍是 draft，会优先重试邮件发送。

## 数据和输出目录

常用目录：

```text
data/litmonitor.db        SQLite 数据库
data/reports/             单篇 digest 和 weekly report 输出
src/litmonitor/templates/ 邮件模板
src/litmonitor/web/       Web UI
```

建议不要提交：

- `.env`
- `data/litmonitor.db`
- `data/reports/`
- SMTP 授权码
- LLM API key
- Cloudflare 凭据

## 常见问题

### 收不到邮件

优先检查：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

QQ 邮箱应使用授权码，不是 QQ 登录密码。

### 邮件里 LLM summary 是 not available

常见原因：

- LLM API key 错误。
- base URL 或 model 不匹配。
- API 限流，例如 HTTP 429。
- 本地 Codex CLI 不可用或输出无法解析。

项目会记录失败原因到数据库中的 LLM 分析记录。配置 `LLM_FALLBACK_BACKEND=cli` 可以在远端模型失败时尝试本地 Codex。

### 为什么不分析全部 100 篇检索结果

这是有意设计。LLM 只分析最终会进入邮件 digest 的论文，避免浪费 token。

### 报告里的结论能否直接作为系统综述

不能。当前 digest 和 weekly report 主要基于标题、摘要和元数据做结构化整理，不等同于全文精读、系统综述或 meta-analysis。

## 推荐工作流

1. 配置 `.env`：SMTP、DeepSeek 或其他 LLM、NCBI API key。
2. 初始化数据库：`pixi run lit init-db`。
3. 创建 weekly profile。
4. 手动运行一次：`pixi run lit profile run "<profile>" --use-llm --send-email`。
5. 确认邮件和 LLM summary 正常。
6. 启动 Web 服务并开启 `SCHEDULER_ENABLED=true`。
7. 按需生成单篇 digest 或 high-impact weekly report。
