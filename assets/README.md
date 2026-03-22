# Brand assets (ACID2Reaper)

## Logo

`acid2reaper_logo.png` — psychedelic “acid” inspired artwork with a stylized **scythe** motif (nod to REAPER’s grim‑reaper branding), suitable for marketing and app icons.

### macOS `.icns`

1. Create an `icon.iconset` folder with PNGs at standard sizes (16, 32, 128, 256, 512, …).
2. Run:

   ```bash
   iconutil -c icns icon.iconset -o acid2reaper.icns
   ```

3. Set `icon=` in `packaging/pyinstaller.spec` `BUNDLE()` to the `.icns` path.

### Windows `.ico`

Use an image editor or a tool like ImageMagick to export a multi-resolution `.ico` from the PNG, then add `--icon=...` to the PyInstaller `EXE()` section if you split GUI/CLI builds.

### Web / README

You may reference the PNG directly in documentation (keep file path stable for links).
