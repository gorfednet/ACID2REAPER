# Building installers and app bundles

**ACID2Reaper** (first public beta) binaries are built with **PyInstaller** (`packaging/pyinstaller.spec`). Run the **macOS** script on a Mac, the **Linux** script on Linux, and the **Windows** script on Windows (PyInstaller targets the host OS). GitHub Actions also exercises tests on all three OS families. Every release build must pass the changelog check:

```bash
python scripts/verify_changelog.py
```

Install the optional dependency group:

```bash
pip install ".[pyinstaller]"
```

## macOS — `.app` + `.dmg`

From the repository root:

```bash
chmod +x packaging/build_mac_dmg.sh
./packaging/build_mac_dmg.sh
```

Outputs:

- `dist/ACID2Reaper.app` — GUI application bundle
- `dist/ACID2Reaper-macos.dmg` — compressed disk image for distribution

**Code signing / notarization:** For public distribution outside your machine, sign the `.app` with your Apple Developer ID and staple a notarization ticket (Apple documentation). The scripts here do not run `codesign`.

**Icon:** The spec embeds the multi-resolution `assets/acid2reaper.icns` in the app bundle.

If `codesign` warns about “resource fork” when building, clear extended attributes: `xattr -cr dist/ACID2Reaper.app`, then sign or rebuild.

## Windows — `ACID2Reaper.exe` (folder build)

From PowerShell at the project root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build_windows.ps1
```

Outputs:

- `dist/ACID2Reaper/ACID2Reaper.exe` plus DLLs and support files (onedir layout)
- `dist/ACID2Reaper-windows.zip` — the same folder tree, zipped for distribution

To ship a **single** `.exe` only, add a second PyInstaller invocation with `EXE(..., onefile=True)` or use **Inno Setup** / **WiX** to build a classic installer that copies the folder.

**Icon:** The spec embeds the multi-resolution `assets/acid2reaper.ico` in the executable.

## Linux — tarball

```bash
chmod +x packaging/build_linux.sh
./packaging/build_linux.sh
```

Outputs:

- `dist/ACID2Reaper/` — runnable tree
- `dist/ACID2Reaper-linux-<arch>.tar.gz`

**AppImage:** Many projects run `appimagetool` on a prepared AppDir; that is not automated here but is compatible with the PyInstaller output tree.

## Manual PyInstaller

```bash
pip install .
pip install ".[pyinstaller]"
python scripts/verify_changelog.py
pyinstaller packaging/pyinstaller.spec
```

## Troubleshooting

- **Tkinter missing (Linux):** Install your distro’s `python3-tk` package before building.
- **Missing `rpp`:** Ensure `pip install .` ran successfully so site-packages contains `acid2reaper` and dependencies.
