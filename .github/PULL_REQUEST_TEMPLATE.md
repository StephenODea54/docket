# Summary

What changed and why.

## Checklist

- [ ] `uv run pytest` passes
- [ ] `uv run pre-commit run --all-files` passes
- [ ] New persisted tables are registered in `ALL_MODELS`; steampipe (`Aws*`) models are not
- [ ] Slow AWS reads happen outside write transactions

## Notes for the reviewer

Anything that needs extra attention: schema changes (sqlite rebuilds the
table), new environment variables, changes to `SYSTEM_PROMPT` or extraction
behavior.
