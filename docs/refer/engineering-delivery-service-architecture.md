# Engineering Delivery Service Architecture

**Status:** Draft v0.2  
**Date:** 2026-08-22

## 1. 定位

Engineering Delivery Service（EDS）是一个面向 Agent / 企业系统的自主工程交付服务。

它接收的不是一次 coding prompt，而是一个完整的 **Engineering Work Order**，并自主推进：

```text
API Requirement
      ↓
Requirement Confirmation
      ↓
Development
      ↓
Testing
      ↓
Inspection
      ↓
Deployment
      ↓
Acceptance
```

第一版 MVP 只支持一个明确场景：

> **FastAPI API 开发与部署**

约束：

- Python + FastAPI
- 单 Git Repository
- 明确 API Requirement
- 自动化测试
- 容器化运行
- 部署到测试环境
- 最终提供 `/docs`
- 人工可直接通过 Swagger UI 验证结果

EDS 对外暴露 **A2A** 接口；内部由一个自由运行的 **ReAct Supervisor** 持续驱动工程任务，直到 Work Order 达到目标状态。

---

## 2. 核心架构判断

### 2.1 EDS 本身就是一个 ReAct Supervisor Agent

EDS 不采用一个确定性 workflow 作为最高层控制器。

最高层是：

```text
Free-running ReAct Supervisor
```

Supervisor 可以持续：

```text
Observe
   ↓
Reason
   ↓
Choose Tool
   ↓
Act
   ↓
Observe Result
   ↓
Reason Again
```

直到工程目标完成。

因此真实运行方式更接近：

```text
Supervisor
   │
   ├─ 检查 Work Order
   ├─ 查询当前状态
   ├─ 要求 Worker 开发
   ├─ 观察 Worker 状态
   ├─ 回答 Worker clarification
   ├─ approve 必要操作
   ├─ 要求 Inspector 验收
   ├─ 根据 Inspector feedback 要求 Worker 修复
   ├─ 再次验收
   ├─ 部署
   ├─ 检查部署状态
   └─ 判断 Work Order 完成
```

Supervisor 决定“下一步做什么”。

确定性系统只负责提供可靠动作和状态。

---

## 3. Delivery Control 是 Supervisor 的工具

确定性 Delivery Control 不控制 Supervisor。

它是 Supervisor 可以调用的一组工具。

```text
                    ReAct Supervisor
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
 Delivery Control      Worker Runtime    Inspector Runtime
     Tools                 Tools              Tools
          │
          ▼
 PostgreSQL Work Order State
```

Delivery Control 负责：

- Work Order CRUD
- 状态持久化
- Project / Repository 定位
- Workspace / Sandbox 生命周期
- Runtime 注册
- Deployment 生命周期
- Retry / timeout primitives
- Approval 状态
- Evidence 持久化
- Audit log
- 幂等操作

但它不负责判断：

> “现在应该开发、测试、重新设计还是部署？”

这个判断属于 Supervisor。

### 3.1 核心 Delivery Control Tools

MVP 可以抽象为：

```text
get_work_order()
update_work_order()

resolve_project()
get_current_state()

create_worker_runtime()
create_inspector_runtime()
destroy_runtime()

get_worker_status()
get_inspector_status()

deploy_candidate()
get_deployment_status()

record_evidence()
mark_complete()
mark_failed()
```

底层都依赖 PostgreSQL 中持久化的 `WorkOrderState`。

---

## 4. 总体架构

```text
                  External Agent / Platform / User
                              │
                              │ A2A
                              ▼
                 ┌───────────────────────────┐
                 │ Engineering Delivery Agent│
                 │                           │
                 │ Google ADK                │
                 │ ReAct Supervisor          │
                 └─────────────┬─────────────┘
                               │
                 reason → tool → observe
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Delivery Control │  │ Worker Runtime   │  │ Inspector Runtime│
│ Tools            │  │                  │  │                  │
│                  │  │ Codex App Server │  │ Codex App Server │
│ PostgreSQL       │  │ Codex Thread     │  │ Codex Thread     │
│ State            │  │ writable sandbox │  │ clean sandbox    │
└─────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
          │                    │                     │
          │                    │ candidate           │ verdict
          │                    ▼                     │
          │                Git Commit                │
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               ▼
                       Deployment Runtime
                               │
                               ▼
                        FastAPI `/docs`
```

---

## 5. 对外接口：A2A

EDS 对外是一个 Engineering Delivery Agent。

A2A 的：

```text
Task
≈
Engineering Work Order
```

而不是：

```text
Task
≈
Codex Turn
```

外部调用者只关心：

```text
"Build and deploy this API."
```

而不需要知道：

- Worker Thread
- Inspector Thread
- Codex Turn
- Sandbox
- Retry
- Inspection loop

### 5.1 A2A 状态映射

| A2A Task State | EDS |
|---|---|
| submitted | Work Order 已建立 |
| working | Supervisor 正在自主推进 |
| input-required | 需要外部确认需求 |
| auth-required | 需要额外权限 |
| completed | 部署并完成最终验收 |
| failed | 无法继续 |
| canceled | 被取消 |

最终 Artifact 至少包括：

```text
repository / commit
deployment URL
/docs URL
test result
inspection result
delivery summary
```

---

## 6. Supervisor

### 6.1 推荐实现：Google ADK

第一版推荐：

```text
Google ADK
+
ReAct Supervisor
+
Delivery Control Tools
```

Google ADK 的优势：

- 与 A2A 集成自然
- Agent / Session / Tool 模型完整
- 可以直接实现自由运行的 LLM Agent
- 支持 callback、tool execution、session state
- 后续可以继续接企业级 Agent Runtime

对于当前目标，没有必要为了 orchestration 换成 LangGraph。

LangGraph 的 graph/state-machine 表达能力更强，但本架构刻意把最高层控制权交给 ReAct Supervisor，因此 ADK 更符合第一版需求。

如果未来需要数小时/数天的强 durable execution，可以把 Temporal 放到 Delivery Control Tool 的实现层：

```text
Supervisor
   ↓
Delivery Control Tool
   ↓
Temporal
```

而不是让 Temporal 取代 Supervisor。

---

## 7. Supervisor 的运行模型

Supervisor 的核心系统提示应围绕一个目标：

> 持续推进当前 Engineering Work Order，直到所有 acceptance criteria 被独立验证并且部署可用。

每轮 Supervisor 获取：

```text
Work Order
Current State
Recent Worker / Inspector Events
Open Questions
Open Gaps
Available Tools
```

然后自主决定：

```text
ask user?
call worker?
continue worker?
approve?
inspect?
fix?
deploy?
verify deployment?
finish?
```

### 7.1 Supervisor 不直接做工程工作

Supervisor 不：

- checkout repository
- 阅读大量代码
- 修改源码
- 跑 pytest
- 调试程序

这些属于 Worker / Inspector。

Supervisor 只维护：

```text
Goal
Current State
Open Gaps
Next Action
```

---

## 8. Worker Runtime

Worker 是完整的 Engineering Runtime。

```text
Worker Sandbox
│
├── Git Workspace
├── FastAPI Project
├── Python Environment
├── Codex App Server
├── Codex Thread
└── Worker Driver
```

Worker 可以：

- checkout/read code
- 理解 FastAPI 项目
- 设计 API
- 修改代码
- 添加测试
- 运行 pytest
- 启动服务
- debug
- 修改 Dockerfile / deployment files
- commit candidate

Worker 的结果：

```text
Candidate Commit
+
Engineering Summary
+
Test Evidence
+
Remaining Concerns
```

Worker 的：

```text
done
```

只表示：

> Candidate 已准备好接受 Inspector 检查。

不代表 Work Order 完成。

---

## 9. 为什么 Worker 使用 Codex App Server

Worker 不使用一次性 `codex exec` 作为唯一控制界面。

因为 Supervisor 需要持续观察并控制工程过程：

```text
Supervisor
    │
    ├── start / resume thread
    ├── start turn
    ├── answer clarification
    ├── approve / reject
    ├── steer
    ├── interrupt
    └── continue after completion
```

同时从 Codex App Server 获得：

```text
turn status
item status
agent messages
command execution
file changes
questions
approval requests
errors
completion events
```

因此 App Server 是：

> **Supervisor 驱动 Coding Worker 的双向控制接口。**

---

## 10. Inspector Runtime

Inspector 不是一个简单的 LLM Judge。

它是第二个完整 Engineering Runtime：

```text
Inspector Sandbox
│
├── Independent Checkout
├── Candidate Commit
├── Python Environment
├── Codex App Server
├── Fresh Codex Thread
└── Inspection Driver
```

它承担：

```text
Reviewer
+
Tester
+
Acceptance Engineer
```

的部分职责。

### 10.1 Inspector 输入

Inspector 获得：

```text
Original Requirement
Acceptance Criteria
Baseline Commit
Candidate Commit
Project Constraints
Deployment Contract
```

原则上不获得 Worker 的完整 reasoning history。

### 10.2 Inspector 工作

典型过程：

```text
checkout candidate
      ↓
read requirement
      ↓
read relevant implementation
      ↓
review diff
      ↓
run existing tests
      ↓
add temporary tests / probes
      ↓
start FastAPI
      ↓
call API
      ↓
inspect OpenAPI schema
      ↓
compare with acceptance criteria
      ↓
ACCEPT / REJECT
```

输出：

```text
verdict
verified criteria
failed criteria
evidence
gaps
risk
```

### 10.3 Inspector 不修代码

如果发现：

```text
GET /sales-summary
```

在空参数下返回 500：

```text
Inspector
    ↓
REJECT + evidence
    ↓
Supervisor
    ↓
"Fix empty-input handling..."
    ↓
Worker
```

Inspector 不直接修改 Candidate。

---

## 11. Worker / Inspector 闭环

```text
                    Supervisor
                        │
                      task
                        ▼
                     Worker
                        │
              candidate + done
                        ▼
                    Supervisor
                        │
                     inspect
                        ▼
                    Inspector
                     /       \
                ACCEPT       REJECT
                  │             │
                  │          feedback
                  │             ▼
                  │         Supervisor
                  │             │
                  │          fix task
                  │             ▼
                  │           Worker
                  │             │
                  │          candidate
                  │             │
                  └─────────────┘
                        │
                        ▼
                     Deploy
```

Worker 与 Inspector 永远不直接通信。

---

## 12. Work Order State

PostgreSQL 中保存的是 EDS 的 durable source of truth。

一个最小 Work Order：

```text
identity
  work_order_id
  project_id
  repository
  baseline_commit

requirement
  original_request
  confirmed_requirement
  acceptance_criteria

worker
  runtime_id
  thread_id
  status
  candidate_commit

inspector
  runtime_id
  thread_id
  status
  verdict
  findings

testing
  pytest
  api_contract
  acceptance

deployment
  status
  deployment_id
  base_url
  docs_url
  health

gaps
  [...]

artifacts
  [...]

overall_status
```

Supervisor 可以随时通过 Delivery Control Tools 重新读取这个状态，而不是依赖自己的短期对话记忆。

---

## 13. FastAPI MVP 的目标交付协议

第一版只接受 FastAPI API 工作。

一个 Work Order 至少包含：

```text
Project
API Requirement
Input
Output
Business Logic
Acceptance Criteria
```

例如：

```text
新增 GET /sales-summary

输入：
month

逻辑：
按 province × channel × brand 汇总 sales，
保留累计销量 Top 75% 的品牌。

输出：
JSON records。

验收：
1. 正常输入返回 200。
2. OpenAPI 中存在 endpoint。
3. pytest 通过。
4. 返回字段符合约定。
5. 部署后可以通过 /docs 人工调用。
```

最终必须得到：

```text
http://<deployment>/docs
```

人工验收的最低门槛就是：

> 打开 `/docs` → Try it out → Execute → 看见符合需求的结果。

这使 MVP 无需先建设额外前端。

---

# 14. MVP Milestones

原则：

> **每个 Milestone 都必须是一个能够完成完整 “API需求 → 开发 → 测试 → 部署 → /docs验证” 的系统。**

后续 Milestone 增加的是自主性、可靠性和工程质量，而不是补齐端到端链路。

---

## Milestone 1 — Single Worker End-to-End

### 目标

验证最小闭环：

```text
A2A Requirement
      ↓
ReAct Supervisor
      ↓
Worker Codex
      ↓
FastAPI Code
      ↓
pytest
      ↓
Docker Deploy
      ↓
/docs
```

### 范围

固定：

- 一个 FastAPI template repository
- 一个 Worker
- 一个 Sandbox
- 一个 Codex App Server
- 本地 Docker 部署
- 单 Work Order
- 无 Inspector

Supervisor 可以直接根据 Worker 的结果判断是否继续。

### 最小组件

```text
Google ADK Supervisor
A2A endpoint
Worker Codex Driver
Sandbox Manager
Git
pytest
Docker
```

PostgreSQL 可以先只记录：

```text
work_order
status
worker_thread_id
candidate_commit
deployment_url
```

### 可验证系统

用户发送：

```text
"增加 GET /hello?name=...，返回 greeting。"
```

系统自动：

```text
开发
→ pytest
→ docker build
→ docker run
```

最终返回：

```text
http://localhost:<port>/docs
```

人工通过 Swagger UI 验证。

### Milestone 1 Exit Criteria

```text
A2A → Supervisor → Codex → FastAPI → pytest → deploy → /docs
```

全链路成功。

---

## Milestone 2 — Durable Delivery Control

### 目标

让系统从“能跑一次”升级为“任务状态可靠”。

加入完整：

```text
PostgreSQL Work Order State
+
Delivery Control Tools
```

Supervisor 开始通过工具操作工程流程，而不是隐式依赖内存。

### 新增

```text
get_work_order
update_work_order
get_current_state

create_runtime
get_runtime_status

deploy_candidate
get_deployment_status

record_evidence
```

增加：

- Work Order durable state
- restart/reconnect
- 基本 retry
- runtime lifecycle
- event/audit record

### 仍然是完整系统

```text
A2A
 ↓
Supervisor
 ↓
Delivery Control + Worker
 ↓
FastAPI
 ↓
pytest
 ↓
deploy
 ↓
/docs
```

### Milestone 2 Exit Criteria

Supervisor 或服务重启后，可以从 PostgreSQL 恢复 Work Order，并继续完成任务。

---

## Milestone 3 — Independent Inspector

### 目标

解决最重要的可靠性问题：

> Worker 不能自己宣布自己完成。

加入第二个：

```text
Inspector Codex App Server
```

### 新流程

```text
Supervisor
   ↓
Worker
   ↓
Candidate Commit
   ↓
Supervisor
   ↓
Inspector
   ↓
ACCEPT / REJECT
```

Inspector 使用独立 checkout，并验证：

```text
code diff
pytest
FastAPI startup
OpenAPI schema
API request/response
acceptance criteria
```

REJECT 后：

```text
Inspector feedback
      ↓
Supervisor
      ↓
Worker fix
      ↓
Inspector again
```

### Milestone 3 Exit Criteria

系统能够故意面对一个 Worker 引入的缺陷：

```text
test failure
wrong response schema
missing edge case
```

Inspector 可以发现问题，Supervisor 驱动 Worker 修复，最终重新验收通过并部署 `/docs`。

---

## Milestone 4 — Requirement Confirmation + HITL

### 目标

把：

```text
"写一个 API"
```

升级成：

```text
"理解并交付 API 需求"
```

Supervisor 在开发前建立：

```text
Confirmed Requirement
+
Acceptance Criteria
```

如果需求存在真正歧义：

```text
Supervisor
    ↓
A2A input-required
    ↓
Human answer
    ↓
continue
```

Codex Worker 自己提出的问题也首先交给 Supervisor：

```text
Worker request_user_input
       ↓
Supervisor
       ├── 可以从 Work Order 回答 → 自动回答
       └── 业务歧义 → Ask Human
```

### Milestone 4 Exit Criteria

一个描述不完整的 API 需求可以通过 1-N 次澄清后，被自动开发、检查、部署，并产生 `/docs`。

---

## Milestone 5 — Project-aware API Delivery

### 目标

从固定 template repo 进入真实已有 FastAPI 项目。

增加：

```text
Project Registry
      ↓
Repository Resolver
      ↓
Repository / Branch / Baseline
```

Work Order 首先定位：

```text
Which Project?
      ↓
Which Git Repository?
      ↓
Which Baseline?
```

再创建独立 Worker / Inspector workspace。

### 新增能力

- 多 Project Registry
- Git clone/worktree
- branch / baseline management
- candidate commit
- PR delivery
- project-specific build/test command
- project-specific deployment config

仍限制：

```text
FastAPI only
single repository
```

### Milestone 5 Exit Criteria

EDS 能针对多个已登记 FastAPI 项目接收 API Work Order，并正确找到 repository、开发、测试、检查、部署和返回 `/docs`。

---

## Milestone 6 — Recoverable Autonomous Delivery

### 目标

让 Supervisor 真正可以无人值守地持续工作。

覆盖：

```text
Worker crash
Inspector crash
Codex turn failure
sandbox failure
deployment failure
Supervisor restart
```

Supervisor 基于：

```text
PostgreSQL State
+
Git Candidate
+
Codex Thread
+
Evidence
```

重新判断当前状态并继续。

增加：

- retry policies
- stale runtime detection
- thread resume
- runtime recreation
- deployment rollback
- bounded autonomous retry
- escalation to human

### Milestone 6 Exit Criteria

在开发、inspection 或 deployment 阶段主动杀掉 runtime，EDS 可以恢复并最终完成 `/docs` 交付，或者明确进入 `input-required / failed`，而不是丢失任务。

---

# 15. MVP 演进总览

```text
M1
Working E2E
A2A → Supervisor → Worker → pytest → deploy → /docs
                     │
                     ▼
M2
Durable State
PostgreSQL + Delivery Control Tools
                     │
                     ▼
M3
Independent Verification
Worker → Inspector → feedback loop
                     │
                     ▼
M4
Requirement Engineering
clarification + HITL + acceptance criteria
                     │
                     ▼
M5
Real Projects
project → repo → worktree → PR
                     │
                     ▼
M6
Autonomous Recovery
crash/retry/resume/recover
```

每一层都保持：

```text
API Requirement
      ↓
Development
      ↓
Testing
      ↓
Deployment
      ↓
FastAPI /docs
```

端到端可运行。

---

## 16. 推荐第一版技术栈

| Layer | Choice |
|---|---|
| External Agent Protocol | A2A |
| Supervisor Framework | Google ADK |
| Supervisor Pattern | Free-running ReAct Agent |
| Deterministic Control | Delivery Control Tools |
| Durable State | PostgreSQL |
| Worker | Codex App Server |
| Inspector | Codex App Server |
| Worker/Inspector Isolation | Separate Sandbox / Container |
| Project Source | Git |
| API Framework | FastAPI only |
| Test | pytest |
| API Contract | OpenAPI |
| Deployment | Docker |
| Human Acceptance | FastAPI `/docs` |
| Delivery | Commit → later PR |
| Observability | Work Order events + Codex events |

---

## 17. MVP 最小代码结构

```text
engineering-delivery-service/
│
├── agent/
│   ├── supervisor.py
│   └── prompts/
│
├── a2a/
│   └── server.py
│
├── tools/
│   ├── work_order.py
│   ├── project.py
│   ├── runtime.py
│   ├── worker.py
│   ├── inspector.py
│   └── deployment.py
│
├── control/
│   ├── state.py
│   ├── repository.py
│   └── policy.py
│
├── codex/
│   ├── app_server_client.py
│   ├── worker_driver.py
│   └── inspector_driver.py
│
├── sandbox/
│   └── manager.py
│
├── deployment/
│   └── docker.py
│
└── db/
    ├── models.py
    └── migrations/
```

这里刻意不建立：

```text
workflow/
  deterministic_pipeline.py
```

因为流程控制属于 Supervisor。

`control/` 只提供确定性状态和动作 primitive。

---

## 18. 最终职责模型

```text
External Agent
       │
       │ A2A Work Order
       ▼
┌─────────────────────────────┐
│ ReAct Supervisor            │
│                             │
│ Understand                  │
│ Decide                      │
│ Coordinate                  │
│ Recover                     │
│ Finish                      │
└──────────────┬──────────────┘
               │ tools
       ┌───────┼────────┐
       │       │        │
       ▼       ▼        ▼
 Delivery    Worker   Inspector
 Control      Codex     Codex
   │           │         │
   │       candidate   verdict
   │           │         │
   └───────────┴─────────┘
               │
               ▼
         Current State
               │
               └──────► Supervisor
```

最终原则：

> **Supervisor owns the delivery.**  
> **Delivery Control provides deterministic state and actions.**  
> **Worker produces the candidate.**  
> **Inspector establishes the truth.**

对于 MVP，唯一业务目标是：

> **给 EDS 一个 FastAPI API 需求，它自主完成开发、测试和部署，最终给人一个可以打开并通过 `/docs` 验证的 API。**
