# ILASP executable

`ILASP` is the existing Linux x86_64 binary moved from `C:\tmp\ILASP`.
It reports version **4.4.1**, built on **2024-11-11**, and supports algorithms
`--version=2`, `2i`, `3`, and `4`.

SHA256: `816edec521b48f88bd078960e6b4a1c99723e1f64ea20a502eebd496d89dc6c5`.

Upstream: [ILASP releases](https://github.com/ilaspltd/ILASP-releases/releases).
ILASP is third-party software by Mark Law / ILASP Limited; the Gentians GPL
license does not relicense this executable. See the upstream
[terms of use](https://www.ilasp.com/terms). Upstream permits non-commercial
research and education; commercial use requires contacting the author.

The binary requires Linux x86_64, glibc >= 2.34, libstdc++ providing
`GLIBCXX_3.4.30`, and `libpython3.10.so.1.0` with its Python standard library.
Ubuntu 22.04 on Shelob supplies these dependencies. Windows runs it through WSL.
The experiment runner also needs GNU `timeout`.

The Git executable bit is set. If a copy outside Git loses it, run
`chmod +x tools/ilasp/ILASP` on Linux.

See [the experiment protocol](../../docs/ilasp-experiments.md) for native Linux,
Windows/WSL, and custom Python runtime commands.
