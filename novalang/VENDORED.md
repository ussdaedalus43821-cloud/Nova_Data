# Vendored NovaLang

Copied unmodified from the Nova_Lang repository, `develop` at **34a6256** (the merge of pull request 12, M14 slice P1: `std:csv`,
`std:dict` and `sorted(list, key)`; it also brings `std:date` and `std:hash`). Every file below was copied from that commit
with `git show`.

| File | Purpose |
| --- | --- |
| `novalang.py` | the interpreter, bytecode VM and CLI |
| `novalang.nova` | the self-hosted interpreter, run by `--bootstrap` |
| `bootstrap.py` | loader for the self-hosted engine |
| `lib/std/` | the standard modules (`std:csv`, `std:date`, `std:decimal`, `std:dict`, `std:files`, `std:format`, `std:hash`, `std:math`, `std:regex`, `std:text`) and their list, `modules.json` |
| `tools/` | `nova-typecheck.py`, `nova_ast.py`, `nova_scope.py`, `nova_compiler.py`: a program that has an `import` needs them beside the interpreter (G-017 in Nova_Stats). The other upstream tools (formatter, linter, package manager, language server) are not needed to run the program and are not vendored |
| `LICENSE-MIT`, `LICENSE-APACHE` | upstream licence (NovaLang is dual MIT OR Apache-2.0 since 685e74c; this replaces the single MIT `LICENSE` of the previous copy) |

To update, copy the same files from a newer commit and re-run `python3 tests/run_suite.py`.
