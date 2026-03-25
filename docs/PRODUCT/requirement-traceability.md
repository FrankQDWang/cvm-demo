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
- `services/platform-api/src/cvm_platform/infrastructure/models.py`
- `services/temporal-worker/src/cvm_worker/workflows.py`
- `services/eval-runner/src/cvm_eval_runner/cli.py`
- `apps/web-user/src/app/features/cases/cases.page.ts`
- `apps/web-ops/src/app/features/ops/ops.page.ts`
- `apps/web-evals/src/app/features/evals/evals.page.ts`
- `tests/test_api_flow.py`
- `tests/test_api_stack.py`
- `tests/test_eval_runner.py`
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

## PRD Goals, JD, Keywords, and Search Run

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | PRD | §1.2 | Goal | JD 到首批候选列表更快；从录入到首批候选中位耗时 ≤ 5 分钟 | partial | `routes.py::create_case`<br>`routes.py::create_search_run`<br>`tests/test_api_flow.py::test_mainline_flow` | Mainline flow exists; no timed SLO check | latency measurement, timed evals | Slice 02 | 流程在，目标度量缺失 |
| G2 | PRD | §1.2 | Goal | 首轮筛查效率提升 ≥ 30% | missing | `service.py::save_verdict` stores outcomes but no funnel metric | None yet | funnel definition, baseline dataset, ops metrics | Slice 03 | 只有 verdict 数据，没有效率口径 |
| G3 | PRD | §1.2 | Goal | AI 草案被真正使用；草案采纳率 ≥ 70% | partial | `service.py::create_keyword_draft_job`<br>`cases.page.ts` step 2 | No adoption metric or telemetry | adoption telemetry, analytics events | Slice 02 | 草案存在，使用率未测 |
| G4 | PRD | §1.2 | Goal | 流程稳定可恢复；Run 完成率 ≥ 95%，异常可重试且不丢页 | partial | `service.py::execute_search_run`<br>`models.py` unique `run_id,page_no`<br>`workflows.py::SearchRunWorkflow` | `tests/test_api_stack.py::test_stack_mainline_flow` | retry controls, partial status model | Slice 02 | 有快照和 Temporal，重试/恢复语义不足 |
| G5 | PRD | §1.2 | Goal | 审计与合规可落地；敏感动作审计覆盖率 100%，默认脱敏导出 | partial | `service.py::_audit`<br>`service.py::create_export` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | admin audit query, role model, download audit | Slice 04 | 默认脱敏有证据，审计覆盖不完整 |
| G6 | PRD | §1.2 | Goal | AI 异常不阻塞业务；AI 不可用时主流程仍可手工完成 | partial | `cases.page.ts` lets users edit conditions manually<br>`service.py::_upsert_candidate` builds stub analysis | No explicit AI timeout/degrade test | timeout handling, async AI modules | Slice 03 | 手工编辑可继续，但 AI 降级契约未完整实现 |
| JD-01 | PRD | §4.1 | P0 | 支持创建、保存、归档 JD Case；创建后默认草稿 | partial | `service.py::create_case`<br>`routes.py::create_case`<br>`cases.page.ts` step 1 | `tests/test_api_flow.py::bootstrap_case_flow` covers create only | archive behavior, case list UI | Slice 02 | 创建/保存在，归档缺失 |
| JD-02 | PRD | §4.1 | P0 | 修改激活 JD 时创建新版本，不改写历史版本 | implemented | `service.py::create_jd_version`<br>`sqlalchemy_uow.py::deactivate_versions` | No targeted version-history test | version-history UI, history assertions | Slice 02 | 代码按新版本写入，未见专项验证 |
| JD-03 | PRD | §4.1 | P0 | 同一时间只有一个激活 JD 版本可发起新检索 | implemented | `service.py::create_jd_version` sets `is_active=True`<br>`sqlalchemy_uow.py::deactivate_versions` | No targeted active-version test | active-version read model | Slice 02 | 持久层有唯一激活语义 |
| JD-04 | PRD | §4.1 | P1 | 离开页面前提示未保存修改 | missing | `cases.page.ts` has no dirty-form or unload guard | None yet | UI state tracking | Slice 02 | 直接缺口 |
| JD-05 | PRD | §4.1 | P0 | JD 超长时不得静默截断；提示精简或智能精简 | missing | `service.py::create_jd_version` stores raw text unchanged; no `JD_TOO_LONG` path | None yet | long-JD contract, condense flow | Slice 02 | 规范存在，代码无对应 |
| JD-06 | PRD | §4.1 | P0 | 无有效激活版本时不允许发起 Search Run | partial | `cases.page.ts` disables draft generation until `jdVersionId` exists<br>`service.py::create_search_run` only checks confirmed plan | No direct invalid-version test | active-version guard at API boundary | Slice 02 | 通过 plan 间接约束，不是显式规则 |
| KW-01 | PRD | §4.2 | P0 | 基于激活 JD 生成结构化关键词与条件草案 | implemented | `service.py::create_keyword_draft_job`<br>`routes.py::create_keyword_draft_job` | `tests/test_api_flow.py::bootstrap_case_flow` | richer prompt/schema coverage | Slice 02 | 草案结构已落库 |
| KW-02 | PRD | §4.2 | P0 | 每条 AI 关键词/条件显示提取依据 | partial | `service.py::_draft_to_payload` stores `evidence_refs`<br>`ConfirmConditionPlanRequest` carries `evidenceRefs` | No UI test proving evidence display | evidence UI, human-readable rationale | Slice 02 | 后端有证据结构，前端未直接呈现 |
| KW-03 | PRD | §4.2 | P0 | 用户可新增、删除、移动、合并、去重、手工改写关键词 | partial | `cases.page.ts` allows raw textarea editing<br>`service.py::confirm_condition_plan` persists edited payload | Mainline flow confirms edited payload, but no move/merge/dedupe test | richer condition-builder UI | Slice 02 | 手工改写可做，结构化编辑器不足 |
| KW-04 | PRD | §4.2 | P1 | 支持多套查询方案并显式选择其一 | missing | `service.py::create_keyword_draft_job` creates one plan per draft | None yet | multi-plan model and UI | Slice 02 | 直接缺口 |
| KW-05 | PRD | §4.2 | P0 | 发起检索前必须有一次用户确认动作；不得后台自动起 Run | implemented | `service.py::confirm_condition_plan`<br>`service.py::create_search_run` rejects unconfirmed plan<br>`cases.page.ts` disables run button until confirmed | No direct `PLAN_NOT_CONFIRMED` API test | explicit actor audit in API tests | Slice 02 | 规则已编码，缺少专项验证 |
| KW-06 | PRD | §4.2 | P0 | 关键词冲突时提示修正；未处理前不允许发起 Run | missing | `confirm_condition_plan` has no conflict-detection branch | None yet | conflict validation rules | Slice 02 | 直接缺口 |
| KW-07 | PRD | §4.2 | P0 | AI 草案超过 10 秒仍需保留手工编辑可用并允许重试 | missing | Draft generation is synchronous in `service.py::create_keyword_draft_job` | None yet | async draft workflow, timeout UX | Slice 03 | 直接缺口 |
| KW-08 | PRD | §4.2 | P1 | JD 超上下文预算时先给智能精简摘要再生成草案 | missing | No condense step in service or UI | None yet | condense workflow, summary approval UI | Slice 03 | 直接缺口 |
| SR-01 | PRD | §4.3 | P0 | Search Run 冻结发起人、JD 版本、条件方案、时间与状态 | partial | `service.py::create_search_run` stores case/plan/time/status/idempotency | `tests/test_api_flow.py::test_mainline_flow` covers creation path | actor attribution, jd-version snapshot exposure | Slice 02 | 关键字段在，发起人暴露不足 |
| SR-02 | PRD | §4.3 | P0 | 默认首批固定页数；继续翻页必须用户显式触发 | partial | `service.py::create_search_run` accepts `pageBudget`<br>`cases.page.ts` edits `pageBudgetText` | Mainline run proves one-page path only | default budget, continue/stop actions | Slice 02 | 有 page budget，无默认 3 页与继续翻页动作 |
| SR-03 | PRD | §4.3 | P0 | 部分页失败不影响已返回页使用 | partial | `service.py::_persist_page` commits pages before later failure | No targeted partial-failure test | retry UI, partial-complete status | Slice 02 | 快照先落库，但状态语义偏弱 |
| SR-04 | PRD | §4.3 | P0 | 明确区分 0 结果与参数异常 | validated | `adapters.py` returns `CTS_PARAM_ANOMALY` for invalid paging<br>`routes.py::get_search_run_pages` exposes error fields | `tests/test_api_flow.py::test_zero_results_and_parameter_anomaly_are_distinct` | none | Slice 02 | 当前最明确的一条已验证链路 |
| SR-05 | PRD | §4.3 | P0 | 展示 Run 状态、进度、失败原因，便于决定重试/继续翻页 | implemented | `routes.py::get_search_run`<br>`routes.py::get_search_run_pages`<br>`cases.page.ts` run status banner | No targeted UI/status test | retry/continue actions | Slice 02 | 状态展示有，操作闭环不足 |
| SR-06 | PRD | §4.3 | P0 | Search Run 创建需支持幂等 | implemented | `service.py::create_search_run` checks `idempotency_key`<br>`models.py` unique `idempotency_key` | No duplicate-request test | explicit conflict/echo contract | Slice 02 | 行为存在，但未验证返回语义 |
| SR-07 | PRD | §4.3 | P0 | 同页重试成功不得重复生成页快照或候选 | implemented | `models.py` unique `run_id,page_no`<br>`service.py::_persist_page` upserts candidates by case + external identity | No retry/replay test | retry controller, replay test | Slice 02 | 持久层约束在，未做回放验证 |
| SR-08 | PRD | §4.3 | P1 | 来源接口有未知新字段时保留原始快照并继续展示已知字段 | partial | `SearchRunPageRecord` stores `upstream_response` raw JSON<br>`routes.py::get_search_run_pages` only exposes normalized known fields | No unknown-field regression test | raw-snapshot viewer, adapter fuzz tests | Slice 05 | 原始快照会保存，兼容性未验证 |
| SR-09 | PRD | §4.3 | P1 | 用户可主动停止剩余页抓取；已返回结果保留 | missing | `SearchRunWorkflow` has no stop signal<br>`cases.page.ts` has no stop action | None yet | Temporal signal, run state expansion | Slice 02 | 直接缺口 |

## PRD List, Detail, Verdict, Export, Audit, Ops, and Evals

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LI-01 | PRD | §4.4 | P0 | 候选列表以当前 Search Run 快照为边界，不跨 Run 混排 | implemented | `routes.py::get_search_run_pages` only reads by `run_id`<br>`cases.page.ts` renders per-snapshot candidates | `tests/test_api_flow.py::test_mainline_flow` reads current run pages | run comparison UI | Slice 03 | 快照边界明确 |
| LI-02 | PRD | §4.4 | P0 | 列表默认显示最小必要字段，联系方式默认不展示 | partial | `cases.page.ts` candidate button shows name/title/company only | No targeted UI field test | richer card projection, review state | Slice 03 | 联系方式没露出，但字段集不完整 |
| LI-03 | PRD | §4.4 | P0 | 高亮命中必须项/加分项并标记缺失必须项 | missing | No hit-highlighting logic in `cases.page.ts` or candidate card payload | None yet | match explanation model | Slice 03 | 直接缺口 |
| LI-04 | PRD | §4.4 | P1 | 支持按 verdict、命中完整度、疑似重复、本地排序筛选列表 | missing | No list filter controls in `cases.page.ts` | None yet | filter model, client state | Slice 03 | 直接缺口 |
| LI-05 | PRD | §4.4 | P1 | 详情返回列表时保留滚动位置、筛选条件、选中页 | missing | `cases.page.ts` has no router-state or scroll preservation | None yet | route state, UI state model | Slice 03 | 直接缺口 |
| LI-06 | PRD | §4.4 | P0 | 来源字段缺失统一显示“未提供”，不得报错 | partial | `cases.page.ts` uses fallback text in detail lists and resume blocks | No targeted missing-field test | card-level fallback coverage | Slice 03 | 详情有兜底，列表未完全覆盖 |
| CD-01 | PRD | §4.5 | P0 | 候选详情展示简历主要区块，敏感字段按角色处理 | partial | `routes.py::_candidate_detail_response`<br>`cases.page.ts` detail/resume blocks | `tests/test_api_flow.py::test_mainline_flow` loads detail | role-based masking, source-field projection | Slice 03 | 区块大体在，角色处理不足 |
| CD-02 | PRD | §4.5 | P0 | AI 面板输出“满足/部分满足/缺失证据/需人工核实”检查清单 | partial | `ResumeAnalysis` carries `summary`, `evidenceSpans`, `riskFlags` | No checklist-format test | structured checklist schema | Slice 03 | 有分析对象，无标准检查清单 |
| CD-03 | PRD | §4.5 | P0 | AI 每条结论必须关联证据；无证据需标“无直接证据” | partial | `service.py::_candidate_evidence_spans` populates evidence spans | No proof for no-evidence labeling | evidence labeling rules | Slice 03 | 有证据片段，无“无直接证据”契约 |
| CD-04 | PRD | §4.5 | P0 | 原始简历内容优先加载，AI 面板异步非阻塞 | partial | `routes.py::get_case_candidate` returns resume + aiAnalysis together | No async-loading or degrade test | split detail loading path | Slice 03 | 当前是同步聚合返回 |
| CD-05 | PRD | §4.5 | P1 | 证据片段可一键插入 verdict 备注 | missing | No insert-evidence interaction in `cases.page.ts` | None yet | verdict composer UX | Slice 03 | 直接缺口 |
| CD-06 | PRD | §4.5 | P0 | AI 辅助超过 10 秒应提示可重试且不锁死详情页 | missing | No timeout/retry branch for detail AI analysis | None yet | async analysis job, timeout UX | Slice 03 | 直接缺口 |
| CD-07 | PRD | §4.5 | P0 | 简历过长或结构异常时分段折叠并以“未提供”兜底 | partial | `cases.page.ts` uses sectional lists and fallbacks | No long-resume stress test | segmented resume renderer | Slice 03 | 有基础兜底，无长简历折叠 |
| RV-01 | PRD | §4.6 | P0 | 顾问显式提交 Match / Maybe / No；AI 不得代提 | implemented | `cases.page.ts` verdict buttons<br>`routes.py::save_verdict` | `tests/test_api_flow.py::test_mainline_flow` covers `Match` path only | broader tri-state tests | Slice 03 | 显式提交在，三态未全验 |
| RV-02 | PRD | §4.6 | P0 | verdict=No 时必须有原因标签或手工原因 | missing | `service.py::save_verdict` accepts empty `reasons` and `notes` | None yet | No-verdict validation rule | Slice 03 | 直接缺口 |
| RV-03 | PRD | §4.6 | P0 | Match / Maybe 支持加入 Case 级候选池并保留来源 Run/理由 | partial | `service.py::save_verdict` updates `latest_verdict`<br>`service.py::create_export` exports `Match/Maybe` candidates | Mainline flow proves verdict persistence, not explicit pool UI | candidate pool read model and UI | Slice 03 | 有池化效果，无独立候选池对象/UI |
| RV-04 | PRD | §4.6 | P0 | 同一候选每次 verdict 修改都留历史，展示最新有效 verdict | implemented | `service.py::save_verdict` appends `VerdictHistoryRecord`<br>`routes.py::_candidate_detail_response` returns history | No repeated-edit test | repeated-update test | Slice 03 | append-only 语义已编码 |
| RV-05 | PRD | §4.6 | P1 | 不同用户冲突 verdict 需显著提示 | missing | No conflict-detection logic in service or UI | None yet | reviewer identity model, conflict projection | Slice 03 | 直接缺口 |
| RV-06 | PRD | §4.6 | P0 | 从候选池移除不删除历史检索与 verdict 记录 | missing | No pool-removal operation exists | None yet | pool lifecycle model | Slice 03 | 缺少“移除但保留历史”能力 |
| EX-01 | PRD | §4.7 | P0 | 支持按条件导出候选池到 CSV | validated | `service.py::create_export` writes CSV<br>`service.py::_write_export_file` | `tests/test_api_flow.py::test_mainline_flow` | none | Slice 04 | CSV 导出已跑通 |
| EX-02 | PRD | §4.7 | P0 | 默认脱敏导出；敏感字段需权限和原因 | validated | `service.py::create_export` enforces `NO_CONTACT_PERMISSION`<br>`cases.page.ts` only triggers masked export | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | approval workflow, field-level policy | Slice 04 | 当前只覆盖本地模式禁止敏感导出 |
| EX-03 | PRD | §4.7 | P0 | 导出为异步任务，导出中心可看生成中/完成/失败 | partial | `ExportJobRecord` has status fields<br>`service.py::create_export` updates running/completed/failed | No async export-center test | async export worker, export center UI | Slice 04 | 有状态字段，执行仍同步发生在请求内 |
| EX-04 | PRD | §4.7 | P0 | 导出任务记录发起人、时间、Case、条件、字段范围、下载行为 | partial | `ExportJobRecord` stores case, reason, status, times<br>`_audit` writes export completion | No download-audit or actor-identity test | export metadata expansion, download audit | Slice 04 | 留痕不完整 |
| EX-05 | PRD | §4.7 | P1 | 导出文件默认 7 天过期 | missing | `service.py::_build_export_path` writes plain path; no TTL policy | None yet | expiry scheduler, signed access policy | Slice 04 | 直接缺口 |
| EX-06 | PRD | §4.7 | P1 | 导出失败显示原因并支持原条件重试 | partial | `service.py::create_export` marks failure with `EXPORT_FAILED` | No retry surface or test | retry endpoint/UI | Slice 04 | 失败状态在，重试闭环不足 |
| LD-01 | PRD | §4.8 | P1 | 团队看板展示 Case 数、运行中 Run、候选打开数、Match/Maybe、失败分布 | partial | `routes.py::get_ops_summary`<br>`apps/web-ops/.../ops.page.ts` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` asserts ops summary version fields | case/team projections, candidate-open audit | Slice 04 | 当前更像系统运行总览，不是 Team Lead 看板 |
| LD-02 | PRD | §4.8 | P1 | 可按顾问、Case、时间范围筛选并查看趋势 | missing | No filterable team dashboard route or UI | None yet | team model, time-series projections | Slice 04 | 直接缺口 |
| LD-03 | PRD | §4.8 | P1 | 同一 Case 的不同 JD 版本 / Search Run 可并排对比 | missing | No compare view in API or UI | None yet | comparison read model | Slice 04 | 直接缺口 |
| LD-04 | PRD | §4.8 | P0 | Team Lead 复核或修订 verdict 必须留痕 | missing | `save_verdict` records actor, but no lead-review flow | None yet | team-role review workflow | Slice 04 | 基础留痕在，复核能力缺失 |
| AU-01 | PRD | §4.9 | P0 | 审计登录、Case、条件确认、Run、打开候选、verdict、导出/下载等敏感动作 | partial | `service.py::_audit` logs case/jd/plan/run/verdict/export/eval events<br>`AuditLogModel` exists | No coverage audit proving all required actions | auth events, candidate-open audit, download audit | Slice 04 | 审计基础在，覆盖率远未到 100% |
| AU-02 | PRD | §4.9 | P0 | 管理员可按人、Case、时间、动作类型、导出任务查询审计日志 | missing | No audit query route in `routes.py` | None yet | admin audit API and UI | Slice 04 | 直接缺口 |
| AU-03 | PRD | §4.9 | P0 | 审计日志只增不改，普通业务页面不可编辑 | implemented | `AuditLogRepository` only exposes `save_audit_log`<br>No audit update route in `routes.py` | No explicit immutability test | DB-level guard, admin surface | Slice 04 | 当前 API 面未提供编辑路径 |
| AU-04 | PRD | §4.9 | P0 | 列表、详情、导出、看板的字段脱敏规则一致 | missing | Export path masks sensitive export; list/detail/ops use separate projections | None yet | shared field policy layer | Slice 04 | 统一脱敏策略尚未建立 |
| AU-05 | PRD | §4.9 | P0 | 权限不足时给明确拒绝信息但不泄露敏感内容 | partial | `NO_CONTACT_PERMISSION` in `service.py::create_export` | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | broader permission model, detail masking | Slice 04 | 导出场景成立，其它敏感入口不足 |
| OP-01 | PRD | §4.10 | P1 | 运行监控页看到排队、失败、超时任务及原因分类 | partial | `routes.py::get_ops_summary`<br>`ops.page.ts` summary and diagnostics | No timeout-category test | queue/timeout projections | Slice 04 | 有总览和 diagnostics，无完整任务分类 |
| OP-02 | PRD | §4.10 | P1 | 支持按版本查看 AI 命中率、AI 超时率、Run 完成率 | partial | `OpsSummaryResponse.version` exposes build/version data | No version-metrics test | `ai_version_metrics` projection | Slice 04 | 版本元数据在，效果指标不在 |
| EV-01 | PRD | §4.10 | P2 | 内部评测页比较不同提示词/模型版本效果 | partial | `routes.py::create_eval_run`<br>`evals.page.ts`<br>`cli.py::run_blocking_suite` | `tests/test_eval_runner.py::test_blocking_suite_passes` | dataset/version comparison, non-blocking suites | Slice 05 | 仅 blocking suite 触发器，不是对比平台 |

## PRD Acceptance and Non-Functional Requirements

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | PRD | §7.2 | P0 | 在一个 Case 内完成 JD -> 条件 -> Run -> 浏览候选 -> verdict -> 候选池闭环 | partial | `test_api_flow.py::test_mainline_flow` covers create -> draft -> confirm -> run -> detail -> verdict -> export | Mainline flow test exists | explicit candidate-pool UI/model | Slice 03 | 闭环大体在，候选池仍是隐式效果 |
| AC-02 | PRD | §7.2 | P0 | 明确区分 0 结果和参数异常 | validated | `adapters.py` anomaly mapping<br>`routes.py::get_search_run_pages` | `tests/test_api_flow.py::test_zero_results_and_parameter_anomaly_are_distinct` | none | Slice 02 | 已有端到端验证 |
| AC-03 | PRD | §7.2 | P0 | AI 草案或 AI 简历分析失败时仍可手工继续 | partial | `cases.page.ts` keeps manual condition textareas editable | No timeout/failure-path test | async AI failures, degrade UX | Slice 03 | 手工路径在，失败契约不足 |
| AC-04 | PRD | §7.2 | P0 | Run 中断后成功页可查看，重试不重复生成页 | partial | `_persist_page` commits before completion<br>`models.py` unique `run_id,page_no` | No retry/interruption regression test | retry controller and tests | Slice 02 | 核心数据约束在，恢复动作不足 |
| AC-05 | PRD | §7.2 | P0 | 历史 Search Run、JD 版本、verdict 记录可完整复盘 | partial | `JDVersionRecord`, `SearchRunRecord`, `VerdictHistoryRecord`, `AuditLogModel` all exist | No holistic replay or audit query test | history UI, audit query API | Slice 04 | 数据基础在，复盘入口不足 |
| AC-06 | PRD | §7.2 | P0 | 导出默认脱敏；敏感导出受权限与原因校验约束 | partial | `create_export` enforces masked/sensitive split and reason | `tests/test_api_flow.py::test_sensitive_export_is_blocked_in_local_mode` | approval rules, field policy | Slice 04 | 基础限制有，审批未建 |
| AC-07 | PRD | §7.2 | P0 | 管理员可查敏感动作审计日志 | partial | `AuditLogModel` and `_audit` exist | No admin query test | audit query/read model | Slice 04 | 写入基础在，查询缺口大 |
| AC-08 | PRD | §7.2 | P1 | Team Lead 可看 Case 数、运行中任务、候选打开量、Match/Maybe、失败分布 | partial | `get_ops_summary` exposes run/failure/latency/version data | No team-lead dashboard test | team metrics and role filters | Slice 04 | 当前更像系统 ops summary |
| PRD-NFR-PERFORMANCE | PRD | §6.1 | P0 | Search Run 提交 2 秒内返回明确状态；首批结果页与详情原始简历有 SLO；AI 超时 10 秒自动降级 | partial | `routes.py::create_search_run` returns queued status immediately<br>`routes.py::get_case_candidate` returns detail payload | No latency or timeout benchmark | timing instrumentation, async AI timeout handling | Slice 05 | 返回快，但没有正式 SLO/降级证明 |
| PRD-NFR-RELIABILITY | PRD | §6.1 | P0 | 成功快照、verdict、导出审计不能丢失或重复；异常重试有上限且转为可见失败 | partial | `models.py` unique constraints on pages/export idempotency<br>`service.py::save_verdict` append-only history | No bounded-retry test | retry policy and failure-state model | Slice 05 | 数据约束有，重试策略未闭环 |
| PRD-NFR-CAPACITY | PRD | §6.1 | P0/P1 | 至少 50 并发 Search Run / 100 并发详情 AI；超载时排队且不阻塞已返回结果浏览 | missing | No capacity controls or load tests in repo | None yet | queueing model, load tests | Slice 05 | 直接缺口 |
| PRD-NFR-SECURITY | PRD | §6.1 | P0 | 敏感字段默认脱敏；导出、下载、查看敏感字段都纳入审计 | partial | `create_export` masks by policy and blocks sensitive export locally<br>`_audit` exists | Sensitive export block test only | role-boundary model, download/view audit | Slice 04 | 安全边界只覆盖一部分入口 |
| PRD-NFR-RETENTION | PRD | §6.1 | P1 | 导出文件 7 天过期；审计日志至少保留 180 天 | missing | No TTL or retention policy in export/audit code | None yet | retention scheduler, lifecycle policy | Slice 04 | 直接缺口 |
| PRD-NFR-TRACEABILITY | PRD | §6.1 | P0 | AI 输出带来源版本和证据引用；Run 可定位到 JD 版本和条件方案版本 | partial | `KeywordDraftJobRecord` and `ResumeAnalysisRecord` store model/prompt versions<br>`SearchRunRecord` links plan | No end-to-end replay proof | output schema versioning, audit queries | Slice 05 | 版本字段有，但全链路回放不足 |
| PRD-NFR-OPERABILITY | PRD | §6.1 | P1 | 内部页面看到 Run 完成率、AI 超时率、导出失败率、主要错误分类 | partial | `OpsSummaryResponse` includes queue/failures/latency/version | No rate-metric test | derived metrics and ops projections | Slice 04 | 错误分布部分在，完成率/AI 超时率缺 |
| PRD-NFR-USABILITY | PRD | §6.1 | P1 | 核心表单支持粘贴、键盘切换、明确空态/加载态/错误态 | partial | `cases.page.ts` and `ops.page.ts` have empty/error banners and form controls | No UX interaction test | keyboard flows, loading states, accessibility checks | Slice 03 | 空态/错误态有，键盘体验未验证 |

## TDD ADRs and Core Engineering Rules

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADR-001 | TDD | §3 / p.5 | Decision | 模块化单体 + 独立 worker；Day 0 不拆微服务 | implemented | `services/platform-api` + `services/temporal-worker` repo shape | `docs/ARCHITECTURE/context-map.md` reflects modular monolith | none | Slice 05 | 当前形态符合 ADR |
| ADR-002 | TDD | §3 / p.5 | Decision | 单一 Angular shell + 路由域隔离，不起四个独立前端应用 | conflict | `docs/ARCHITECTURE/context-map.md` lists `apps/web-user`, `apps/web-ops`, `apps/web-evals` | None yet | architecture decision reset or consolidation plan | Slice 05 | 当前仓库与 ADR 明显冲突 |
| ADR-003 | TDD | §3 / p.5 | Decision | Postgres 写模型 + 读投影 + outbox；不先上 Redis/Kafka/Elastic | partial | Postgres-first repo shape and SQLAlchemy models exist; no outbox tables or publisher | No outbox/projection validation | outbox/event publisher, read models | Slice 05 | 只实现了前半段 |
| ADR-004 | TDD | §3 / p.5 | Decision | Temporal 只编排长流程；不是所有请求都进 workflow | implemented | `SearchRunWorkflow` only long-running path; CRUD routes remain sync | `tests/test_api_stack.py::test_stack_mainline_flow` | none | Slice 05 | 当前用法符合 ADR |
| ADR-005 | TDD | §3 / p.5 | Decision | `docs/` 作为知识事实源并兼作 Obsidian 内容根 | partial | `docs/00-INDEX.md` and docs tree exist | `Makefile validate` runs `tools/ci/check_links.py` | docs freshness automation | Slice 01 | 有 docs SSOT 基础，刷新度校验还偏轻 |
| ADR-006 | TDD | §3 / p.5 | Decision | DTO / client 由合同生成；不手写边界模型双写 | partial | `contracts/` plus generated libs exist<br>`Makefile codegen` | `Makefile validate` runs codegen and generated-clean checks | boundary-model cleanup, codegen hygiene | Slice 05 | 生成链在，但仍有手写 boundary models |
| ADR-007 | TDD | §3 / p.5 | Decision | Ops / Evals 从 Day 0 起建最小骨架 | partial | `apps/web-ops`, `apps/web-evals`, `/ops/summary`, `/evals/runs` | `tests/test_eval_runner.py::test_blocking_suite_passes` | richer metrics, eval comparison UI | Slice 05 | 骨架在，平台能力很薄 |
| ADR-008 | TDD | §3 / p.5 | Decision | 自建 runner 分组，尽量临时化 / 一次性 | partial | `.github/workflows/validate.yml`<br>`.github/workflows/nightly-regression.yml`<br>`.github/workflows/build-verify.yml`<br>`.github/actions/setup-ci-env/action.yml` | Manual workflow review of runner labels, triggers, concurrency, and non-blocking nightly / build-verify placement | runner segmentation and lifecycle | Slice 05 | 当前已把 runner policy 固化到 blocking、nightly、build-verify 三类 workflow，但仍只有单一 self-hosted runner 池 |
| TDD-ARCH-DOMAIN-BOUNDARY | TDD | §3.1 | P0 gate | domain 不得直接依赖 DB / HTTP / Temporal / infra settings | implemented | `tools/ci/check_architecture.py` | `Makefile validate` includes architecture check | stricter import graph coverage | Slice 05 | 当前 gate 覆盖 domain/application 关键禁依赖 |
| TDD-ARCH-CONTRACT-FIRST | TDD | §3.1 | P0 gate | 同步边界走 OpenAPI；异步边界走 AsyncAPI；边界先于实现 | partial | `contracts/openapi/platform-api.openapi.yaml`<br>`contracts/asyncapi/platform-events.asyncapi.yaml`<br>`docs/CONTRACTS/index.md` | `Makefile validate` runs `check_contracts.py` | stronger async-event usage in runtime | Slice 05 | 合同在，AsyncAPI 落地有限 |
| TDD-ARCH-AI-SCHEMA | TDD | §3.1 | P0 gate | AI 输出命中明确 schema，并记录 prompt/model/input/output schema versions | partial | `KeywordDraftJobRecord` / `ResumeAnalysisRecord` store prompt/model versions | No schema-version or timeout regression test | output schema version fields, contract tests | Slice 05 | 版本字段部分在，schema-version 不完整 |
| TDD-ARCH-SNAPSHOT-IMMUTABILITY | TDD | §3.1 | P0 gate | 外部简历页抓取必须快照化，不覆盖历史事实 | implemented | `SearchRunPageRecord` raw request/response fields<br>`models.py` unique `run_id,page_no` | `tests/test_api_flow.py::test_mainline_flow` confirms snapshot retrieval | retry/replay tests | Slice 05 | 不可变快照语义已基本成立 |
| TDD-ARCH-UNIFIED-MASKING | TDD | §3.1 | P0 gate | 导出、列表、详情、看板脱敏使用同一套字段策略 | missing | No shared field-policy module across export/list/detail/ops | None yet | shared masking policy layer | Slice 04 | 直接缺口 |

## TDD Acceptance, Error Contracts, Workflows, Idempotency, and Gates

| Source ID | Source Doc | Section/Page | Priority | Requirement Summary | Current Status | Repo Evidence | Validation Evidence | Blocking Dependencies | Target Slice | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | TDD | §12.2 | P0 | 核心闭环由 Case/JD/Plan/SearchRun/Candidate Review/Verdict 持久化支撑 | partial | `test_api_flow.py::test_mainline_flow`<br>`service.py` case/plan/run/detail/verdict methods | Mainline flow test | candidate pool and richer review surface | Slice 03 | 与 PRD AC-01 同步 |
| AC-02 | TDD | §12.2 | P0 | 通过 CTS adapter 校验明确区分 0 结果与参数异常 | validated | `adapters.py` anomaly mapping | `tests/test_api_flow.py::test_zero_results_and_parameter_anomaly_are_distinct` | none | Slice 02 | 已有直接验证 |
| AC-03 | TDD | §12.2 | P0 | `AI_TIMEOUT` 降级策略 + workflow / UI 规则 | missing | No `AI_TIMEOUT` path in service, worker, or UI | None yet | async AI workflow and timeout UX | Slice 03 | 直接缺口 |
| AC-04 | TDD | §12.2 | P0 | page snapshot 幂等落库 + run 重试不重复页 | partial | `models.py` unique `run_id,page_no`<br>`service.py::_persist_page` | No retry/replay test | retry controller and tests | Slice 02 | 约束在，重试链不足 |
| AC-05 | TDD | §12.2 | P0 | JD Version / Search Run / Snapshot / Verdict / Audit 全链路保存 | partial | `JDVersionRecord`, `SearchRunPageRecord`, `VerdictHistoryRecord`, `AuditLogModel` | No replay/audit query test | admin replay views | Slice 04 | 数据基本在，回放入口不足 |
| AC-06 | TDD | §12.2 | P0 | field policy + export workflow + 审批 / reason 支撑默认脱敏导出 | partial | `create_export` supports masked vs sensitive plus reason | Sensitive-export block test only | approval flow, unified field policy | Slice 04 | 只覆盖基础限制 |
| AC-07 | TDD | §12.2 | P0 | `audit_log` + 权限模型 + 查询 API 支撑敏感动作审计 | partial | `AuditLogModel`, `_audit` | No query API test | admin audit API, role model | Slice 04 | 只实现写入半边 |
| AC-08 | TDD | §12.2 | P1 | `ops_summary_view` + metrics projection 支撑 Team Lead 看板 | partial | `service.py::get_ops_summary`<br>`ops.page.ts` | No team-lead metrics test | case/team projections | Slice 04 | 当前仅最小系统视图 |
| TDD-ERR-API-GUARDS | TDD | §6.5 + Appx A | P0 | `INVALID_PAGINATION_PARAMS`、`PLAN_NOT_CONFIRMED` 需明确阻断提交 | implemented | `service.py::create_search_run` raises both codes | No explicit API regression test for both codes | contract tests for error responses | Slice 05 | 代码有，专项验证缺 |
| TDD-ERR-DEGRADE | TDD | §6.5 + Appx A | P0 | `JD_TOO_LONG`、`AI_TIMEOUT`、`CTS_TIMEOUT`、`CTS_PARAM_ANOMALY` 要有明确降级语义 | partial | `CTS_PARAM_ANOMALY` exists in `adapters.py`; other codes absent | `tests/test_api_flow.py::test_zero_results_and_parameter_anomaly_are_distinct` covers anomaly only | long-JD, AI timeout, CTS timeout handling | Slice 05 | 一组错误只实现了部分 |
| TDD-ERR-PERMISSION-IDEMPOTENCY | TDD | §6.5 + Appx A | P0 | `NO_CONTACT_PERMISSION`、`IDEMPOTENCY_CONFLICT` 需要稳定契约 | partial | `NO_CONTACT_PERMISSION` exists in `create_export`; duplicate search/export requests return existing resources instead of conflict | Sensitive-export test only | explicit duplicate semantics | Slice 05 | 权限错误在，幂等冲突契约未对齐 |
| TDD-ERR-EVAL | TDD | Appx A | P0 | `EVAL_BLOCKING_FAILED` 应阻断 CI / release gate | partial | `tools/ci/run_eval_gate.sh` surfaces `EVAL_BLOCKING_FAILED` on failure<br>`.github/workflows/nightly-regression.yml` runs the explicit eval gate before other nightly checks with `CVM_RESUME_SOURCE_MODE=mock` and `CVM_LLM_MODE=stub` | `tests/test_eval_runner.py::test_blocking_suite_passes`<br>`tests/test_eval_runner.py::test_blocking_suite_returns_failure_result_when_search_run_fails`<br>`./tools/ci/run_eval_gate.sh` | eval-result propagation into release publishing | Slice 05 | 现在已有明确且确定性的 CI eval gate，但尚未接入单独 release 流程 |
| TDD-WF-SEARCH | TDD | §7.1 | P0 | `SearchRunWorkflow` 编排 Search Run，支持可恢复背景执行 | validated | `services/temporal-worker/src/cvm_worker/workflows.py::SearchRunWorkflow`<br>`routes.py::create_search_run` | `tests/test_api_stack.py::test_stack_mainline_flow` | stop/continue signals | Slice 02 | 当前唯一真正落地的 workflow |
| TDD-WF-AI | TDD | §7.1 | P0 | `KeywordDraftWorkflow` / `ResumeAnalysisWorkflow` 负责 AI 草案与简历分析 | missing | Keyword draft and resume analysis happen synchronously in `service.py` | None yet | dedicated AI workflows, async job state | Slice 03 | 直接缺口 |
| TDD-WF-DELIVERY | TDD | §7.1 | P0/P1 | `ExportWorkflow` / `EvalRunWorkflow` 支撑导出与评测 | partial | `create_export` and `create_eval_run` exist, but run synchronously in API service | `tests/test_eval_runner.py::test_blocking_suite_passes` covers blocking eval function only | actual workflows or background jobs | Slice 05 | 能力在，编排层没有按 TDD 落地 |
| TDD-IDEMPOTENCY-SEARCH-RUN | TDD | §7.2 | P0 | Search Run 用 idempotency key 去重 | implemented | `service.py::create_search_run`<br>`models.py` unique `idempotency_key` | No duplicate-key regression test | response contract for duplicates | Slice 02 | 代码层成立 |
| TDD-IDEMPOTENCY-PAGE-SNAPSHOT | TDD | §7.2 | P0 | 页快照幂等写入；同页重试不重复 | implemented | `models.py` unique `run_id,page_no`<br>`service.py::_upsert_candidate` reuses candidate identity | No replay test | retry harness | Slice 02 | 约束在 |
| TDD-IDEMPOTENCY-EXPORT-EVENTS | TDD | §7.2 | P0/P1 | export job 要幂等；集成事件消费要 dedupe | partial | `create_export` checks `idempotency_key`<br>No outbox or consumer dedupe | No duplicate-export or event-consumer test | outbox_event, processed markers | Slice 05 | 只实现导出半边 |
| TDD-DAY0-GATES | TDD | §12.1 | P0 | Day 0 必须有 docs/contracts 骨架、`make validate`、CI skeleton、CODEOWNERS、AGENTS 等 | partial | `docs/`<br>`contracts/`<br>`Makefile`<br>`.github/workflows/validate.yml`<br>`.github/workflows/nightly-regression.yml`<br>`.github/workflows/build-verify.yml`<br>`.github/actions/setup-ci-env/action.yml`<br>`.github/CODEOWNERS`<br>`AGENTS.md` | `make test`<br>`make test-stack`<br>Manual workflow review for required-check layout and non-blocking post-merge workflows | runner segmentation, ontology freshness | Slice 01 | CI skeleton 现在覆盖 blocking、nightly、build verification，并把 stack gate 固定为 deterministic mock/stub 模式；`.env` 保持真实运行时配置，测试 harness 与 workflow env 显式注入 deterministic mode |
| TDD-WEEK1-GATES | TDD | §12.1 | P0 | Week 1 应完成 codegen、最小主链路、允许目录策略、Ops/Evals blocking suite | partial | `Makefile codegen`<br>`test_api_flow.py`<br>`ops.page.ts`<br>`evals.page.ts`<br>`.github/workflows/nightly-regression.yml`<br>`tools/ci/run_eval_gate.sh` | `tests/test_eval_runner.py::test_blocking_suite_passes`<br>`tests/test_eval_runner.py::test_blocking_suite_returns_failure_result_when_search_run_fails`<br>`./tools/ci/run_eval_gate.sh` | single-shell alignment, context-pack discipline | Slice 05 | 现有 blocking eval 已进入 nightly CI gate，且 deterministic mock/stub 由测试 harness 与 workflow env 统一注入，但仍不是 PR required check，整体仓库形态与 TDD 仍有差距 |
| TDD-HARD-RULES | TDD | Appx B | P0 | 不得绕过 `contracts/` 改 DTO；不得在 domain 引 infra；不得手改 generated | partial | `AGENTS.md` hard rules<br>`tools/ci/check_architecture.py`<br>`Makefile validate` with `check_generated_clean.py` | No policy-specific regression test | stronger CI policy checks | Slice 05 | 规则和部分 gate 在，覆盖仍可加硬 |

## Existing Active Plan Mapping Snapshot

| Plan | Current Mapping | Disposition |
| --- | --- | --- |
| `docs/EXEC-PLANS/active/bootstrap-plan.md` | Broadly overlaps `ADR-001`, `ADR-005`, `ADR-006`, `ADR-007`, `TDD-DAY0-GATES`, `TDD-WEEK1-GATES` | Keep as historical bootstrap note only; not acceptable as current execution source because it lacks row-level scope and evidence |
| `docs/EXEC-PLANS/active/dependency-governance-plan.md` | Mostly maps to `ADR-001`, `ADR-006`, `TDD-ARCH-DOMAIN-BOUNDARY`, `TDD-HARD-RULES`, parts of `TDD-DAY0-GATES` | Retain as thematic backlog; later split across Slice 02 and Slice 05 using explicit IDs |
| `docs/EXEC-PLANS/active/ci-pipeline-hardening-plan.md` | Maps to `ADR-008`, `TDD-ERR-EVAL`, `TDD-DAY0-GATES`, and `TDD-WEEK1-GATES` | Current execution source for CI hardening, diagnostics capture, and post-merge workflow layout |
| `docs/EXEC-PLANS/active/hard-harness-plan.md` | Mostly maps to `ADR-006`, `ADR-007`, `TDD-ERR-*`, `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-07`, `TDD-HARD-RULES` | Retain as thematic backlog; later split across Slice 04 and Slice 05 using explicit IDs |
