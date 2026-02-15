# Public Repo Polish Report

## Summary of issues found

- `MANIFEST.txt` referenced old private-layout paths (legacy package-root paths) and files not present in this public repository.
- `docs/quickstart.md` assumed commands from an old package root, which does not exist in this repository layout.
- `examples/c/minimal_eval.c` compile-check comments also referenced the old package-root layout.
- Binary distribution expectations were implicit; users could assume local `lib/` artifacts existed when they currently do not.
- No plain-language evaluation usage terms were present.
- No guidance file existed for GitHub "About" metadata consistency.

## Files changed

- `.gitignore`
- `MANIFEST.txt`
- `README.md`
- `docs/quickstart.md`
- `examples/c/minimal_eval.c`
- `docs/distribution.md` (new)
- `docs/github_metadata.md` (new)
- `EVALUATION_TERMS.md` (new)
- `reports/public_repo_polish_report.md` (new)

## Quickstart path fix (before/after)

Before:

```text
Run commands from an old package root
cd <old-package-root>
```

After:

```text
This guide assumes you are at the repository root.
cl ... /I include examples/c/minimal_eval.c ...
```

## Rationale

- Public repo should be self-consistent and runnable from its actual layout.
- Manifest should document only what is truly published.
- Binary availability must be explicit to avoid credibility gaps during evaluation.
- Evaluation terms and metadata guidance reduce ambiguity for external reviewers.

## Remaining known limitations

- No redistributable binaries are currently committed in this repository.
- Compile-and-run evaluation requires separately delivered or released binary artifacts.
- This repository is intentionally docs+headers+example focused; private engine internals are out of scope.
