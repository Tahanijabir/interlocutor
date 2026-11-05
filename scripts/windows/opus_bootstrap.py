
"""Run a Python script with an explicit native Opus DLL on Windows."""

import argparse
import ctypes
import ctypes.util
import os
import runpy
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Launch a Python script using an explicit Opus DLL."
    )

    parser.add_argument(
        "--opus-dll",
        required=True,
        help="Path to the native Opus DLL.",
    )

    parser.add_argument(
        "--dll-dir",
        action="append",
        default=[],
        help="Additional DLL dependency directory (repeatable).",
    )

    parser.add_argument(
        "script",
        help="Python script to execute.",
    )

    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the target script.",
    )

    args = parser.parse_args()

    if sys.platform != "win32":
        parser.error("This launcher is intended for Windows.")

    opus_dll = Path(args.opus_dll).resolve()
    target = Path(args.script).resolve()

    if not opus_dll.is_file():
        parser.error(f"Opus DLL not found: {opus_dll}")

    if not target.is_file():
        parser.error(f"Python script not found: {target}")

    # Keep DLL search directories active while Python runs.
    dll_handles = []

    for directory in [
        opus_dll.parent,
        *map(Path, args.dll_dir),
    ]:
        directory = directory.resolve()

        if not directory.is_dir():
            parser.error(f"Directory not found: {directory}")

        try:
            dll_handles.append(
                os.add_dll_directory(str(directory))
            )
        except OSError as exc:
            parser.error(
                f"Unable to add DLL directory: {directory}\n"
                f"Details: {exc}"
            )

    # Load and validate the native Opus library.
    try:
        native_opus = ctypes.CDLL(str(opus_dll))

        native_opus.opus_get_version_string.restype = ctypes.c_char_p
        version = native_opus.opus_get_version_string()

        if not version:
            parser.error(
                "The Opus DLL returned an empty version string."
            )

    except (OSError, AttributeError) as exc:
        parser.error(
            f"Unable to load a valid Opus DLL: {opus_dll}\n"
            "Check --dll-dir for missing runtime dependencies.\n"
            f"Details: {exc}"
        )

    # opuslib-next searches for "opus", which may not
    # resolve a Windows library named "libopus.dll".
    original_find = ctypes.util.find_library

    def find_opus(name):
        if name == "opus":
            return str(opus_dll)
        return original_find(name)

    ctypes.util.find_library = find_opus

    # Execute the requested Python script with its arguments.
    sys.path.insert(0, str(target.parent))
    sys.argv = [str(target), *args.script_args]

    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
