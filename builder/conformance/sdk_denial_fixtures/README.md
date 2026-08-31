# SDK-denial fixtures (HAR-003, ADR-0002 R2)

Each fixture is a role spec + a denied action. When the Claude Agent SDK
adapter is wired (HAR-003 implementation), a runner job spawns the
restricted subagent and asserts the denial. Until then, the host-side
policy layer (config/builder-roles.yaml via builder.core.policy) is the
enforced substitution and is qualified by tests/test_confinement.py.
The fixtures are declared here so the adapter has a fixed target set.
