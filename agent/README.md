# Claims reviewer tools

The three Python tools in this folder read the local Gold claim output and fictional policy index. First run the claims demo. Point `SATYASETU_CLAIMS_OUT` to its output directory.

For a hosted assistant, scaffold an agent in your own Agent Bricks workspace using the [BRFSS setup guide](../cloud/agent_bricks/README.md) as a starting point. Add the claims tool modules to the scaffold, make the installed SatyaSetu package and synthetic evidence available, and register the functions using the scaffold's tool API. Use [reviewer.md](prompts/reviewer.md) as the instructions. The notification tool returns a preview. A human can then use the claims CLI to create and approve a draft.

Try: “Why was C002 flagged, and which sections of the fictional policy explain it?”
