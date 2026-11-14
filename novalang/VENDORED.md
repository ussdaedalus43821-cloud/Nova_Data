# Vendored NovaLang

Copied unmodified from the Nova_Lang repository, `develop` at **0192f5b** (the merge of pull request 6: the native standard-module tier,
`std:files`, `chr`/`ord`, and `std:decimal` on the native tier). Every file below was compared byte for byte with that commit.

| File | Purpose |
| --- | --- |
| `novalang.py` | the interpreter, bytecode VM and CLI |
| `novalang.nova` | the self-hosted interpreter, run by `--bootstrap` |
| `bootstrap.py` | loader for the self-hosted engine |
| `lib/std/` | the standard modules (`std:decimal`, `std:format`, `std:math`, `std:text`, `std:files`) and their list, `modules.json` |
| `tools/` | `nova-typecheck.py`, `nova_ast.py`, `nova_scope.py`, `nova_compiler.py`: a program that has an `import` needs them beside the interpreter (G-017 in Nova_Stats), so the program that used to have no imports now vendors four more files |
| `LICENSE` | upstream licence |

To update, copy the same files from a newer commit and re-run `python3 tests/run_suite.py`.
