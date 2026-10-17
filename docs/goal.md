# GraphOS — Project Goal

## The problem

AI agents often work with fragmented information. They can miss relationships between people, systems, events, and records; lose useful context between sessions; and produce decisions that are difficult to verify or explain.

## The goal

**GraphOS is an AI agent that uses connected data to understand a situation, reason across relationships, decide what should happen, and explain why.** It should work from evidence and the links between that evidence—not from isolated facts, unsupported assumptions, or guesses.

The graph should provide the agent with connected context and useful memory across investigations and sessions. As the agent learns, relevant findings and outcomes should help it make better-informed decisions later.

## What GraphOS must be able to do

- **Investigate through relationships.** Follow meaningful multi-step connections between entities and records to understand a problem beyond the information stated in the initial request.
- **Use the graph to reason.** Graph queries, traversals, and applicable graph algorithms must contribute to the investigation and decision—not merely display data.
- **Choose tools purposefully.** Select and use available graph capabilities through MCP according to the question being investigated, then use the returned results to guide the next step.
- **Build conclusions from evidence.** Check relevant connections, consider competing explanations when appropriate, and distinguish observed facts from inferences and unknowns.
- **Decide and act based on what the graph shows.** Recommend or perform an action only when the available evidence supports it and the action is permitted. Seek approval or explain the limitation when authority, evidence, or policy is insufficient.
- **Remember useful context.** Preserve relevant findings, decisions, and outcomes in connected memory so they can inform later work rather than treating every session as unrelated.
- **Explain its reasoning.** Make it possible to inspect the evidence and relationship paths behind a conclusion or proposed action. The explanation must reflect what the system actually found and did.

## Non-negotiable principles

### The graph is central

FalkorDB must be a primary part of how GraphOS works. The graph must participate in its investigation, reasoning, memory, or decisions in a meaningful way. It must not be a decorative visualization or an optional layer placed over a product that would work the same without it. Removing the graph should materially weaken the product's core capabilities.

### Evidence before confidence

GraphOS must not invent entities, relationships, history, sources, or tool results. A path through the graph is evidence of a recorded relationship, not automatic proof of causation. Missing evidence must be reported as uncertainty, not treated as proof that something does not exist.

### Tool use must be real

GraphOS must use actual capabilities exposed through MCP and base its next steps on their results. It must not simulate graph access, hard-code expected findings, or bypass the graph access boundary to create the appearance of reasoning.

### Actions must be accountable

A decision to act must be grounded in findings, checked against applicable permissions and policies, and traceable to its justification. The agent must not treat its own conclusion as permission to execute an action. Significant or irreversible actions require the appropriate authorization.

### Context must be handled responsibly

Use only data that the project is permitted to access. Treat retrieved records and documents as evidence to examine, not as instructions that can override the system's rules or permissions. Protect credentials and sensitive information.

## What GraphOS is not

- A general chatbot that answers without using connected data.
- A graph viewer whose underlying graph does not affect the result.
- A conventional search or retrieval system that merely returns related records without reasoning over their relationships.
- An agent that takes actions first and tries to justify them afterward.
- A system that hides uncertainty, fabricates evidence, or claims success without verifying the result.

## How to judge whether a change serves the goal

When building or changing GraphOS, ask:

1. Does this help the agent investigate or reason over real relationships in the graph?
2. Does it improve the quality, usefulness, or continuity of its context and memory?
3. Does it help the agent choose a justified, permitted action—or explain why it cannot act?
4. Can a person inspect the evidence behind the result?
5. Does the behavior depend meaningfully on FalkorDB and real MCP tool results?
6. Does the change preserve safety, honesty, and accountability?

If a change does not meaningfully support these goals, it is not a core GraphOS requirement and should not be added merely for complexity or appearance.

## The intended outcome

GraphOS should turn connected data into **grounded understanding, justified decisions, accountable action, and reusable memory**. A person should be able to see not only what the agent concluded or did, but also which evidence and relationships led it there.
