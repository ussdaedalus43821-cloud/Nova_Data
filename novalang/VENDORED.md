# Vendored NovaLang

Copied unmodified from the Nova_Lang repository, `develop` at **7360fb4** (the merge of pull request 8: packages part 1; it
includes `std:files`, `std:decimal` on the native tier, `std:regex`, and the static capability check of packages). Every file below
was copied from that commit with `git show`.

| File | Purpose |
| --- | --- |
| `novalang.py` | the interpreter, bytecode VM and CLI |
| `novalang.nova` | the self-hosted interpreter, run by `--bootstrap` |
| `bootstrap.py` | loader for the self-hosted engine |
| `lib/std/` | the standard modules (`std:decimal`, `std:files`, `std:format`, `std:math`, `std:regex`, `std:text`) and their list, `modules.json` |
| `tools/` | `nova-typecheck.py`, `nova_ast.py`, `nova_scope.py`, `nova_compiler.py`: a program that has an `import` needs them beside the interpreter (G-017 in Nova_Stats), so the program that used to have no imports now vendors four more files |
| `LICENSE` | upstream licence |

To update, copy the same files from a newer commit and re-run `python3 tests/run_suite.py`.
