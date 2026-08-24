# SE Skills

SE Skills defines reusable software-engineering workflows and the collaborating roles that carry them out.

## Language

**Agent Observer**:
A runtime-neutral toolkit that discovers, reads, queries, and computes facts from locally persisted agent-session records. It does not interpret those facts or prescribe a fixed analysis.
_Avoid_: Telemetry agent, trace agent

**Hive Sentinel**:
The swarm-specific observer role that interprets Agent Observer facts to characterize resource use and identify optimization opportunities. Its Chinese role name is “哨蜂”.
_Avoid_: Observer bee, scout bee, fourth caste

**Session Record**:
An original JSONL record persisted locally by an agent runtime such as Codex or Claude Code.
_Avoid_: Trace, span, telemetry event

**Swarm Checkpoint**:
A bounded inspection of session records performed while a swarm run is in progress, without continuously monitoring the run.
_Avoid_: Live watchdog, polling loop

**Swarm Review**:
A post-completion analysis of a swarm run derived from its session records.
_Avoid_: Postmortem, observability report

**Optimization Advice**:
A recommendation derived from session analysis and returned to the Queen Bee without changing or interrupting the observed swarm run.
_Avoid_: Remediation, self-healing action

**Swarm Feedback**:
Session-derived facts and optimization advice that the Queen Bee may use to adjust an unfinished swarm run. It is corrective input, not a negative evaluation of an agent.
_Avoid_: Negative feedback, automatic remediation

**Swarm Guidance**:
Project-specific, durable lessons for future swarm runs, stored in the workspace's `SWARM.md` and maintained by the Queen Bee.
_Avoid_: Sentinel report, temporary prompt adjustment

**Session Scope**:
The agent sessions and known relationships that a Queen Bee asks a Hive Sentinel to analyze.
_Avoid_: Current session, latest session

**Exploratory Runtime**:
An agent runtime without a dedicated session adapter, whose persisted records the Hive Sentinel locates and investigates from natural-language guidance using available tools.
_Avoid_: Unsupported runtime, generic adapter
