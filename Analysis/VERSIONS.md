# Version Index

| Version | File | Date | Key Decisions | Status |
|---|---|---|---|---|
| v0.1 | [v0.1-initial-plan.md](v0.1-initial-plan.md) | 2026-09-21 | Initial architecture derived from AgentStudio + eInsta analysis | DRAFT — open for debate |
| Enterprise Comparison | [feature-analysis-enterprise-comparison.md](feature-analysis-enterprise-comparison.md) | 2026-09-21 | Full gap analysis vs. Boomi, MuleSoft, SAP CPI, Informatica; 20-feature roadmap; differentiation strategy | REFERENCE — feeds v0.2 |
| Connector Registry | [connector-registry.md](connector-registry.md) | 2026-09-21 | Authoritative list of all 73 connectors (26 from AgentStudio + 47 new), priority-labelled, with implementation notes | LIVING DOCUMENT — update as connectors are added |
| Scenario: Salesforce → AWS | [scenario-salesforce-to-aws.md](scenario-salesforce-to-aws.md) | 2026-09-21 | Reference design: Flow YAML, step-by-step runtime walkthrough, class hierarchy, alternate AWS targets, error handling | REFERENCE SCENARIO |
| Transform Engine Design | [transform-engine-design.md](transform-engine-design.md) | 2026-09-21 | Four-layer transform stack: YAML declarative, DuckDB SQL, Python pandas, PySpark — rationale, syntax, when to use each | ARCHITECTURE DECISION |
| Runtime Language Decision | [runtime-language-decision.md](runtime-language-decision.md) | 2026-09-21 | Python core + Node.js frontend + polyglot connector protocol — full rationale vs Java and Node.js | ARCHITECTURE DECISION |
| SAP BTP Deployment Design | [btp-deployment-design.md](btp-deployment-design.md) | 2026-09-21 | Split control plane (Node.js CAP on CF) + execution engine (Python on Kyma); BTP service mapping; multi-target deployment | SUPERSEDED — BTP not a target; see runtime-language-decision.md |
| Exception Handling Design | [exception-handling-design.md](exception-handling-design.md) | 2026-09-21 | Retryable vs non-retryable split; row-level error modes (fail/skip/dead-letter); validate at deploy; error_threshold; structured events | ARCHITECTURE DECISION |

## How versions evolve
1. Debate open questions in `OPEN_QUESTIONS.md`
2. Resolve each question → document decision
3. Write next version file (`v0.N+1-<slug>.md`) incorporating decisions
4. Add row to this table
