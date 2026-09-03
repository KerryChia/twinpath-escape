#!/usr/bin/env python3
"""Build and validate the required C++17 native search library."""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "core" / "ai" / "native" / "search_native.cpp"
HEADER = SOURCE.with_suffix(".h")
ABI_VERSION = 1


def platform_tag() -> str:
    machine = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    return f"{platform.system().lower()}-{machine}"


def library_name() -> str:
    if sys.platform == "win32":
        return "search_native.dll"
    if sys.platform == "darwin":
        return "libsearch_native.dylib"
    return "libsearch_native.so"


def output_path() -> Path:
    return ROOT / "build" / "native" / platform_tag() / library_name()


def is_stale(output: Path) -> bool:
    if not output.is_file():
        return True
    build_inputs = (SOURCE, HEADER, Path(__file__).resolve())
    return output.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in build_inputs)


def validate(path: Path) -> str:
    try:
        library = ctypes.CDLL(str(path))
        library.tn_search_abi_version.argtypes = []
        library.tn_search_abi_version.restype = ctypes.c_uint32
        library.tn_search_backend_info.argtypes = []
        library.tn_search_backend_info.restype = ctypes.c_char_p
        library.tn_search_self_test.argtypes = []
        library.tn_search_self_test.restype = ctypes.c_int32
        abi = int(library.tn_search_abi_version())
        info = library.tn_search_backend_info()
        self_test = int(library.tn_search_self_test())
    except (AttributeError, OSError) as exc:
        raise RuntimeError(f"built library failed to load: {exc}") from exc
    if abi != ABI_VERSION:
        raise RuntimeError(f"built library ABI is {abi}, expected {ABI_VERSION}")
    if not info:
        raise RuntimeError("built library returned empty backend information")
    if self_test != 1:
        raise RuntimeError("built library self-test failed")
    return info.decode("utf-8")


def _vswhere_path() -> Path | None:
    located = shutil.which("vswhere") or shutil.which("vswhere.exe")
    candidates = [
        Path(located) if located else None,
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def _msvc_environment() -> dict[str, str] | None:
    vswhere = _vswhere_path()
    if vswhere is None:
        return None
    query = subprocess.run(
        [str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
        check=False,
    )
    installation = query.stdout.strip()
    if query.returncode != 0 or not installation:
        return None
    vcvars = Path(installation) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.is_file():
        return None
    result = subprocess.run(
        ["cmd.exe", "/d", "/s", "/c", f'call "{vcvars}" >nul && set'],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    environment = os.environ.copy()
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key] = value
    return environment


def compiler_command(destination: Path) -> tuple[list[str], dict[str, str] | None, str]:
    if sys.platform == "win32":
        msvc_env = _msvc_environment()
        if msvc_env is not None and shutil.which("cl.exe", path=msvc_env.get("PATH")):
            return (
                ["cl.exe", "/nologo", "/std:c++17", "/O2", "/EHsc", "/MT", "/LD", str(SOURCE),
                 "/link", f"/OUT:{destination}"],
                msvc_env,
                "MSVC",
            )
        mingw = shutil.which("g++") or shutil.which("g++.exe")
        if mingw:
            return (
                [mingw, "-std=c++17", "-O2", "-shared", "-static", "-static-libgcc", "-static-libstdc++",
                 "-o", str(destination), str(SOURCE)],
                None,
                "MinGW g++",
            )
        raise RuntimeError("No C++17 compiler found. Install Visual Studio Build Tools (C++) or MinGW g++.")
    if sys.platform == "darwin":
        compiler = shutil.which("clang++")
        if not compiler:
            raise RuntimeError("clang++ was not found; install Xcode Command Line Tools")
        return ([compiler, "-std=c++17", "-O2", "-dynamiclib", "-o", str(destination), str(SOURCE)], None, "clang++")
    compiler = shutil.which("g++")
    if not compiler:
        raise RuntimeError("g++ was not found; install a C++17 compiler")
    return ([compiler, "-std=c++17", "-O2", "-fPIC", "-shared", "-o", str(destination), str(SOURCE)], None, "g++")


def build(output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-build-", dir=output.parent) as temporary:
        candidate = Path(temporary) / output.name
        command, environment, compiler = compiler_command(candidate)
        print(f"Building native search backend with {compiler}...")
        subprocess.run(command, cwd=temporary, env=environment, check=True)
        info = validate(candidate)
        os.replace(candidate, output)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--ensure", action="store_true", help="build only when absent or stale")
    mode.add_argument("--rebuild", action="store_true", help="always rebuild")
    parser.add_argument("--self-test", action="store_true", help="validate the installed library")
    args = parser.parse_args()
    output = output_path()
    try:
        if args.self_test and not args.rebuild and not args.ensure:
            info = validate(output)
            print(f"Native search self-test passed: {info} ({output})")
            return 0
        rebuild = args.rebuild or is_stale(output)
        if not rebuild:
            try:
                info = validate(output)
            except RuntimeError:
                if not args.ensure:
                    raise
                rebuild = True
        if rebuild:
            info = build(output)
            print(f"Native search backend ready: {info} ({output})")
        else:
            print(f"Native search backend is current: {info} ({output})")
        if args.self_test:
            print("Native search self-test passed")
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
