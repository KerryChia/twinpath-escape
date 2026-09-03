# Native search build

TwinPath Escape requires the C++17 CSR search backend. There is intentionally no production Python fallback.

## Build commands

```text
python tools/build_native.py --ensure --self-test
python tools/build_native.py --rebuild --self-test
```

Windows users can also run `build_native_windows.bat`. `run_windows.bat` always performs `--ensure --self-test` before source/TMX validation or launch.

Output is platform-specific and generated:

```text
build/native/windows-x86_64/search_native.dll
build/native/linux-x86_64/libsearch_native.so
build/native/darwin-arm64/libsearch_native.dylib
```

The directory and native binaries are ignored by Git. Never copy one platform's binary into another platform/architecture directory.

## Toolchains

- Windows: Visual Studio C++ Build Tools discovered with `vswhere.exe`, with `vcvars64.bat` used to construct the compiler environment; MinGW `g++` is the fallback.
- Linux: `g++`.
- macOS: `clang++` from Xcode Command Line Tools.

The builder compares native source, header, and build-tool modification times for `--ensure`, compiles into a temporary directory, loads the candidate with `ctypes`, checks ABI version 1 and runs the exported self-test, then atomically replaces the installed binary. A failed candidate never replaces a working output. Windows MSVC builds use `/MT`; MinGW builds statically link the GCC/C++ runtimes.

## ABI and loading

`core/ai/native/search_native.h` exposes only fixed-width C types, pointers and plain structs. It does not include Python headers. The exports are:

- `tn_search_abi_version`
- `tn_search_backend_info`
- `tn_search_self_test`
- `tn_search_csr`

`core/ai/native_backend.py` checks ABI version and searches the source tree and PyInstaller's `sys._MEIPASS` for the exact `build/native/<platform>-<arch>` path. `game.spec` packages the library at that path.

## Troubleshooting

- “library was not found”: run `python tools/build_native.py --ensure --self-test` from the repository root.
- “No C++17 compiler found”: install Visual Studio Build Tools with Desktop development with C++, or add MinGW g++ to `PATH`.
- “ABI mismatch”: rebuild; do not retain an older DLL/shared object after changing the header/backend.
- load failure on Windows with MinGW: rebuild with the provided script, which statically links the MinGW C++ runtime.
- self-test failure: delete only `build/native/<platform>-<arch>` and run `--rebuild`; do not add a Python fallback.
