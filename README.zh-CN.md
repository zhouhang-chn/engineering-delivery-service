# Engineering Delivery Service (EDS)

[English](README.md) · **简体中文**

一个自主工程交付服务。它通过 A2A 接收一个 **Engineering Work
Order（工程工作单）**——而不是一段 coding prompt——并自主推进：

```
需求 → 开发 → 测试 → 检查 → 部署 → 验收
```

调用方只需要说"开发并部署这个 API"，就能拿回一个可运行的服务：
人工打开它的 `/docs`（Swagger UI），"Try it out" 即可验证——全程
无需接触 worker 线程、沙箱、重试或检查循环。

首个发布范围：**FastAPI API 开发与部署**——单一仓库、明确的验收
标准、容器化测试部署。完整设计见
[架构源草案](docs/refer/engineering-delivery-service-architecture.md)（中文）
与[设计文档集](docs/designs/README.md)（英文）。

## 设计

最上层控制器是一个自由运行的 **ReAct Supervisor**（Google ADK）。
确定性的 **Delivery Control Tools（交付控制工具）** 基于持久的
**PostgreSQL** 工作单状态提供可靠动作。**Worker** 与 **Inspector**
是各自沙箱中的完整 Codex App Server 运行时：Worker 产出候选
commit；Inspector 依据验收标准独立验证并返回 ACCEPT / REJECT。
交付循环由 Supervisor 掌控。

![EDS 架构总览](docs/eds-arch.png)

同一架构的文本版：

```
              External Agent / Platform / User
                              │ A2A
                              ▼
               Engineering Delivery Agent
               (ReAct Supervisor, Google ADK)
                              │
                reason → tool → observe
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
 Delivery Control       Worker Runtime        Inspector Runtime
 (tools + durable       (Codex App Server,    (Codex App Server,
  PostgreSQL state)      writable sandbox)     clean sandbox)
        │                     │ candidate           │ verdict
        └─────────────────────┼─────────────────────┘
                              ▼
                      Deployment Runtime
                              ▼
                       FastAPI `/docs`
```

四条原则支配整个系统：

> **Supervisor 掌控交付。Delivery Control 提供确定性的状态与
> 动作。Worker 产出候选。Inspector 确立事实。**

其背后刻意的设计判断：

- **顶层没有 workflow 层。** 没有一条确定性流水线决定下一步发生
  什么。最高控制层是 Supervisor 的 observe → reason → act 循环；
  确定性代码只提供可靠的动作与状态。"现在该开发、重新检查还是
  部署？"这类判断属于 Supervisor。
- **A2A Task ≈ Engineering Work Order，而不是一次 Codex turn。**
  外部契约是一整个交付：任何 A2A 兼容的调用方都可以提交一个
  工作单并轮询到 `completed`，拿到 artifacts：repository@commit、
  部署 URL、`/docs` URL、测试证据、交付摘要。
- **没有人给自己的作业打分。** Worker 的 `done` 只表示候选已准备
  好接受检查。Inspector 基于独立 checkout 工作，看不到 Worker 的
  推理历史，可以带着证据 REJECT；证据再作为修复任务回流给
  Worker。
- **持久状态优先于对话记忆。** 工作单、证据与审计轨迹都保存在
  PostgreSQL 里；Supervisor 每一轮重新读取状态，而不是信任聊天
  历史。
- **人通过产品本身验收。** 验收底线就是交付出来的 API 本身——
  打开 `/docs`、"Try it out"、执行——因此不需要额外的前端或
  仪表盘来验证一次交付。

## 路线图

每个里程碑都保持
`需求 → 开发 → 测试 → 部署 → /docs` 全链路可运行；后续里程碑增加
的是自主性与可靠性，而不是补齐链路（详见
[docs/milestones.md](docs/milestones.md)，英文）：

| 版本 | 里程碑 | 新增能力 | 状态 |
|---|---|---|---|
| v0.1 | Single Worker End-to-End | 最小闭环：A2A → Supervisor → Worker → pytest → Docker 部署 → 可访问的 `/docs` | ✅ 已完成 |
| v0.2 | Durable Delivery Control | 重启恢复——工作单在服务重启后存活并继续；交付排队 | 计划中 |
| v0.3 | Independent Inspector | 设计中的验证环节：独立 checkout、ACCEPT / REJECT、反馈驱动的修复循环 | 计划中 |
| v0.4 | Requirement Confirmation + HITL | 预先确认需求与验收标准；歧义通过 A2A `input-required` 澄清 | 计划中 |
| v0.5 | Project-aware API Delivery | 走出模板仓库：项目注册、仓库解析、worktree、PR 交付 | 计划中 |
| v0.6 | Recoverable Autonomous Delivery | 崩溃/重试/恢复/回滚、有界自主、升级给人工 | 计划中 |

## 快速体验

完整闭环可离线运行——不需要 LLM 凭证，不需要 Codex 登录（只需要
[uv](https://docs.astral.sh/uv/) 与 Docker 守护进程）：

```bash
uv sync
docker compose up -d postgres && uv run alembic upgrade head

# 终端 1 —— 以确定性 demo 模式启动 EDS：
EDS_SUPERVISOR_BACKEND=deterministic \
EDS_WORKER_SCRIPT=examples/scripted_worker_hello.json \
uv run eds serve

# 终端 2 —— 提交一个需求并观看它交付：
uv run eds submit "Add a GET /hello endpoint returning {'hello': 'world'}"
uv run eds status wo-<id> --watch
uv run eds open wo-<id>    # 打开交付出来的 Swagger UI
```

若要使用真实 LLM Supervisor 与真实 Codex Worker，见
[开发者指南](developer-guide.md)（英文）。

## 仓库结构

```
cli.py        `eds` CLI —— 参考外部调用方（serve/submit/status/open）
agent/        ReAct Supervisor + 提示词 + 确定性 demo 后端
a2a_api/      A2A 端点（Task ≈ Engineering Work Order）
tools/        暴露给 Supervisor 的 Delivery Control 工具
control/      确定性状态 / git / 策略原语
codex/        Codex App Server 客户端 + worker/inspector 驱动
sandbox/      沙箱生命周期（可写 worker、干净 inspector）
deployment/   Docker 部署运行时
db/           SQLAlchemy 模型 + alembic 迁移
docs/         designs/（设计文档集）、milestones.md、refer/（源草案）
```

## 文档

- [架构源草案](docs/refer/engineering-delivery-service-architecture.md)（中文）—— EDS 赖以构建的原始设计文档
- [设计文档集](docs/designs/README.md)（英文）—— 活的真相源：系统架构、A2A 接口、supervisor、交付控制、运行时、工作单状态、部署、交付协议
- [里程碑](docs/milestones.md)（英文）—— 版本驱动的路线图（v0.1–v0.6 ↔ M1–M6）
- [开发者指南](developer-guide.md)（英文）—— 安装、运行、配置、测试、开发工作流
- [CHANGELOG](CHANGELOG.md)（英文） · [v0.1 回顾](docs/versions/v0.1-single-worker-e2e/retrospect.md)（英文）

## 状态

| | |
|---|---|
| **版本** | v0.1 — Single Worker End-to-End · ✅ 已完成（2026-08-22） |
| **已端到端验证** | `eds` CLI → A2A 端点 → ReAct Supervisor（ADK）→ 持久 PostgreSQL 状态 + Delivery Control 工具 → Worker（Codex 或脚本）→ pytest 证据 → Docker 部署 → 可访问的 `/docs` —— 已 dogfood 并记录验收证据 |
| **已设计，尚未落地** | Inspector 运行时与澄清/恢复机制将在 v0.3–v0.6 落地（见[路线图](#路线图)） |
| **已知保留** | 真实模型的实时链路（`pytest -m llm`）在无 LLM 凭证时跳过 —— 每条闭环都以"除模型外全部真实"的方式验证过 |

质量门禁：52/52（`verify_version.py`）· 详情见
[CHANGELOG](CHANGELOG.md) 与
[v0.1 回顾](docs/versions/v0.1-single-worker-e2e/retrospect.md)。

## 许可证

[MIT](LICENSE)
