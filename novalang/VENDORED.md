# Vendored NovaLang

Copied unmodified from the Nova_Lang repository, branch `m13/slice-3-native-tier` (the native standard-module tier, on top of
`develop` at **1029fcf**, the merge of pull request 5: `std:decimal`, `std:math`, `std:format`). It moves to a `develop` commit when
that branch is merged; until then this repository is not mergeable to `main`.

| File | Purpose |
| --- | --- |
| `novalang.py` | the interpreter, bytecode VM and CLI |
| `novalang.nova` | the self-hosted interpreter, run by `--bootstrap` |
| `bootstrap.py` | loader for the self-hosted engine |
| `lib/std/` | the standard modules (`std:decimal`, `std:format`, `std:math`, `std:text`, `std:files`) and their list, `modules.json` |
| `tools/` | `nova-typecheck.py`, `nova_ast.py`, `nova_scope.py`, `nova_compiler.py`: a program that has an `import` needs them beside the interpreter (G-017 in Nova_Stats), so the program that used to have no imports now vendors four more files |
| `LICENSE` | upstream licence |

To update, copy the same files from a newer commit and re-run `python3 tests/run_suite.py`.
