#!/usr/bin/env python3
import json
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = Path(sys.executable).resolve()
CLI = PROJECT_DIR / "mobile_longform_export.py"
RENDERER = PROJECT_DIR / "render_mobile_reader_v3.py"
SWIFT_SOURCE = PROJECT_DIR / "mobileexport_app.swift"
APP_SUPPORT = Path.home() / "Library/Application Support/MobileLongformExport"
BIN_DIR = APP_SUPPORT / "bin"
INSTALLED_CLI = BIN_DIR / "mobile_longform_export.py"
INSTALLED_RENDERER = BIN_DIR / "render_mobile_reader_v3.py"
CONFIG_PATH = APP_SUPPORT / "config.json"
APPLICATIONS_DIR = Path.home() / "Applications"
APP_PATH = APPLICATIONS_DIR / "mobileexport.app"
OLD_APP_PATH = APPLICATIONS_DIR / "Mobile Longform Export.app"
SERVICES_DIR = Path.home() / "Library/Services"
WORKFLOW_PATH = SERVICES_DIR / "Export Mobile Longform.workflow"
SWIFTC = Path("/usr/bin/swiftc")
XCRUN = Path("/usr/bin/xcrun")
XCODE_DEVELOPER_DIR = Path("/Applications/Xcode.app/Contents/Developer")
PBS = Path("/System/Library/CoreServices/pbs")
DEFAULT_AUTHOR = "Isaac's Agent"


def now_stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_config():
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    defaults = {
        "author": DEFAULT_AUTHOR,
        "output_root": str(Path.home() / "Downloads/MobileLongformExports"),
        "reveal": True,
        "copy_pdf_path": True,
    }

    config = {}
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = loaded
        except (OSError, json.JSONDecodeError):
            config = {}

    changed = False
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
            changed = True

    if changed or not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_runtime():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CLI, INSTALLED_CLI)
    shutil.copy2(RENDERER, INSTALLED_RENDERER)
    INSTALLED_CLI.chmod(0o755)
    INSTALLED_RENDERER.chmod(0o644)


def unique_retired_path(path, bucket):
    retired_dir = APP_SUPPORT / "retired" / bucket
    retired_dir.mkdir(parents=True, exist_ok=True)
    stem = path.name
    candidate = retired_dir / f"{stem}.{now_stamp()}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = retired_dir / f"{stem}.{now_stamp()}-{index}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a retired path for {path}")


def retire_existing(path, bucket):
    if not path.exists():
        return None
    destination = unique_retired_path(path, bucket)
    shutil.move(str(path), str(destination))
    return destination


def app_info_plist():
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": "mobileexport",
        "CFBundleIdentifier": "local.mobileexport",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "mobileexport",
        "CFBundleDisplayName": "mobileexport",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "MIT License",
        "MLEPythonPath": str(PYTHON),
        "MLECLIPath": str(INSTALLED_CLI),
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Markdown document",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": [
                    "net.daringfireball.markdown",
                    "public.plain-text",
                    "public.text",
                ],
                "CFBundleTypeExtensions": ["md", "markdown"],
            }
        ],
    }


def build_app_bundle():
    command, env = swift_compile_invocation()
    if not command:
        raise FileNotFoundError(SWIFTC)

    build_root = APP_SUPPORT / "build" / f"mobileexport-{now_stamp()}-{os.getpid()}"
    app_path = build_root / "mobileexport.app"
    contents = app_path / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    executable = macos_dir / "mobileexport"
    subprocess.run(command + [str(SWIFT_SOURCE), "-o", str(executable)], check=True, env=env)
    executable.chmod(0o755)
    (contents / "Info.plist").write_bytes(plistlib.dumps(app_info_plist(), sort_keys=False))
    return app_path, build_root


def swift_compile_invocation():
    if XCODE_DEVELOPER_DIR.exists() and XCRUN.exists():
        env = dict(os.environ)
        env["DEVELOPER_DIR"] = str(XCODE_DEVELOPER_DIR)
        return [str(XCRUN), "swiftc"], env
    if SWIFTC.exists():
        return [str(SWIFTC)], None
    return [], None


def install_app():
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    app_bundle, build_root = build_app_bundle()
    retired = []
    for existing in (APP_PATH, OLD_APP_PATH):
        retired_path = retire_existing(existing, "apps")
        if retired_path is not None:
            retired.append(retired_path)

    shutil.move(str(app_bundle), str(APP_PATH))
    try:
        build_root.rmdir()
    except OSError:
        pass
    return retired


def disable_quick_action():
    return retire_existing(WORKFLOW_PATH, "services")


def refresh_services_cache():
    if PBS.exists():
        subprocess.run([str(PBS), "-flush", "en", "zh-Hans"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([str(PBS), "-update", "en", "zh-Hans"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["/usr/bin/killall", "Finder"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    for required in (CLI, RENDERER, SWIFT_SOURCE):
        if not required.exists():
            raise FileNotFoundError(required)

    ensure_config()
    install_runtime()
    retired_apps = install_app()
    retired_workflow = disable_quick_action()
    refresh_services_cache()

    print(f"app: {APP_PATH}")
    if retired_apps:
        for path in retired_apps:
            print(f"retired app: {path}")
    if retired_workflow is not None:
        print(f"retired workflow: {retired_workflow}")
    print(f"config: {CONFIG_PATH}")
    print(f"runtime: {BIN_DIR}")


if __name__ == "__main__":
    main()
