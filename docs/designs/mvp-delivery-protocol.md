# MVP Delivery Protocol

**Status:** Current · **Applies to:** every work order until the milestone plan lifts it

## 1. Scope Constraints

- Delivered stack: **Python + FastAPI only**.
- Source: **one Git repository per work order** (single fixed template
  repository in v0.1; project registry from v0.5).
- Verification: pytest + OpenAPI contract + human `/docs` acceptance.

## 2. Required Work Order Input

```
Project                  which repository (implicit until v0.5)
API Requirement          the endpoint(s) to build
Input                    request parameters / bodies
Output                   response shape (JSON records, status codes)
Business Logic           the actual rules
Acceptance Criteria      machine-checkable + human-checkable list
```

## 3. Reference Example

```
新增 GET /sales-summary

输入：month

逻辑：按 province × channel × brand 汇总 sales，
保留累计销量 Top 75% 的品牌。

输出：JSON records。

验收：
1. 正常输入返回 200。
2. OpenAPI 中存在 endpoint。
3. pytest 通过。
4. 返回字段符合约定。
5. 部署后可以通过 /docs 人工调用。
```

Minimal v0.1 shape: `"增加 GET /hello?name=...，返回 greeting。"` — the
requirement is complete enough that no clarification is needed (v0.4 adds the
clarification loop for genuinely ambiguous requests).

## 4. Acceptance Gates

A work order is delivered only when all hold:

| Gate | Verified by |
|---|---|
| Normal inputs return 200 with the agreed shape | pytest + Inspector probes |
| Endpoint present in the OpenAPI schema | Inspector |
| pytest suite passes | evidence (`pytest_run`) |
| Response fields match the agreement | Inspector (v0.3+) / Supervisor (v0.1) |
| Deployed and callable through `/docs` | deployment health + human |

## 5. Final Artifact

```
http://<deployment>/docs
```

The minimum bar for human acceptance: open `/docs` → Try it out → Execute →
see a result that satisfies the requirement.
