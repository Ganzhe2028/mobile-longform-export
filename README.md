# Mobile Longform Export

[中文说明](README.zh-CN.md)

Mobile Longform Export is a local macOS tool that turns Markdown into
iPhone-readable longform PDF and paged PNG files.

It is built for Chinese-English mixed articles that are shared to phone readers.
The renderer targets an iPhone-class reading canvas: `402 x 874 CSS px` at `3x`
scale, exported as `1206 x 2622` PDF pages and matching PNG pages.

## Features

- Native macOS GUI launched as `mobileexport`
- Paste Markdown text or select a `.md` / `.markdown` file
- Exports a complete PDF and individual page PNG files
- Keeps all input and output local on your Mac
- Uses SF Pro for Latin text and PingFang SC for Chinese text on macOS

## Requirements

- macOS 12 or newer
- Python 3.10 or newer
- Xcode or Xcode Command Line Tools for compiling the AppKit launcher
- Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Install

Run from this project directory:

```bash
python3 install_mac_tool.py
```

The installer creates:

- App: `~/Applications/mobileexport.app`
- Runtime copy: `~/Library/Application Support/MobileLongformExport/bin`
- Config: `~/Library/Application Support/MobileLongformExport/config.json`

The installed app uses the runtime copy under Application Support, so Spotlight
and Finder do not need permission to read this source directory.

## Use

GUI flow:

1. Open Spotlight and type `mobileexport`.
2. Press Return to open the app window.
3. Paste Markdown into the text box, or drag/click to choose a Markdown file.
4. Click `导出`.
5. The output folder opens in Finder, and the PDF path is copied to the clipboard.

CLI flow:

```bash
python3 mobile_longform_export.py --input samples/sample.md
python3 mobile_longform_export.py --clipboard
python3 mobile_longform_export.py --input samples/sample.md --author "Your Name"
python3 mobile_longform_export.py --input samples/sample.md --hide-author
```

## Output

Default output root:

```text
~/Downloads/MobileLongformExports
```

Each export creates a directory like:

```text
20260501-001200-Article-Title/
  mobile-longform.reader-screen-pages.pdf
  mobile-longform-page-01.png
  mobile-longform-page-02.png
```

Default config:

```json
{
  "author": "Isaac's Agent",
  "output_root": "~/Downloads/MobileLongformExports",
  "reveal": true,
  "copy_pdf_path": true
}
```

Edit the installed config file to change defaults:

```text
~/Library/Application Support/MobileLongformExport/config.json
```

## Typography Defaults

- Latin and numbers: SF Pro
- Chinese: PingFang SC
- Page size: `1206 x 2622`
- Body size: `16.67 CSS px`
- Body line-height ratio: `1.64`
- Body margin: `28 CSS px`
- Mixed Latin/CJK spacing and Latin tracking are applied during rendering
- Chinese-facing straight quotes are normalized to curly Chinese quotes
- Line-start punctuation and short final-line runts are repaired where possible

## Privacy

Mobile Longform Export runs locally. It does not upload Markdown content,
generated PDFs, generated PNGs, or config files to any service.

## Verify

Compile checks:

```bash
python3 -m py_compile mobile_longform_export.py install_mac_tool.py render_mobile_reader_v3.py
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swiftc mobileexport_app.swift -o /private/tmp/mobileexport-compile-check
```

Smoke test:

```bash
python3 mobile_longform_export.py --input samples/sample.md --output-root /private/tmp/mobile-longform-export-smoke --max-pages 1 --no-reveal --no-copy-pdf-path
```

The generated PNG should be `1206 x 2622`.

## License

MIT
