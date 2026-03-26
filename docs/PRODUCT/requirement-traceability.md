# Requirement Traceability

This document is the execution-facing bridge between the normative PDFs and repository work. The normative sources remain [prd.pdf](../../prd.pdf) and [TDD.pdf](../../TDD.pdf); this file is the queryable markdown source that later slices must update.

## Rules

- Row identity is `Source Doc + Source ID`. This matters because `AC-01` exists in both PRD and TDD.
- Numbered source IDs keep their original IDs.
- Unnumbered clauses get stable synthetic IDs with `PRD-` or `TDD-` prefixes.
- `Current Status` is restricted to `missing`, `partial`, `implemented`, `validated`, `deferred`, or `conflict`.
- `implemented` and `validated` both require concrete `Repo Evidence`.
- `validated` additionally requires concrete `Validation Evidence`.
- This audit is conservative. If the repo has code but no proof or only partial behavior, the row is not marked `validated`.

## Audit Basis

The current status snapshot below is based on direct inspection of:

- `services/platform-api/src/cvm_platform/application/service.py`
- `services/platform-api/src/cvm_platform/api/routes.py`
- `services/platform-api/src/cvm_platform/api/openapi_contract.py`
- `services/platform-api/src/cvm_platform/infrastructure/adapters.py`
- `services/platform-api/src/cvm_platform/infrastructure/agent_tracing.py`
- `services/platform-api/src/cvm_platform/infrastructure/models.py`
- `services/temporal-worker/src/cvm_worker/workflows.py`
- `services/eval-runner/src/cvm_eval_runner/cli.py`
- `apps/web-user/src/app/features/shortlist/shortlist.page.ts`
- `apps/web-user/src/app/features/shortlist/shortlist.page.html`
- `apps/web-ops/src/app/features/ops/ops.page.ts`
- `tests/test_api_flow.py`
- `tests/test_api_stack.py`
- `tests/test_eval_runner.py`
- `docker-compose.yml`
- `Makefile`
- `.github/workflows/validate.yml`

## Synthetic ID Namespaces

- `PRD-NFR-*`: unnumbered PRD non-functional requirement groups from PRD `§6.1`
- `TDD-ARCH-*`: unnumbered architecture principles from TDD `§3.1`
- `TDD-ERR-*`: grouped error-code expectations from TDD `§6.5` and Appendix A
- `TDD-WF-*`: grouped workflow expectations from TDD `§7.1`
- `TDD-IDEMPOTENCY-*`: grouped retry / idempotency rules from TDD `§7.2`
- `TDD-DAY0-GATES`, `TDD-WEEK1-GATES`: rollout gates from TDD `§12.1`
- `TDD-HARD-RULES`: hard prohibitions from TDD Appendix B

## PRD Goals, JD, Keywords, and Agent Run

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | PRD | §1.2 | Goal | JD 到首批候选列表更快；从录入到首批候选中位耗时 ≤ 5 分钟 | partial | `routes.py::create_agent_run`<br>`tests/test_api_flow.py::test_mainline_agent_flow` | Mainline flow exists; no timed SLO check | latency measurement, timed evals | Slice 02 | 流程在，目标度量缺失 |
| G2 | PRD | §1.2 | Goal | 首轮筛查效率提升 ≥ 30% | missing | `service.py::save_verdict` stores outcomes but no funnel metric | None yet | funnel definition, baseline dataset, ops metrics | Slice 03 | 只有 verdict 数据，没有效率口径 |
| G3 | PRD | §1.2 | Goal | AI 草案被真正使用；草案采纳率 ≥ 70% | partial | `agent_runs.py::_extract_strategy`<br>`agent_runs.py::_reflect_round` | `tests/test_api_flow.py::test_mainline_agent_flow` proves AI strategy generation is on the main path, but there is no adoption metric | adoption telemetry, reviewer feedback capture | Slice 02 | 当前 AI 直接生成并迭代检索策略，不再经旧草案确认流 |
| G4 | PRD | §1.2 | Goal | 流程稳定可恢复；Run 完成率 ≥ 95%，异常可重试且不丢结果 | partial | `service.py::execute_agent_run`<br>`workflows.py::AgentRunWorkflow`<br>`agent_runs.py::_should_stop_after_round` | `tests/test_api_stack.py::test_stack_agent_run_flow` | retry controls, partial status model | Slice 02 | 现有主链通过 Temporal 编排，但更细的恢复语义仍待补强 |
| G5 | PRD | §1.2 | Goal | 审计与合规可落地；敏感动作审计覆盖率 100%，默认脱敏导出 | partial | `service.py::_audit`<br>`service.py::create_export` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | admin audit query, role model, download audit | Slice 04 | 默认脱敏有证据，审计覆盖不完整 |
| G6 | PRD | §1.2 | Goal | AI 异常不阻塞业务；AI 不可用时主流程仍可手工完成 | partial | `agent_runs.py::_extract_strategy`<br>`agent_runs.py::_analyze_candidate_with_fallback` | `tests/unit/test_agent_runs.py::test_agent_run_execute_uses_fallback_strategy_and_duplicate_strategy_stop` | manual strategy editor, richer degrade UX | Slice 03 | 当前后端会降级到确定性策略与 heuristic ranking，但前端手工干预面仍未补齐 |
| JD-01 | PRD | §4.1 | P0 | 支持创建、保存、归档 JD Case；创建后默认草稿 | partial | `service.py::create_case`<br>`routes.py::create_case` | `tests/unit/test_platform_service.py::test_create_export_writes_masked_file_and_reuses_idempotency_key` creates a case through the current service path | archive behavior, case list UI | Slice 02 | Case 基础能力仍在，但当前最小闭环不再要求用户先建 Case |
| JD-02 | PRD | §4.1 | P0 | 修改激活 JD 时创建新版本，不改写历史版本 | implemented | `service.py::create_jd_version`<br>`sqlalchemy_uow.py::deactivate_versions` | No targeted version-history test | version-history UI, history assertions | Slice 02 | 代码按新版本写入，未见专项验证 |
| JD-03 | PRD | §4.1 | P0 | 同一时间只有一个激活 JD 版本可发起新检索 | implemented | `service.py::create_jd_version` sets `is_active=True`<br>`sqlalchemy_uow.py::deactivate_versions` | No targeted active-version test | active-version read model | Slice 02 | 持久层有唯一激活语义 |
| JD-04 | PRD | §4.1 | P1 | 离开页面前提示未保存修改 | missing | `shortlist.page.ts` has no dirty-form or unload guard | None yet | UI state tracking | Slice 02 | 直接缺口 |
| JD-05 | PRD | §4.1 | P0 | JD 超长时不得静默截断；提示精简或智能精简 | missing | `service.py::create_jd_version` stores raw text unchanged; no `JD_TOO_LONG` path | None yet | long-JD contract, condense flow | Slice 02 | 规范存在，代码无对应 |
| JD-06 | PRD | §4.1 | P0 | 无有效激活版本时不允许发起 Agent Run | partial | `shortlist.page.ts::startRun` requires explicit `JD` input before `createAgentRun` | No direct invalid-version test | active-version guard at API boundary | Slice 02 | 当前最小闭环直接从两段原始输入起跑，不再经旧的 Case/Plan 入口 |
| KW-01 | PRD | §4.2 | P0 | 基于激活 JD 生成结构化关键词与条件草案 | implemented | `agent_runs.py::_extract_strategy`<br>`adapters.py::extract_agent_search_strategy` | `tests/test_api_flow.py::test_mainline_agent_flow` | richer prompt/schema coverage | Slice 02 | 当前最小闭环在 AgentRun 内直接生成结构化检索策略 |
| KW-02 | PRD | §4.2 | P0 | 每条 AI 关键词/条件显示提取依据 | partial | `service.py::_draft_to_payload` stores `evidence_refs`<br>`ConfirmConditionPlanRequest` carries `evidenceRefs` | No UI test proving evidence display | evidence UI, human-readable rationale | Slice 02 | 后端有证据结构，前端未直接呈现 |
| KW-03 | PRD | §4.2 | P0 | 用户可新增、删除、移动、合并、去重、手工改写关键词 | missing | Current `shortlist.page.ts` only submits raw `JD` + `寻访偏好`; no manual keyword editor or query-plan surface exists | None yet | explicit query editor UI and contract | Slice 02 | 旧确认计划流已删除，这条需求需要后续以新 UI 重新实现 |
| KW-04 | PRD | §4.2 | P1 | 支持多套查询方案并显式选择其一 | missing | `agent_runs.py::_reflect_round` only keeps one active strategy per round | None yet | multi-plan model and reviewer selection UI | Slice 02 | 当前只有单条运行中策略，没有显式多方案选择面 |
| KW-05 | PRD | §4.2 | P0 | 发起检索前必须有一次用户确认动作；不得后台自动起 Run | implemented | `shortlist.page.ts::startRun` is the only explicit trigger for `createAgentRun` | `tests/test_api_flow.py::test_mainline_agent_flow` | explicit actor audit in API tests | Slice 02 | 当前最小闭环只有一次显式启动动作 |
| KW-06 | PRD | §4.2 | P0 | 关键词冲突时提示修正；未处理前不允许发起 Run | missing | `routes.py::create_agent_run` accepts only raw inputs; there is no explicit strategy-conflict review step yet | None yet | conflict validation rules, reviewer intervention UI | Slice 02 | 当前最小闭环缺少显式冲突修正面 |
| KW-07 | PRD | §4.2 | P0 | AI 草案超过 10 秒仍需保留手工编辑可用并允许重试 | partial | `agent_runs.py::_extract_strategy` degrades to deterministic fallback instead of blocking the run | `tests/unit/test_agent_runs.py::test_agent_run_execute_uses_fallback_strategy_and_duplicate_strategy_stop` | manual strategy editor, retry UX | Slice 03 | 后端已可降级继续，但还没有显式手工编辑和重试交互 |
| KW-08 | PRD | §4.2 | P1 | JD 超上下文预算时先给智能精简摘要再生成草案 | missing | No condense step in service or UI | None yet | condense workflow, summary approval UI | Slice 03 | 直接缺口 |
| SR-01 | PRD | §4.3 | P0 | Agent Run 冻结发起输入、时间、状态、模型与提示词版本 | partial | `service.py::create_agent_run`<br>`routes.py::_agent_run_response` | `tests/test_api_flow.py::test_mainline_agent_flow` | actor attribution, richer replay metadata | Slice 02 | 关键字段已落库，回放维度仍可继续扩展 |
| SR-02 | PRD | §4.3 | P0 | 默认首批固定页数；继续翻页必须用户显式触发 | partial | `config.py::agent_round_fetch_schedule`<br>`agent_runs.py::execute_run` | `tests/test_api_stack.py::test_stack_agent_run_flow` | explicit continue/stop controls | Slice 02 | 当前默认节奏是 `10 -> 5 -> 5`，但没有显式用户继续翻页操作 |
| SR-03 | PRD | §4.3 | P0 | 部分页失败不影响已返回页使用 | partial | `agent_runs.py::_search_round` and `agent_runs.py::_append_step` preserve completed-round evidence before later stop/failure | No targeted partial-failure regression yet | retry UI, partial-complete status | Slice 02 | 当前通过 step/shortlist 保留已完成轮次结果，不再经旧页快照接口暴露 |
| SR-04 | PRD | §4.3 | P0 | 明确区分 0 结果与参数异常 | partial | `adapters.py` returns `CTS_PARAM_ANOMALY` for invalid paging | `tests/unit/test_adapters_runtime.py::test_cts_runtime_adapter_distinguishes_param_anomaly_from_zero_results` | run-level error surfacing in current UI | Slice 02 | 适配器层已区分两类结果，但当前最小 UI 还没单独展示该差异 |
| SR-05 | PRD | §4.3 | P0 | 展示 Run 状态、进度、失败原因，便于决定重试/继续翻页 | implemented | `routes.py::get_agent_run`<br>`shortlist.page.ts::syncRunState` | `tests/test_api_flow.py::test_mainline_agent_flow` | retry/continue actions | Slice 02 | 当前会展示 AgentRun 状态、轮次和最终结果，但操作按钮仍待扩展 |
| SR-06 | PRD | §4.3 | P0 | Agent Run 创建需支持幂等 | implemented | `agent_runs.py::create_run` checks `idempotency_key`<br>`models.py` unique `idempotency_key` | `tests/unit/test_agent_runs.py::test_agent_run_create_normalizes_config_and_backfills_existing_workflow_id` | explicit conflict/echo contract | Slice 02 | 当前幂等语义统一落在 AgentRun 上 |
| SR-07 | PRD | §4.3 | P0 | 同页重试成功不得重复生成页快照或候选 | partial | `agent_runs.py::_dedupe_round_candidates` skips repeated resumes before analysis and ranking | `tests/test_api_flow.py::test_mainline_agent_flow` proves final shortlist IDs are unique | retry controller, replay test | Slice 02 | 当前主闭环重点是跨轮去重，不再生成旧页快照对象 |
| SR-08 | PRD | §4.3 | P1 | 来源接口有未知新字段时保留原始快照并继续展示已知字段 | partial | `agent_runs.py::_search_round` preserves normalized CTS payloads in step records and Langfuse spans | No unknown-field regression test | raw-snapshot viewer, adapter fuzz tests | Slice 05 | 当前回放更多依赖 step payload 和 Langfuse trace，而不是旧页快照接口 |
| SR-09 | PRD | §4.3 | P1 | 用户可主动停止剩余页抓取；已返回结果保留 | partial | `agent_runs.py::_should_stop_after_round` and reflection stop rules preserve existing shortlist output | No explicit user-stop test | Temporal signal, run state expansion | Slice 02 | 系统内停机规则在，显式用户 stop 仍未暴露 |

## PRD List, Detail, Verdict, Export, Audit, Ops, and Evals

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LI-01 | PRD | §4.4 | P0 | 候选列表以当前 Agent Run 结果为边界，不跨 Run 混排 | implemented | `routes.py::get_agent_run` returns one run-scoped shortlist<br>`shortlist.page.ts::syncRunState` renders only the current run result | `tests/test_api_flow.py::test_mainline_agent_flow` | run comparison UI | Slice 03 | 结果边界明确 |
| LI-02 | PRD | §4.4 | P0 | 列表默认显示最小必要字段，联系方式默认不展示 | partial | `shortlist.page.ts::candidateMeta` only shows title/company/location next to the candidate name | No targeted UI field test | richer card projection, review state | Slice 03 | 联系方式没露出，但字段集不完整 |
| LI-03 | PRD | §4.4 | P0 | 高亮命中必须项/加分项并标记缺失必须项 | missing | No hit-highlighting logic in `shortlist.page.ts` or current shortlist payload | None yet | match explanation model | Slice 03 | 直接缺口 |
| LI-04 | PRD | §4.4 | P1 | 支持按 verdict、命中完整度、疑似重复、本地排序筛选列表 | missing | No list filter controls in `shortlist.page.ts` | None yet | filter model, client state | Slice 03 | 直接缺口 |
| LI-05 | PRD | §4.4 | P1 | 详情返回列表时保留滚动位置、筛选条件、选中页 | missing | `shortlist.page.ts` has no router-state or scroll preservation | None yet | route state, UI state model | Slice 03 | 直接缺口 |
| LI-06 | PRD | §4.4 | P0 | 来源字段缺失统一显示“未提供”，不得报错 | partial | `shortlist.page.ts::candidateReason` and `shortlist.page.html` rely on fallback text and conditional detail sections | No targeted missing-field test | card-level fallback coverage | Slice 03 | 详情有兜底，列表未完全覆盖 |
| CD-01 | PRD | §4.5 | P0 | 候选详情展示简历主要区块，敏感字段按角色处理 | partial | `routes.py::_candidate_detail_response`<br>`shortlist.page.html` detail/resume blocks | `tests/test_api_flow.py::test_mainline_flow` loads detail | role-based masking, source-field projection | Slice 03 | 区块大体在，角色处理不足 |
| CD-02 | PRD | §4.5 | P0 | AI 面板输出“满足/部分满足/缺失证据/需人工核实”检查清单 | partial | `ResumeAnalysis` carries `summary`, `evidenceSpans`, `riskFlags` | No checklist-format test | structured checklist schema | Slice 03 | 有分析对象，无标准检查清单 |
| CD-03 | PRD | §4.5 | P0 | AI 每条结论必须关联证据；无证据需标“无直接证据” | partial | `service.py::_candidate_evidence_spans` populates evidence spans | No proof for no-evidence labeling | evidence labeling rules | Slice 03 | 有证据片段，无“无直接证据”契约 |
| CD-04 | PRD | §4.5 | P0 | 原始简历内容优先加载，AI 面板异步非阻塞 | partial | `routes.py::get_case_candidate` returns resume + aiAnalysis together | No async-loading or degrade test | split detail loading path | Slice 03 | 当前是同步聚合返回 |
| CD-05 | PRD | §4.5 | P1 | 证据片段可一键插入 verdict 备注 | missing | No insert-evidence interaction in `shortlist.page.ts` | None yet | verdict composer UX | Slice 03 | 直接缺口 |
| CD-06 | PRD | §4.5 | P0 | AI 辅助超过 10 秒应提示可重试且不锁死详情页 | missing | No timeout/retry branch for detail AI analysis | None yet | async analysis job, timeout UX | Slice 03 | 直接缺口 |
| CD-07 | PRD | §4.5 | P0 | 简历过长或结构异常时分段折叠并以“未提供”兜底 | partial | `shortlist.page.html` uses sectional lists and conditional fallbacks | No long-resume stress test | segmented resume renderer | Slice 03 | 有基础兜底，无长简历折叠 |
| RV-01 | PRD | §4.6 | P0 | 顾问显式提交 Match / Maybe / No；AI 不得代提 | implemented | `service.py::save_verdict`<br>`routes.py::save_verdict` | `tests/test_api_flow.py::test_mainline_flow` covers `Match` path only | broader tri-state tests | Slice 03 | 显式提交在，三态未全验 |
| RV-02 | PRD | §4.6 | P0 | verdict=No 时必须有原因标签或手工原因 | missing | `service.py::save_verdict` accepts empty `reasons` and `notes` | None yet | No-verdict validation rule | Slice 03 | 直接缺口 |
| RV-03 | PRD | §4.6 | P0 | Match / Maybe 支持加入 Case 级候选池并保留来源 Run/理由 | partial | `service.py::save_verdict` updates `latest_verdict`<br>`service.py::create_export` exports `Match/Maybe` candidates | Mainline flow proves verdict persistence, not explicit pool UI | candidate pool read model and UI | Slice 03 | 有池化效果，无独立候选池对象/UI |
| RV-04 | PRD | §4.6 | P0 | 同一候选每次 verdict 修改都留历史，展示最新有效 verdict | implemented | `service.py::save_verdict` appends `VerdictHistoryRecord`<br>`routes.py::_candidate_detail_response` returns history | No repeated-edit test | repeated-update test | Slice 03 | append-only 语义已编码 |
| RV-05 | PRD | §4.6 | P1 | 不同用户冲突 verdict 需显著提示 | missing | No conflict-detection logic in service or UI | None yet | reviewer identity model, conflict projection | Slice 03 | 直接缺口 |
| RV-06 | PRD | §4.6 | P0 | 从候选池移除不删除历史检索与 verdict 记录 | missing | No pool-removal operation exists | None yet | pool lifecycle model | Slice 03 | 缺少“移除但保留历史”能力 |
| EX-01 | PRD | §4.7 | P0 | 支持按条件导出候选池到 CSV | validated | `service.py::create_export` writes CSV<br>`service.py::_write_export_file` | `tests/test_api_flow.py::test_mainline_flow` | none | Slice 04 | CSV 导出已跑通 |
| EX-02 | PRD | §4.7 | P0 | 默认脱敏导出；敏感字段需权限和原因 | validated | `service.py::create_export` enforces `NO_CONTACT_PERMISSION` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | approval workflow, field-level policy | Slice 04 | 当前只覆盖本地模式禁止敏感导出 |
| EX-03 | PRD | §4.7 | P0 | 导出为异步任务，导出中心可看生成中/完成/失败 | partial | `ExportJobRecord` has status fields<br>`service.py::create_export` updates running/completed/failed | No async export-center test | async export worker, export center UI | Slice 04 | 有状态字段，执行仍同步发生在请求内 |
| EX-04 | PRD | §4.7 | P0 | 导出任务记录发起人、时间、Case、条件、字段范围、下载行为 | partial | `ExportJobRecord` stores case, reason, status, times<br>`_audit` writes export completion | No download-audit or actor-identity test | export metadata expansion, download audit | Slice 04 | 留痕不完整 |
| EX-05 | PRD | §4.7 | P1 | 导出文件默认 7 天过期 | missing | `service.py::_build_export_path` writes plain path; no TTL policy | None yet | expiry scheduler, signed access policy | Slice 04 | 直接缺口 |
| EX-06 | PRD | §4.7 | P1 | 导出失败显示原因并支持原条件重试 | partial | `service.py::create_export` marks failure with `EXPORT_FAILED` | No retry surface or test | retry endpoint/UI | Slice 04 | 失败状态在，重试闭环不足 |
| LD-01 | PRD | §4.8 | P1 | 团队看板展示 Case 数、运行中 Run、候选打开数、Match/Maybe、失败分布 | partial | `routes.py::get_ops_summary`<br>`apps/web-ops/.../ops.page.ts` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` asserts ops summary version fields | case/team projections, candidate-open audit | Slice 04 | 当前更像系统运行总览，不是 Team Lead 看板 |
| LD-02 | PRD | §4.8 | P1 | 可按顾问、Case、时间范围筛选并查看趋势 | missing | No filterable team dashboard route or UI | None yet | team model, time-series projections | Slice 04 | 直接缺口 |
| LD-03 | PRD | §4.8 | P1 | 同一 Case 的不同 JD 版本 / Agent Run 可并排对比 | missing | No compare view in API or UI | None yet | comparison read model | Slice 04 | 直接缺口 |
| LD-04 | PRD | §4.8 | P0 | Team Lead 复核或修订 verdict 必须留痕 | missing | `save_verdict` records actor, but no lead-review flow | None yet | team-role review workflow | Slice 04 | 基础留痕在，复核能力缺失 |
| AU-01 | PRD | §4.9 | P0 | 审计登录、Case、条件确认、Run、打开候选、verdict、导出/下载等敏感动作 | partial | `service.py::_audit` logs case/jd/plan/run/verdict/export/eval events<br>`AuditLogModel` exists | No coverage audit proving all required actions | auth events, candidate-open audit, download audit | Slice 04 | 审计基础在，覆盖率远未到 100% |
| AU-02 | PRD | §4.9 | P0 | 管理员可按人、Case、时间、动作类型、导出任务查询审计日志 | missing | No audit query route in `routes.py` | None yet | admin audit API and UI | Slice 04 | 直接缺口 |
| AU-03 | PRD | §4.9 | P0 | 审计日志只增不改，普通业务页面不可编辑 | implemented | `AuditLogRepository` only exposes `save_audit_log`<br>No audit update route in `routes.py` | No explicit immutability test | DB-level guard, admin surface | Slice 04 | 当前 API 面未提供编辑路径 |
| AU-04 | PRD | §4.9 | P0 | 列表、详情、导出、看板的字段脱敏规则一致 | missing | Export path masks sensitive export; list/detail/ops use separate projections | None yet | shared field policy layer | Slice 04 | 统一脱敏策略尚未建立 |
| AU-05 | PRD | §4.9 | P0 | 权限不足时给明确拒绝信息但不泄露敏感内容 | partial | `NO_CONTACT_PERMISSION` in `service.py::create_export` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | broader permission model, detail masking | Slice 04 | 导出场景成立，其它敏感入口不足 |
| OP-01 | PRD | §4.10 | P1 | 运行监控页看到排队、失败、超时任务及原因分类 | partial | `routes.py::get_ops_summary`<br>`ops.page.ts` summary and diagnostics | No timeout-category test | queue/timeout projections | Slice 04 | 有总览和 diagnostics，无完整任务分类 |
| OP-02 | PRD | §4.10 | P1 | 支持按版本查看 AI 命中率、AI 超时率、Run 完成率 | partial | `OpsSummaryResponse.version` exposes build/version data | No version-metrics test | `ai_version_metrics` projection | Slice 04 | 版本元数据在，效果指标不在 |
| EV-01 | PRD | §4.10 | P2 | 内部评测页比较不同提示词/模型版本效果 | partial | `routes.py::create_eval_run`<br>`docker-compose.yml::web-evals` exposes self-hosted Langfuse review UI<br>`agent_tracing.py::LangfuseAgentRunTracer`<br>`cli.py::run_blocking_suite` | `tests/test_eval_runner.py::test_blocking_suite_passes` | dataset/version comparison, non-blocking suites | Slice 05 | 当前评测回看转向 Langfuse trace review，不是独立 Angular 对比平台 |

## PRD Acceptance and Non-Functional Requirements

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | PRD | §7.2 | P0 | 在一个 Case 内完成 JD -> 条件 -> Run -> 浏览候选 -> verdict -> 候选池闭环 | partial | `test_api_flow.py::test_mainline_agent_flow` covers the current `JD + 寻访偏好 -> AgentRun -> shortlist` path | Mainline flow test exists | explicit candidate-pool UI/model | Slice 03 | 当前先聚焦最小 agent 闭环 |
| AC-02 | PRD | §7.2 | P0 | 明确区分 0 结果和参数异常 | partial | `adapters.py` anomaly mapping | `tests/unit/test_adapters_runtime.py::test_cts_runtime_adapter_distinguishes_param_anomaly_from_zero_results` | current UI/API surfacing for run-level anomaly details | Slice 02 | 适配器已区分，但当前最小闭环尚未把该差异显式展示给最终用户 |
| AC-03 | PRD | §7.2 | P0 | AI 草案或 AI 简历分析失败时仍可手工继续 | partial | `shortlist.page.html` keeps raw `JD` / `寻访偏好` inputs editable until submission<br>`service.py::_upsert_candidate` builds stub analysis | No timeout/failure-path test | async AI failures, degrade UX | Slice 03 | 手工路径在，失败契约不足 |
| AC-04 | PRD | §7.2 | P0 | Run 中断后成功页可查看，重试不重复生成页 | partial | `agent_runs.py::_append_step` and `agent_runs.py::_dedupe_round_candidates` preserve completed-round evidence and suppress duplicate resumes | No retry/interruption regression test | retry controller and tests | Slice 02 | 当前通过 step/shortlist 保留进度，不再依赖旧页快照落库 |
| AC-05 | PRD | §7.2 | P0 | 历史 Agent Run、JD 版本、verdict 记录可完整复盘 | partial | `JDVersionRecord`, `AgentRunRecord`, `VerdictHistoryRecord`, `AuditLogModel` all exist | No holistic replay or audit query test | history UI, audit query API | Slice 04 | 数据基础在，复盘入口不足 |
| AC-06 | PRD | §7.2 | P0 | 导出默认脱敏；敏感导出受权限与原因校验约束 | partial | `create_export` enforces masked/sensitive split and reason | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | approval rules, field policy | Slice 04 | 基础限制有，审批未建 |
| AC-07 | PRD | §7.2 | P0 | 管理员可查敏感动作审计日志 | partial | `AuditLogModel` and `_audit` exist | No admin query test | audit query/read model | Slice 04 | 写入基础在，查询缺口大 |
| AC-08 | PRD | §7.2 | P1 | Team Lead 可看 Case 数、运行中任务、候选打开量、Match/Maybe、失败分布 | partial | `get_ops_summary` exposes run/failure/latency/version data | No team-lead dashboard test | team metrics and role filters | Slice 04 | 当前更像系统 ops summary |
| PRD-NFR-PERFORMANCE | PRD | §6.1 | P0 | Agent Run 提交 2 秒内返回明确状态；首批结果与详情原始简历有 SLO；AI 超时 10 秒自动降级 | partial | `routes.py::create_agent_run` returns queued status immediately<br>`routes.py::get_case_candidate` returns detail payload | No latency or timeout benchmark | timing instrumentation, async AI timeout handling | Slice 05 | 返回快，但没有正式 SLO/降级证明 |
| PRD-NFR-RELIABILITY | PRD | §6.1 | P0 | 成功快照、verdict、导出审计不能丢失或重复；异常重试有上限且转为可见失败 | partial | `models.py` unique constraints on pages/export idempotency<br>`service.py::save_verdict` append-only history | No bounded-retry test | retry policy and failure-state model | Slice 05 | 数据约束有，重试策略未闭环 |
| PRD-NFR-CAPACITY | PRD | §6.1 | P0/P1 | 至少 50 并发 Agent Run / 100 并发详情 AI；超载时排队且不阻塞已返回结果浏览 | missing | No capacity controls or load tests in repo | None yet | queueing model, load tests | Slice 05 | 直接缺口 |
| PRD-NFR-SECURITY | PRD | §6.1 | P0 | 敏感字段默认脱敏；导出、下载、查看敏感字段都纳入审计 | partial | `create_export` masks by policy and blocks sensitive export locally<br>`_audit` exists | Sensitive export block test only | role-boundary model, download/view audit | Slice 04 | 安全边界只覆盖一部分入口 |
| PRD-NFR-RETENTION | PRD | §6.1 | P1 | 导出文件 7 天过期；审计日志至少保留 180 天 | missing | No TTL or retention policy in export/audit code | None yet | retention scheduler, lifecycle policy | Slice 04 | 直接缺口 |
| PRD-NFR-TRACEABILITY | PRD | §6.1 | P0 | AI 输出带来源版本和证据引用；Run 可定位到 JD 版本和条件方案版本 | partial | `AgentRunRecord` and step payloads store model/prompt versions<br>`ResumeAnalysisRecord` stores prompt/model versions | No end-to-end replay proof | output schema versioning, audit queries | Slice 05 | 版本字段有，但全链路回放不足 |
| PRD-NFR-OPERABILITY | PRD | §6.1 | P1 | 内部页面看到 Run 完成率、AI 超时率、导出失败率、主要错误分类 | partial | `OpsSummaryResponse` includes queue/failures/latency/version | No rate-metric test | derived metrics and ops projections | Slice 04 | 错误分布部分在，完成率/AI 超时率缺 |
| PRD-NFR-USABILITY | PRD | §6.1 | P1 | 核心表单支持粘贴、键盘切换、明确空态/加载态/错误态 | partial | `shortlist.page.html` and `shortlist.page.ts` provide paste-friendly textareas plus empty/loading/error states<br>`ops.page.ts` | No UX interaction test | keyboard flows, loading states, accessibility checks | Slice 03 | 空态/错误态有，键盘体验未验证 |

## TDD ADRs and Core Engineering Rules

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADR-001 | TDD | §3 / p.5 | Decision | 模块化单体 + 独立 worker；Day 0 不拆微服务 | implemented | `services/platform-api` + `services/temporal-worker` repo shape | `docs/ARCHITECTURE/context-map.md` reflects modular monolith | none | Slice 05 | 当前形态符合 ADR |
| ADR-002 | TDD | §3 / p.5 | Decision | 单一 Angular shell + 路由域隔离，不起四个独立前端应用 | conflict | `docs/ARCHITECTURE/context-map.md` lists `apps/web-user` and `apps/web-ops` as separate Angular apps | None yet | architecture decision reset or consolidation plan | Slice 05 | 当前仓库与 ADR 仍有结构性冲突 |
| ADR-003 | TDD | §3 / p.5 | Decision | Postgres 写模型 + 读投影 + outbox；不先上 Redis/Kafka/Elastic | partial | Postgres-first repo shape and SQLAlchemy models exist; no outbox tables or publisher | No outbox/projection validation | outbox/event publisher, read models | Slice 05 | 只实现了前半段 |
| ADR-004 | TDD | §3 / p.5 | Decision | Temporal 只编排长流程；不是所有请求都进 workflow | implemented | `AgentRunWorkflow` is the long-running path; CRUD routes remain sync | `tests/test_api_stack.py::test_stack_agent_run_flow` | none | Slice 05 | 当前用法符合 ADR |
| ADR-005 | TDD | §3 / p.5 | Decision | `docs/` 作为知识事实源并兼作 Obsidian 内容根 | partial | `docs/00-INDEX.md` and docs tree exist | `Makefile validate` runs `tools/ci/check_links.py` | docs freshness automation | Slice 01 | 有 docs SSOT 基础，刷新度校验还偏轻 |
| ADR-006 | TDD | §3 / p.5 | Decision | DTO / client 由合同生成；不手写边界模型双写 | partial | `contracts/` plus generated libs exist<br>`Makefile codegen` | `Makefile validate` runs codegen and generated-clean checks | boundary-model cleanup, codegen hygiene | Slice 05 | 生成链在，但仍有手写 boundary models |
| ADR-007 | TDD | §3 / p.5 | Decision | Ops / Evals 从 Day 0 起建最小骨架 | partial | `apps/web-ops`, `services/eval-runner`, `/ops/summary`, Langfuse trace review | `tests/test_eval_runner.py::test_blocking_suite_passes` | richer metrics, eval comparison UI | Slice 05 | Ops 页面保留，eval review 转向 Langfuse UI |
| ADR-008 | TDD | §3 / p.5 | Decision | 自建 runner 分组，尽量临时化 / 一次性 | partial | `.github/workflows/validate.yml`<br>`.github/workflows/nightly-regression.yml`<br>`.github/workflows/build-verify.yml`<br>`.github/actions/setup-ci-env/action.yml` | Manual workflow review of runner labels, triggers, concurrency, and non-blocking nightly / build-verify placement | runner segmentation and lifecycle | Slice 05 | 当前已把 runner policy 固化到 blocking、nightly、build-verify 三类 workflow，但仍只有单一 self-hosted runner 池 |
| TDD-ARCH-DOMAIN-BOUNDARY | TDD | §3.1 | P0 gate | domain 不得直接依赖 DB / HTTP / Temporal / infra settings | implemented | `tools/ci/check_architecture.py` | `Makefile validate` includes architecture check | stricter import graph coverage | Slice 05 | 当前 gate 覆盖 domain/application 关键禁依赖 |
| TDD-ARCH-CONTRACT-FIRST | TDD | §3.1 | P0 gate | 同步边界走 OpenAPI；异步边界走 AsyncAPI；边界先于实现 | partial | `contracts/openapi/platform-api.openapi.yaml`<br>`contracts/asyncapi/platform-events.asyncapi.yaml`<br>`docs/CONTRACTS/index.md` | `Makefile validate` runs `check_contracts.py` | stronger async-event usage in runtime | Slice 05 | 合同在，AsyncAPI 落地有限 |
| TDD-ARCH-AI-SCHEMA | TDD | §3.1 | P0 gate | AI 输出命中明确 schema，并记录 prompt/model/input/output schema versions | partial | `agent_runs.py::_append_step` records prompt/model driven AI steps<br>`ResumeAnalysisRecord` stores prompt/model versions | No schema-version regression test | output schema version fields, contract tests | Slice 05 | AgentRun steps 已承载主链 AI 版本元数据，但 schema-version 字段仍不完整 |
| TDD-ARCH-SNAPSHOT-IMMUTABILITY | TDD | §3.1 | P0 gate | 外部简历页抓取必须快照化，不覆盖历史事实 | partial | `agent_runs.py` stores round-level step payloads and Langfuse trace data | `tests/test_api_flow.py::test_mainline_agent_flow` | retry/replay tests | Slice 05 | 当前快照语义主要体现在 round steps 和 trace，仍可进一步加硬 |
| TDD-ARCH-UNIFIED-MASKING | TDD | §3.1 | P0 gate | 导出、列表、详情、看板脱敏使用同一套字段策略 | missing | No shared field-policy module across export/list/detail/ops | None yet | shared masking policy layer | Slice 04 | 直接缺口 |

## TDD Acceptance, Error Contracts, Workflows, Idempotency, and Gates

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | TDD | §12.2 | P0 | 核心闭环由 Case/JD/Plan/AgentRun/Candidate Review/Verdict 持久化支撑 | partial | `test_api_flow.py::test_mainline_agent_flow`<br>`service.py` agent/detail/verdict methods | Mainline flow test | candidate pool and richer review surface | Slice 03 | 与 PRD AC-01 同步 |
| AC-02 | TDD | §12.2 | P0 | 通过 CTS adapter 校验明确区分 0 结果与参数异常 | validated | `adapters.py` anomaly mapping | `tests/unit/test_adapters_runtime.py::test_cts_runtime_adapter_distinguishes_param_anomaly_from_zero_results` | none | Slice 02 | 适配器级验证已存在 |
| AC-03 | TDD | §12.2 | P0 | `AI_TIMEOUT` 降级策略 + workflow / UI 规则 | missing | No `AI_TIMEOUT` path in service, worker, or UI | None yet | async AI workflow and timeout UX | Slice 03 | 直接缺口 |
| AC-04 | TDD | §12.2 | P0 | page snapshot 幂等落库 + run 重试不重复页 | partial | `agent_runs.py::_dedupe_round_candidates` suppresses repeated resumes across rounds | No retry/replay test | retry controller and tests | Slice 02 | 当前最小闭环不再生成旧页快照，幂等重点转为跨轮去重 |
| AC-05 | TDD | §12.2 | P0 | JD Version / Agent Run / Snapshot / Verdict / Audit 全链路保存 | partial | `JDVersionRecord`, `AgentRunRecord`, `VerdictHistoryRecord`, `AuditLogModel` | No replay/audit query test | admin replay views | Slice 04 | 数据基本在，回放入口不足 |
| AC-06 | TDD | §12.2 | P0 | field policy + export workflow + 审批 / reason 支撑默认脱敏导出 | partial | `create_export` supports masked vs sensitive plus reason | Sensitive-export block test only | approval flow, unified field policy | Slice 04 | 只覆盖基础限制 |
| AC-07 | TDD | §12.2 | P0 | `audit_log` + 权限模型 + 查询 API 支撑敏感动作审计 | partial | `AuditLogModel`, `_audit` | No query API test | admin audit API, role model | Slice 04 | 只实现写入半边 |
| AC-08 | TDD | §12.2 | P1 | `ops_summary_view` + metrics projection 支撑 Team Lead 看板 | partial | `service.py::get_ops_summary`<br>`ops.page.ts` | No team-lead metrics test | case/team projections | Slice 04 | 当前仅最小系统视图 |
| TDD-ERR-API-GUARDS | TDD | §6.5 + Appx A | P0 | `INVALID_PAGINATION_PARAMS`、`PLAN_NOT_CONFIRMED` 需明确阻断提交 | partial | Current minimum loop still enforces `INVALID_PAGINATION_PARAMS` in CTS adapters, but the public `PLAN_NOT_CONFIRMED` path was removed with the old plan-confirmation flow | No explicit API regression test for the remaining guard set | contract tests for current error responses | Slice 05 | 旧 `PLAN_NOT_CONFIRMED` 入口已退场，需按 AgentRun 新边界重写本条 guard 说明 |
| TDD-ERR-DEGRADE | TDD | §6.5 + Appx A | P0 | `JD_TOO_LONG`、`AI_TIMEOUT`、`CTS_TIMEOUT`、`CTS_PARAM_ANOMALY` 要有明确降级语义 | partial | `CTS_PARAM_ANOMALY` exists in `adapters.py`; other codes absent | `tests/test_api_flow.py::test_zero_results_and_parameter_anomaly_are_distinct` covers anomaly only | long-JD, AI timeout, CTS timeout handling | Slice 05 | 一组错误只实现了部分 |
| TDD-ERR-PERMISSION-IDEMPOTENCY | TDD | §6.5 + Appx A | P0 | `NO_CONTACT_PERMISSION`、`IDEMPOTENCY_CONFLICT` 需要稳定契约 | partial | `NO_CONTACT_PERMISSION` exists in `create_export`; duplicate search/export requests return existing resources instead of conflict | Sensitive-export test only | explicit duplicate semantics | Slice 05 | 权限错误在，幂等冲突契约未对齐 |
| TDD-ERR-EVAL | TDD | Appx A | P0 | `EVAL_BLOCKING_FAILED` 应阻断 CI / release gate | partial | `tools/ci/run_eval_gate.sh` surfaces `EVAL_BLOCKING_FAILED` on failure<br>`.github/workflows/nightly-regression.yml` runs the explicit eval gate before other nightly checks with `CVM_RESUME_SOURCE_MODE=mock` and `CVM_LLM_MODE=stub` | `tests/test_eval_runner.py::test_blocking_suite_passes`<br>`tests/test_eval_runner.py::test_blocking_suite_returns_failure_result_when_agent_run_fails`<br>`./tools/ci/run_eval_gate.sh` | eval-result propagation into release publishing | Slice 05 | 现在已有明确且确定性的 CI eval gate，但尚未接入单独 release 流程 |
| TDD-WF-SEARCH | TDD | §7.1 | P0 | `AgentRunWorkflow` 编排 Agent Run，支持可恢复背景执行 | validated | `services/temporal-worker/src/cvm_worker/workflows.py::AgentRunWorkflow`<br>`routes.py::create_agent_run` | `tests/test_api_stack.py::test_stack_agent_run_flow` | stop/continue signals | Slice 02 | 当前真正落地的 workflow |
| TDD-WF-AI | TDD | §7.1 | P0 | `KeywordDraftWorkflow` / `ResumeAnalysisWorkflow` 负责 AI 草案与简历分析 | partial | `workflows.py::AgentRunWorkflow` now backgrounds strategy extraction, resume analysis, and reflection inside one workflow | `tests/test_api_stack.py::test_stack_agent_run_flow` | dedicated sub-workflows or richer async state model | Slice 03 | AI 已移出请求线程，但当前使用单一 AgentRunWorkflow，而非拆分子工作流 |
| TDD-WF-DELIVERY | TDD | §7.1 | P0/P1 | `ExportWorkflow` / `EvalRunWorkflow` 支撑导出与评测 | partial | `create_export` and `create_eval_run` exist, but run synchronously in API service | `tests/test_eval_runner.py::test_blocking_suite_passes` covers blocking eval function only | actual workflows or background jobs | Slice 05 | 能力在，编排层没有按 TDD 落地 |
| TDD-IDEMPOTENCY-SEARCH-RUN | TDD | §7.2 | P0 | Agent Run 用 idempotency key 去重 | implemented | `service.py::create_agent_run`<br>`models.py` unique `idempotency_key` on `AgentRunModel` | No duplicate-key regression test | response contract for duplicates | Slice 02 | 代码层成立 |
| TDD-IDEMPOTENCY-PAGE-SNAPSHOT | TDD | §7.2 | P0 | 轮次快照与重复简历抑制必须稳定；同轮重试不重复进入 shortlist | implemented | `agent_runs.py::_dedupe_round_candidates` and shortlist rerank logic | No replay test | retry harness | Slice 02 | 约束在 |
| TDD-IDEMPOTENCY-EXPORT-EVENTS | TDD | §7.2 | P0/P1 | export job 要幂等；集成事件消费要 dedupe | partial | `create_export` checks `idempotency_key`<br>No outbox or consumer dedupe | No duplicate-export or event-consumer test | outbox_event, processed markers | Slice 05 | 只实现导出半边 |
| TDD-DAY0-GATES | TDD | §12.1 | P0 | Day 0 必须有 docs/contracts 骨架、`make validate`、CI skeleton、CODEOWNERS、AGENTS 等 | partial | `docs/`<br>`contracts/`<br>`Makefile`<br>`.github/workflows/validate.yml`<br>`.github/workflows/nightly-regression.yml`<br>`.github/workflows/build-verify.yml`<br>`.github/actions/setup-ci-env/action.yml`<br>`.github/CODEOWNERS`<br>`AGENTS.md` | `make test`<br>`make test-stack`<br>Manual workflow review for required-check layout and non-blocking post-merge workflows | runner segmentation, ontology freshness | Slice 01 | CI skeleton 现在覆盖 blocking、nightly、build verification，并把 stack gate 固定为 deterministic mock/stub 模式；`.env` 保持真实运行时配置，测试 harness 与 workflow env 显式注入 deterministic mode |
| TDD-WEEK1-GATES | TDD | §12.1 | P0 | Week 1 应完成 codegen、最小主链路、允许目录策略、Ops/Evals blocking suite | partial | `Makefile codegen`<br>`test_api_flow.py`<br>`ops.page.ts`<br>`docker-compose.yml::web-evals`<br>`.github/workflows/nightly-regression.yml`<br>`tools/ci/run_eval_gate.sh` | `tests/test_eval_runner.py::test_blocking_suite_passes`<br>`tests/test_eval_runner.py::test_blocking_suite_returns_failure_result_when_search_run_fails`<br>`./tools/ci/run_eval_gate.sh` | single-shell alignment, context-pack discipline | Slice 05 | 现有 blocking eval 已进入 nightly CI gate，且 deterministic mock/stub 由测试 harness 与 workflow env 统一注入，但仍不是 PR required check，整体仓库形态与 TDD 仍有差距 |
| TDD-HARD-RULES | TDD | Appx B | P0 | 不得绕过 `contracts/` 改 DTO；不得在 domain 引 infra；不得手改 generated | partial | `AGENTS.md` hard rules<br>`tools/ci/check_architecture.py`<br>`Makefile validate` with `check_generated_clean.py` | No policy-specific regression test | stronger CI policy checks | Slice 05 | 规则和部分 gate 在，覆盖仍可加硬 |

## Execution Plan Mapping Snapshot

| Plan | Current Mapping | Disposition |
| --- | --- | --- |
| `docs/EXEC-PLANS/completed/bootstrap-plan.md` | Broadly overlaps `ADR-001`, `ADR-005`, `ADR-006`, `ADR-007`, `TDD-DAY0-GATES`, `TDD-WEEK1-GATES` | Completed historical bootstrap note; successor execution now lives in Slice 02-05 |
| `docs/EXEC-PLANS/completed/dependency-governance-plan.md` | Mostly maps to `ADR-001`, `ADR-006`, `TDD-ARCH-DOMAIN-BOUNDARY`, `TDD-HARD-RULES`, parts of `TDD-DAY0-GATES` | Completed thematic dependency hardening baseline; remaining functional work continues in Slice 02 and Slice 05 |
| `docs/EXEC-PLANS/completed/ci-pipeline-hardening-plan.md` | Maps to `ADR-008`, `TDD-ERR-EVAL`, `TDD-DAY0-GATES`, and `TDD-WEEK1-GATES` | Completed CI hardening slice; remaining harness and eval capability work continues in Slice 05 |
| `docs/EXEC-PLANS/completed/hard-harness-plan.md` | Mostly maps to `ADR-006`, `ADR-007`, `TDD-ERR-*`, `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-07`, `TDD-HARD-RULES` | Completed hard-harness baseline; remaining product-facing ops, audit, and harness work continues in Slice 04 and Slice 05 |
| `docs/EXEC-PLANS/completed/mvp-slice-01-governance-plan.md` | Governance slice for traceability, execution-plan contract, and slice partitioning | Completed governance slice; successor execution sources are Slice 02-05 |
| `docs/EXEC-PLANS/active/mvp-slice-02-jd-kw-agent-run-plan.md` | Exact row set already tagged `Slice 02` in this document | Current execution source for JD / KW / Agent Run mainline closure |
| `docs/EXEC-PLANS/active/mvp-agent-minimum-loop-plan.md` | Extracted execution wedge across selected Slice 02, Slice 03, and Slice 05 rows for `JD + 寻访偏好 -> multi-round CTS search -> dedupe -> top 5 shortlist with reasons`, with a backend-first thread and a separate frontend rebuild thread | Current short-path execution source for the minimum end-to-end agent closure; it does not retag owning rows |
| `docs/EXEC-PLANS/active/mvp-slice-03-list-detail-verdict-plan.md` | Exact row set already tagged `Slice 03` in this document | Primary execution source for broader list / detail / verdict and AI degrade work; the minimum agent loop is temporarily extracted into `mvp-agent-minimum-loop-plan.md` |
| `docs/EXEC-PLANS/active/mvp-slice-04-export-audit-ops-plan.md` | Exact row set already tagged `Slice 04` in this document | Current execution source for export / audit / ops and unified masking |
| `docs/EXEC-PLANS/active/mvp-slice-05-harness-evals-gates-plan.md` | Exact row set already tagged `Slice 05` in this document | Primary execution source for harness / evals / gates and remaining architecture hardening; the minimum agent loop is temporarily extracted into `mvp-agent-minimum-loop-plan.md` |
