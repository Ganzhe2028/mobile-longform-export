# Mobile Longform Export

[English](README.md)

Mobile Longform Export 是一个本地 macOS 工具，可以把 Markdown 转成适合 iPhone 阅读和分享的长文 PDF 与分页 PNG。

它主要面向中英混排长文，不是纸张打印排版工具。渲染器使用 iPhone 级阅读画布：`402 x 874 CSS px`，`3x` 输出，最终页面尺寸为 `1206 x 2622`。

## 功能

- 原生 macOS GUI，应用名为 `mobileexport`
- 支持粘贴 Markdown 文本
- 支持选择或拖入 `.md` / `.markdown` 文件
- 每次导出完整 PDF 和逐页 PNG
- 所有输入和输出都保留在本机
- macOS 上默认使用 SF Pro 处理英文和数字，使用 PingFang SC 处理中文

## 环境要求

- macOS 12 或更新版本
- Python 3.10 或更新版本
- Xcode 或 Xcode Command Line Tools，用于编译 AppKit 启动器
- Python 依赖：

```bash
python3 -m pip install -r requirements.txt
```

## 安装

在项目目录里运行：

```bash
python3 install_mac_tool.py
```

安装脚本会创建：

- App：`~/Applications/mobileexport.app`
- 运行时文件：`~/Library/Application Support/MobileLongformExport/bin`
- 配置文件：`~/Library/Application Support/MobileLongformExport/config.json`

安装后的 app 会调用 Application Support 下的运行时副本，因此 Spotlight 和 Finder 不需要读取源码目录权限。

## 使用

GUI 流程：

1. 打开 Spotlight，输入 `mobileexport`。
2. 按 Return 打开窗口。
3. 粘贴 Markdown，或拖入/点击选择一个 Markdown 文件。
4. 点击 `导出`。
5. 工具会打开输出文件夹，并把 PDF 路径复制到剪贴板。

CLI 流程：

```bash
python3 mobile_longform_export.py --input samples/sample.md
python3 mobile_longform_export.py --clipboard
python3 mobile_longform_export.py --input samples/sample.md --author "Your Name"
python3 mobile_longform_export.py --input samples/sample.md --hide-author
```

## 输出

默认输出目录：

```text
~/Downloads/MobileLongformExports
```

每次导出会创建一个独立目录，例如：

```text
20260501-001200-Article-Title/
  mobile-longform.reader-screen-pages.pdf
  mobile-longform-page-01.png
  mobile-longform-page-02.png
```

默认配置：

```json
{
  "author": "Isaac's Agent",
  "output_root": "~/Downloads/MobileLongformExports",
  "reveal": true,
  "copy_pdf_path": true
}
```

修改默认值：

```text
~/Library/Application Support/MobileLongformExport/config.json
```

## 排版默认值

- 英文和数字：SF Pro
- 中文：PingFang SC
- 页面尺寸：`1206 x 2622`
- 正文字号：`16.67 CSS px`
- 正文行高比例：`1.64`
- 正文左右边距：`28 CSS px`
- 渲染时会处理中英文混排间距和英文 tracking
- 面向中文语境的英文直引号会规范化为中文弯引号
- 在渲染器可控范围内，会修复行首标点和过短尾行

## 隐私

Mobile Longform Export 完全在本机运行。它不会上传 Markdown 内容、生成的 PDF、生成的 PNG 或配置文件。

## 验证

编译检查：

```bash
python3 -m py_compile mobile_longform_export.py install_mac_tool.py render_mobile_reader_v3.py
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swiftc mobileexport_app.swift -o /private/tmp/mobileexport-compile-check
```

Smoke test：

```bash
python3 mobile_longform_export.py --input samples/sample.md --output-root /private/tmp/mobile-longform-export-smoke --max-pages 1 --no-reveal --no-copy-pdf-path
```

生成的 PNG 应为 `1206 x 2622`。

## License

MIT
