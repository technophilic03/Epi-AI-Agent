# Provider Menu Labels Design

## Goal

Help users choose an AI provider by identifying OpenAI as the preferred
configuration and the OpenAI-compatible endpoint path as a beta option.

## Scope

Update the terminal provider menus in `run_fastapi.py`. The first-time setup
menu will read:

```text
No AI provider is configured.

1. Configure OpenAI (preferred)
2. Configure Anthropic
3. Connect to a compatible endpoint (beta)
Selection:
```

The `--reconfigure` menu will use the same qualifiers:

```text
Configure AI providers. Existing providers are retained.

1. Configure or replace OpenAI (preferred)
2. Configure or replace Anthropic
3. Connect to a compatible endpoint (beta)
4. Remove OpenAI
5. Remove Anthropic
6. Keep current providers
Selection [6]:
```

The wording is consistent across both menus because OpenAI remains the
recommended configuration during initial setup and later reconfiguration.
The beta qualifier communicates the less guided, configuration-file-based
nature of compatible endpoints.

## Behavior

This is a presentation-only change. Menu numbering, default selections,
credential prompts, provider validation, environment persistence, compatible
endpoint registration, and model availability remain unchanged.

## Testing

Update the existing exact-string assertions for the first-time and
reconfiguration prompts. Run the focused `tests/test_run_fastapi.py` suite and
the full backend test suite. No frontend rebuild is required because this
change does not modify frontend source or assets. A new feature smoke is not
required because the change introduces no new workflow or behavior and the
production prompt boundary already has focused regression coverage.
