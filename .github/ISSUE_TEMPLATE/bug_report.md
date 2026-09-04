---
name: Bug report
about: Something broke or produced wrong output
labels: bug
---

## What happened

What you ran and what went wrong. Paste the exact command and output.

```console
$ uv run --env-file .env docket ...
```

## Expected

What you expected instead.

## Environment

- OS and Python version:
- docket version or commit:
- `DOCKET_LLM_MODEL` (if the bug involves extraction):
- AWS region(s) scanned:

## Notes

Steampipe and AWS errors surface as raw `sqlite3.OperationalError`; include
the full traceback. Check that your AWS credentials are current before filing
credential-shaped errors.
