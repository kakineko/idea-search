# Agent Teams PoC — Structural Smoke Test

**Date**: 2026-04-18
**Environment**: Claude Code v2.1.114, Opus 4.7 (1M context), Claude Max plan
**PoC directory**: `~/work/agent_teams_poc`
**Context**: Pre-hackathon exploration of Claude Code Agent Teams feasibility for Phase 2 of idea-search (Built with Opus 4.7 hackathon, 2026-04-22 start)

## Purpose

Before committing to Agent Teams as the execution framework for idea-search Phase 2, verify:
1. Does it actually spawn and coordinate teammates as documented?
2. Does it support nested team spawning (needed for hierarchical mode)?

Resolving these in advance saves 1-2 days of hackathon time otherwise lost to blind exploration.

## Setup

```bash
cd ~/work
mkdir agent_teams_poc && cd agent_teams_poc
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
claude
```

No config files, no agent definitions. Team structure expressed purely in natural language prompts.

## Test 1: Basic messaging relay

**Prompt**:
Create an agent team with 3 teammates named alice, bob, and carol.
Alice should send the message "hello" to bob.
Bob should append " world" and send to carol.
Carol should append "!" and report the final string back to you (team lead).
Print the final string.
This is just a structural smoke test. Keep responses minimal.

**Result**: ✅ Worked as expected.

Output:
3 background agents launched
@bob @carol @alice
Team spawned. Waiting for carol's report.
Bob and carol idle, awaiting alice's trigger.
Alice sent greeting to bob. Waiting for chain.
Bob forwarded to carol.
@carol> final result
Final string: hello world!

**Confirmed**:
- Teammate spawn (3 parallel agents in independent contexts)
- Peer-to-peer messaging (alice → bob → carol)
- Team lead synthesis (final report reached the lead)
- Ordered execution (chain proceeded in intended order despite being async)

## Test 2: Nested team spawning

**Prompt**:
I want to test whether Agent Teams supports nested team spawning.
Spawn one teammate called "branch_A".
Instruct branch_A to attempt to spawn its own sub-teammate called "method_A1".
After branch_A attempts this, report back to me (team lead):

Was branch_A able to spawn method_A1?
If yes: briefly describe how.
If no: what error or limitation did branch_A encounter?


**Result**: ❌ Not supported.

Output from branch_A:
Probe results:

No — branch_A could not spawn method_A1.
N/A
Limitation: branch_A has no Agent or TeamCreate tool in its surface.
Available tools are limited to SendMessage (peer messaging),
Task* (shared task list), Cron*, and worktree tools.
Spawning capability appears restricted to the top-level orchestrator.

Conclusion: Nested team/teammate spawning is not supported in this harness.
Only the team lead can spawn agents.

**Confirmed**:
- Only team lead can spawn teammates.
- Teammates' tool surface: `SendMessage`, `Task*` (shared list), `Cron*`, worktree tools.
- Team lead can explicitly shut down a team (confirmed by "Team cleaned up" message).

## Implications for idea-search Phase 2

### Design principle: phase-by-phase flat teams

Given that teammates cannot spawn sub-teams, and that idea-search has natural sequential dependencies (ideas must exist before they can be validated), the cleanest architecture is **phase-by-phase team composition**:
Phase 1: Idea Generation Team

proposer × N, evaluator × M
synthesize → idea set
→ Team shut down

Phase 2: Validation Team (composition determined by Phase 1 output)

outside validator (arXiv / Semantic Scholar)
inside validator × K (multi-persona)
synthesize → reality score
→ Team shut down

Phase 3 (hierarchical): Branch Exploration Team

branch explorer × N
method generator × M
→ Team shut down

Phase 4: Method Refinement Team

...


Between phases, team lead shuts down the previous team and spawns the next, passing state through its own context.

### Why this pattern is superior to one-big-flat-team

1. **Maps cleanly to Agent Teams' capability surface** (no nesting needed)
2. **Dynamic team composition**: Phase 2's teammates can be selected *based on* Phase 1's output (e.g., physics-expert persona when the idea is about quantum computing)
3. **Clear debugging boundaries**: each phase either succeeds or fails, no tangled mid-pipeline states
4. **Reduced concurrent token consumption**: only current phase's teammates are alive
5. **Natural dependency management**: the sequential nature of ideation → validation is reflected in the team structure

### Cost re-estimation for hackathon

With this design clarity, the revised estimate:

| Item | Estimated time |
|---|---|
| Phase 1 team (Agent Teams port of baseline) | 0.5-1 day |
| Phase 1 team (full mode with archive, multi-round) | 1 day |
| Phase 2 team: outside validator (arXiv + Semantic Scholar) | 1-2 days |
| Phase 2 team: inside validator (multi-persona) | 1 day |
| Phase 3/4 teams (hierarchical flattening) | 1-2 days |
| Demo, documentation, submission | 1 day |

Total: 5-8 days — fits within the 7-day hackathon with room for setbacks.

### Revised priority order

1. **Phase 1 team** (Agent Teams port): confirms Agent Teams can run idea-search's core loop
2. **Phase 2 team** (validation): delivers the main thesis — outside + inside grounding
3. **Phase 3/4 teams** (hierarchical): additional depth if time permits

Unlike the earlier assumption that Agent Teams port is risky, the PoC shows it is straightforward. The risk shifts instead to Phase 2's data-fetching logic (arXiv/Semantic Scholar error handling, rate limiting).

## Takeaways

- Agent Teams works as documented. No surprises in basic operation.
- The no-nesting constraint is the single most important structural limitation.
- Phase-by-phase team composition is not a workaround — it is genuinely a better fit for idea-search's dependency structure than nested teams would have been.
- One hour of PoC saved an unknown but significant amount of hackathon time.

## Next actions

1. Commit `results/2026-04-18_outside_signal_design.md` (English) and `_ja.md` (Japanese) — outside signal detailed design.
2. Commit this file.
3. Sketch `phase2_plan_ja.md` (optional): week schedule, Go/No-Go criteria.
4. Stop for the day.