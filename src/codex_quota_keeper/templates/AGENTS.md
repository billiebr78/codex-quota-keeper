# Codex Quota Keeper — efficient development policy

- Prioritize correctness and verification; never sacrifice essential testing to save tokens.
- Search for relevant symbols and read bounded sections before opening whole large files. Read all code needed for a safe edit.
- For long logs, extract only the failing portions and enough surrounding context; preserve the original log on disk.
- Delegate only independent or clearly bounded tasks. Do not spawn multiple agents for trivial work or send the same task to several agents without a reason.
- Favor existing Codex tools and scripts over repeating identical searches or generating large output.
- Keep responses concise during routine operations; report evidence, errors and decisions clearly.
- Maintain a short HANDOFF.md for work spanning sessions. Record verified progress, filenames, commands, blockers, and one precise next step.
- A new session should read HANDOFF.md rather than request the entire old transcript. Do not claim that compacting or resuming creates a fresh context.
- At each milestone, run focused tests; run a broader regression before release. Do not skip a necessary test for token efficiency.
- Never alter permission, sandbox, authentication or model configuration without explicit user approval.
- Treat quota warnings as prompts to assess context, not as a reason to stop work abruptly.
