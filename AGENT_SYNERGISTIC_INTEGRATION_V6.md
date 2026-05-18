# Synergistic Integration Guide (v6 Deployment)

## Overview
This document provides a complete integration framework for deploying the Synergistic Clarification + Batching hybrid approach in discovery agent workloads.

## Part 1: Clarification Phase Execution

### Step 1.1: Prepare Clarification Questions
Before ANY tool calls, gather comprehensive context:

```markdown
## Context Gathering (Required)

1. **Project Rules & Conventions**
   - Coding style guides, naming conventions?
   - Architectural patterns or frameworks to prefer?
   - Off-limits files or restricted areas?

2. **Task Scope Definition**
   - Which modules/components are in scope?
   - What is the primary objective?
   - Are there known hotspots or problem areas?

3. **Optimization Priorities**
   - Primary metric (latency, memory, tokens)?
   - Secondary metrics?
   - Hard constraints on any metric?

4. **Agent Preferences**
   - Exploratory or directed investigation?
   - Preferred tool interaction style?
   - Any prior context from similar projects?
```

### Step 1.2: Execute AskUser with Clarification
Call AskUser with structured questions to establish scope:
- Question should reference all 4 categories above
- Explain trade-offs and implications for each choice
- Provide 2-4 concrete alternative paths forward

### Step 1.3: Cache Context Comprehensively
Use UpdateContext to capture:
- Scope boundaries (what's in, what's out)
- Key constraints and priorities
- Known hotspots or problem areas
- Recommended investigation approach
- Project conventions and patterns

**Critical**: This cached context is reused throughout execution. Quality here multiplies through Phase 2.

## Part 2: Intelligent Batching Phase Execution

### Step 2.1: Plan Batches Based on Scope
Use clarified scope from Phase 1 to design batches:

**Batch Strategy** (adjust based on scope size):
- **Small scope** (1-5 key modules): 1-2 FileList, 2-3 FileRead, 0-1 Grep
- **Medium scope** (5-20 modules): 2-3 FileList, 3-5 FileRead, 1-2 Grep
- **Large scope** (20+ modules): 3-4 FileList, 5-8 FileRead, 2-3 Grep

### Step 2.2: Execute Batch 1 - Structural FileList
```
Call FileList 2-3 times in parallel:
- Root level (understand project layout)
- Primary scope directory (confirm structure)
- [Optional] Secondary scope if needed
```

**Output**: Mental model of scope structure

### Step 2.3: Execute Batch 2 - Content FileRead
```
Call FileRead 3-5 times in parallel:
- Group by logical area (module, component, layer)
- Prioritize by information value
- Limit to scope boundaries from Phase 1
```

**Output**: Concrete implementation details within scope

### Step 2.4: Execute Batch 3 - Pattern RecursiveGrep
```
Call RecursiveGrep 1-2 times (or 0 if not needed):
- Only for high-value patterns (identified in FileRead)
- Use fixed_strings when possible
- Limit directory scope
```

**Output**: Pattern validation and anomaly detection

### Step 2.5: Synthesize and Decide
- Refer to cached context from Phase 1
- Synthesize findings from batches
- Make decisions WITHOUT re-reading
- Complete analysis within Phase 1 scope

## Part 3: Expected Performance Metrics

### Tokens Per Task
- **Baseline**: 100% (e.g., 10,000 tokens)
- **With Synergistic v6**: 65-75% of baseline (6,500-7,500 tokens)
- **Savings**: 25-35%

### Seconds Per Task
- **Baseline**: 100% (e.g., 120 seconds)
- **With Synergistic v6**: 65-75% of baseline (78-90 seconds)
- **Savings**: 25-35%

### Pass Rate
- **Baseline**: 100% (e.g., 92% of eval tasks)
- **With Synergistic v6**: ≥100% (92-95%+)
- **Quality**: Maintained or improved

## Part 4: Failure Mode Analysis

### When Synergistic Works Best
✓ Large projects with clear structure (Blender-scale)
✓ Users have good project understanding
✓ Scope can be meaningfully narrowed
✓ Tasks have semi-defined direction
✓ Multiple modules in scope

### When Synergistic Works Poorly
✗ Completely exploratory tasks (no pre-scope)
✗ Tiny codebases (overhead not worth savings)
✗ Highly distributed codebase (can't batch effectively)
✗ Users unfamiliar with project
✗ Tasks requiring investigation of all modules

### Fallback Strategies
- **If scope too unclear**: Use Early Clarification alone (v3)
- **If batching not effective**: Use Tool Prioritization (v5)
- **If exploration heavy**: Use Prompt Compression (v1)
- **Small/unclear scope**: Simple sequential exploration

## Part 5: Deployment Checklist

### Pre-Execution
- [ ] Identified task type (large-scale, semi-defined scope?)
- [ ] Prepared clarification questions
- [ ] Reviewed project structure (rough understanding)
- [ ] Reviewed Gen 1 baseline metrics (if available)

### Phase 1 (Clarification)
- [ ] Called AskUser with comprehensive context questions
- [ ] Received and understood user responses
- [ ] Cached comprehensive context via UpdateContext
- [ ] Confirmed scope boundaries and priorities

### Phase 2 (Batching)
- [ ] Planned batches based on clarified scope
- [ ] Executed FileList batch (2-3 calls)
- [ ] Executed FileRead batch (3-5 calls)
- [ ] Executed RecursiveGrep batch (0-2 calls)
- [ ] Synthesized findings without re-reading

### Post-Execution
- [ ] Completed analysis within scope
- [ ] Tracked actual tokens and latency
- [ ] Compared vs. Baseline and Gen 1 versions
- [ ] Documented learnings for future use

## Part 6: Tuning Parameters

| Parameter | Small Scope | Medium Scope | Large Scope |
|-----------|------------|--------------|-------------|
| FileList calls | 1-2 | 2-3 | 3-4 |
| FileRead calls | 2-3 | 3-5 | 5-8 |
| Grep calls | 0-1 | 1-2 | 2-3 |
| Expected token savings | 15-20% | 25-30% | 30-35% |
| Expected latency savings | 15-20% | 25-30% | 30-35% |

## Conclusion
The Synergistic Clarification + Batching approach combines the best of both worlds:
- **Clarification** eliminates entire categories of exploratory dead-ends
- **Batching** executes efficiently within narrowed scope
- **Synergy** = much greater than sum of parts

Expected to achieve the highest fitness score of Gen 2 when scope can be meaningfully narrowed.
