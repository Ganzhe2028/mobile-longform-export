import Cocoa
import UniformTypeIdentifiers

private enum InputMode: Int {
    case pastedText = 0
    case markdownFile = 1
}

private enum AppColor {
    static let window = NSColor(calibratedWhite: 0.98, alpha: 1.0)
    static let surface = NSColor.white
    static let surfaceSubtle = NSColor(calibratedWhite: 0.955, alpha: 1.0)
    static let border = NSColor(calibratedWhite: 0.82, alpha: 1.0)
    static let borderStrong = NSColor(calibratedRed: 0.03, green: 0.42, blue: 0.95, alpha: 1.0)
    static let text = NSColor(calibratedWhite: 0.12, alpha: 1.0)
    static let secondaryText = NSColor(calibratedWhite: 0.43, alpha: 1.0)
    static let tertiaryText = NSColor(calibratedWhite: 0.56, alpha: 1.0)
    static let accentFill = NSColor(calibratedRed: 0.03, green: 0.42, blue: 0.95, alpha: 0.08)
}

private func isMarkdownFile(_ url: URL) -> Bool {
    let ext = url.pathExtension.lowercased()
    return ext == "md" || ext == "markdown"
}

private func markdownURL(from pasteboard: NSPasteboard) -> URL? {
    guard let items = pasteboard.pasteboardItems else {
        return nil
    }

    for item in items {
        guard let raw = item.string(forType: .fileURL),
              let url = URL(string: raw),
              isMarkdownFile(url) else {
            continue
        }
        return url
    }

    return nil
}

private func cleanedTitle(from markdown: String) -> String {
    for rawLine in markdown.components(separatedBy: .newlines) {
        var line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        while line.hasPrefix("#") {
            line.removeFirst()
        }
        line = line.trimmingCharacters(in: .whitespacesAndNewlines)
        line = line.replacingOccurrences(of: "**", with: "")
        line = line.replacingOccurrences(of: "__", with: "")
        line = line.replacingOccurrences(of: "`", with: "")
        line = line.replacingOccurrences(of: "[", with: "")
        line = line.replacingOccurrences(of: "]", with: "")
        line = line.replacingOccurrences(of: "(", with: " ")
        line = line.replacingOccurrences(of: ")", with: " ")
        line = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if !line.isEmpty {
            return String(line.prefix(60))
        }
    }
    return "Markdown Export"
}

private func safeFileStem(_ value: String) -> String {
    let invalid = CharacterSet(charactersIn: "/:\\?%*|\"<>")
    let parts = value.unicodeScalars.map { scalar -> String in
        if invalid.contains(scalar) || CharacterSet.newlines.contains(scalar) {
            return "-"
        }
        return String(scalar)
    }
    let stem = parts.joined().trimmingCharacters(in: .whitespacesAndNewlines)
    return stem.isEmpty ? "Markdown Export" : stem
}

final class MarkdownDropZone: NSView {
    weak var controller: MainWindowController?

    private let titleLabel = NSTextField(labelWithString: "选择 .md 文件")
    private let detailLabel = NSTextField(labelWithString: "拖入文件，或点击这里选择")
    private var highlighted = false {
        didSet {
            updateAppearance()
        }
    }

    var selectedURL: URL? {
        didSet {
            if let selectedURL {
                titleLabel.stringValue = selectedURL.lastPathComponent
                detailLabel.stringValue = selectedURL.path
            } else {
                titleLabel.stringValue = "选择 .md 文件"
                detailLabel.stringValue = "拖入文件，或点击这里选择"
            }
            updateAppearance()
        }
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        setup()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setup()
    }

    private func setup() {
        wantsLayer = true
        registerForDraggedTypes([.fileURL])

        titleLabel.font = NSFont.systemFont(ofSize: 15, weight: .semibold)
        titleLabel.textColor = AppColor.text
        titleLabel.alignment = .left
        detailLabel.font = NSFont.systemFont(ofSize: 13)
        detailLabel.textColor = AppColor.secondaryText
        detailLabel.alignment = .left
        detailLabel.maximumNumberOfLines = 2
        detailLabel.lineBreakMode = .byTruncatingMiddle

        let stack = NSStackView(views: [titleLabel, detailLabel])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 4
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)

        NSLayoutConstraint.activate([
            stack.centerYAnchor.constraint(equalTo: centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 18),
            stack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -18),
        ])

        updateAppearance()
    }

    private func updateAppearance() {
        layer?.cornerRadius = 10
        layer?.borderWidth = selectedURL == nil ? 1.5 : 2
        layer?.borderColor = (highlighted || selectedURL != nil ? AppColor.borderStrong : AppColor.border).cgColor
        layer?.backgroundColor = (highlighted || selectedURL != nil ? AppColor.accentFill : AppColor.surface).cgColor
    }

    override func mouseDown(with event: NSEvent) {
        guard controller?.isBusy == false else {
            return
        }
        controller?.chooseFile()
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        guard markdownURL(from: sender.draggingPasteboard) != nil else {
            return []
        }
        highlighted = true
        return .copy
    }

    override func draggingExited(_ sender: NSDraggingInfo?) {
        highlighted = false
    }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        highlighted = false
        guard let url = markdownURL(from: sender.draggingPasteboard) else {
            return false
        }
        controller?.setSelectedFile(url)
        return true
    }
}

final class MainWindowController: NSWindowController, NSWindowDelegate, NSTextViewDelegate {
    private let pythonPath: String
    private let cliPath: String
    private let textView = NSTextView()
    private let textScrollView = NSScrollView()
    private let dropZone = MarkdownDropZone(frame: .zero)
    private let exportButton = NSButton(title: "导出", target: nil, action: nil)
    private let statusLabel = NSTextField(labelWithString: "等待输入")

    private var activeSource = InputMode.pastedText
    private var selectedFileURL: URL?
    private var isExporting = false

    var isBusy: Bool {
        isExporting
    }

    init(pythonPath: String, cliPath: String) {
        self.pythonPath = pythonPath
        self.cliPath = cliPath

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 640, height: 520),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "mobileexport"
        window.minSize = NSSize(width: 560, height: 440)
        window.appearance = NSAppearance(named: .aqua)
        window.isMovableByWindowBackground = true
        super.init(window: window)
        window.delegate = self
        setupUI()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func setupUI() {
        guard let contentView = window?.contentView else {
            return
        }
        contentView.wantsLayer = true
        contentView.layer?.backgroundColor = AppColor.window.cgColor

        let titleLabel = NSTextField(labelWithString: "导出 Markdown")
        titleLabel.font = NSFont.systemFont(ofSize: 22, weight: .semibold)
        titleLabel.textColor = AppColor.text

        let subtitleLabel = NSTextField(labelWithString: "生成适合手机阅读的 PDF 和分页 PNG。")
        subtitleLabel.font = NSFont.systemFont(ofSize: 13)
        subtitleLabel.textColor = AppColor.secondaryText

        let pasteLabel = NSTextField(labelWithString: "粘贴 Markdown")
        pasteLabel.font = NSFont.systemFont(ofSize: 13, weight: .semibold)
        pasteLabel.textColor = AppColor.text

        textView.isRichText = false
        textView.isAutomaticQuoteSubstitutionEnabled = false
        textView.isAutomaticDashSubstitutionEnabled = false
        textView.font = NSFont.monospacedSystemFont(ofSize: 14, weight: .regular)
        textView.textColor = AppColor.text
        textView.backgroundColor = AppColor.surface
        textView.allowsUndo = true
        textView.string = ""
        textView.delegate = self
        textView.textContainerInset = NSSize(width: 12, height: 12)

        textScrollView.borderType = .noBorder
        textScrollView.hasVerticalScroller = true
        textScrollView.drawsBackground = true
        textScrollView.backgroundColor = AppColor.surface
        textScrollView.documentView = textView
        textScrollView.wantsLayer = true
        textScrollView.layer?.cornerRadius = 10
        textScrollView.layer?.borderWidth = 1
        textScrollView.layer?.borderColor = AppColor.border.cgColor
        textScrollView.layer?.backgroundColor = AppColor.surface.cgColor
        textScrollView.translatesAutoresizingMaskIntoConstraints = false
        textScrollView.heightAnchor.constraint(greaterThanOrEqualToConstant: 250).isActive = true

        let fileLabel = NSTextField(labelWithString: "或者选择文件")
        fileLabel.font = NSFont.systemFont(ofSize: 13, weight: .semibold)
        fileLabel.textColor = AppColor.text

        dropZone.controller = self
        dropZone.translatesAutoresizingMaskIntoConstraints = false
        dropZone.heightAnchor.constraint(equalToConstant: 82).isActive = true

        exportButton.target = self
        exportButton.action = #selector(export(_:))
        exportButton.keyEquivalent = "\r"
        exportButton.bezelStyle = .rounded
        exportButton.controlSize = .large

        statusLabel.font = NSFont.systemFont(ofSize: 13)
        statusLabel.textColor = AppColor.secondaryText
        statusLabel.lineBreakMode = .byTruncatingMiddle

        let headerText = NSStackView(views: [titleLabel, subtitleLabel])
        headerText.orientation = .vertical
        headerText.alignment = .leading
        headerText.spacing = 4

        let headerRow = NSStackView(views: [headerText, exportButton])
        headerRow.orientation = .horizontal
        headerRow.alignment = .top
        headerRow.spacing = 16
        headerText.setContentHuggingPriority(.defaultLow, for: .horizontal)
        exportButton.setContentHuggingPriority(.required, for: .horizontal)

        let root = NSStackView(views: [headerRow, pasteLabel, textScrollView, fileLabel, dropZone, statusLabel])
        root.orientation = .vertical
        root.alignment = .leading
        root.spacing = 10
        root.edgeInsets = NSEdgeInsets(top: 22, left: 24, bottom: 20, right: 24)
        root.translatesAutoresizingMaskIntoConstraints = false
        contentView.addSubview(root)

        for view in [headerRow, pasteLabel, textScrollView, fileLabel, dropZone, statusLabel] {
            view.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -48).isActive = true
        }

        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            root.topAnchor.constraint(equalTo: contentView.topAnchor),
            root.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
        ])

        updateStatus()
    }

    func textDidChange(_ notification: Notification) {
        if !textView.string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            activeSource = .pastedText
        }
        updateStatus()
    }

    private func updateStatus() {
        if isExporting {
            statusLabel.stringValue = "正在导出..."
            return
        }
        let hasText = !textView.string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        if activeSource == .pastedText && hasText {
            statusLabel.stringValue = "将导出粘贴内容"
        } else if activeSource == .markdownFile, let selectedFileURL {
            statusLabel.stringValue = "将导出 \(selectedFileURL.lastPathComponent)"
        } else if let selectedFileURL {
            statusLabel.stringValue = "已选择 \(selectedFileURL.lastPathComponent)"
        } else {
            statusLabel.stringValue = "粘贴 Markdown，或选择一个 .md 文件"
        }
    }

    func setSelectedFile(_ url: URL) {
        selectedFileURL = url
        dropZone.selectedURL = url
        activeSource = .markdownFile
        updateStatus()
    }

    func acceptExternalFile(_ url: URL) {
        guard isMarkdownFile(url) else {
            showAlert(title: "文件格式不支持", message: "请选择 .md 或 .markdown 文件。")
            return
        }
        setSelectedFile(url)
    }

    @objc func chooseFile() {
        guard !isExporting else {
            return
        }
        guard let window else {
            return
        }

        let panel = NSOpenPanel()
        panel.title = "选择 Markdown 文件"
        panel.prompt = "选择"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [
            UTType(filenameExtension: "md") ?? .plainText,
            UTType(filenameExtension: "markdown") ?? .plainText,
        ]

        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let url = panel.url else {
                return
            }
            self?.setSelectedFile(url)
        }
    }

    @objc private func export(_ sender: Any?) {
        guard !isExporting else {
            return
        }

        do {
            let inputPath: String
            switch resolvedExportSource() {
            case .pastedText:
                inputPath = try preparePastedMarkdown()
            case .markdownFile:
                inputPath = try prepareSelectedFile()
            }
            runExport(inputPath: inputPath)
        } catch {
            showAlert(title: "无法导出", message: error.localizedDescription)
        }
    }

    private func resolvedExportSource() -> InputMode {
        let hasText = !textView.string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        if activeSource == .pastedText && hasText {
            return .pastedText
        }
        if activeSource == .markdownFile && selectedFileURL != nil {
            return .markdownFile
        }
        if hasText {
            return .pastedText
        }
        return .markdownFile
    }

    private func preparePastedMarkdown() throws -> String {
        let markdown = textView.string.trimmingCharacters(in: .whitespacesAndNewlines)
        if markdown.isEmpty {
            throw NSError(domain: "mobileexport", code: 1, userInfo: [NSLocalizedDescriptionKey: "请先粘贴 Markdown 文本。"])
        }

        let supportURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/MobileLongformExport/gui-input", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: supportURL, withIntermediateDirectories: true)

        let fileName = safeFileStem(cleanedTitle(from: markdown)) + ".md"
        let fileURL = supportURL.appendingPathComponent(fileName)
        try markdown.write(to: fileURL, atomically: true, encoding: .utf8)
        return fileURL.path
    }

    private func prepareSelectedFile() throws -> String {
        guard let selectedFileURL else {
            throw NSError(domain: "mobileexport", code: 2, userInfo: [NSLocalizedDescriptionKey: "请先选择或拖入一个 .md 文件。"])
        }
        guard isMarkdownFile(selectedFileURL) else {
            throw NSError(domain: "mobileexport", code: 3, userInfo: [NSLocalizedDescriptionKey: "文件格式不支持。请选择 .md 或 .markdown 文件。"])
        }
        guard FileManager.default.fileExists(atPath: selectedFileURL.path) else {
            throw NSError(domain: "mobileexport", code: 4, userInfo: [NSLocalizedDescriptionKey: "选择的文件不存在。"])
        }
        return selectedFileURL.path
    }

    private func runExport(inputPath: String) {
        guard FileManager.default.fileExists(atPath: cliPath) else {
            showAlert(title: "导出工具缺失", message: "找不到导出脚本：\(cliPath)")
            return
        }
        guard FileManager.default.isExecutableFile(atPath: pythonPath) else {
            showAlert(title: "Python 不可用", message: "找不到可执行 Python：\(pythonPath)")
            return
        }

        isExporting = true
        exportButton.isEnabled = false
        textView.isEditable = false
        updateStatus()

        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = [cliPath, "--input", inputPath]

        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            do {
                try process.run()
                process.waitUntilExit()

                let output = String(data: outputPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let errorOutput = String(data: errorPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""

                DispatchQueue.main.async {
                    self?.finishExport(status: process.terminationStatus, output: output, errorOutput: errorOutput)
                }
            } catch {
                DispatchQueue.main.async {
                    self?.finishWithError(error.localizedDescription)
                }
            }
        }
    }

    private func finishExport(status: Int32, output: String, errorOutput: String) {
        isExporting = false
        exportButton.isEnabled = true
        textView.isEditable = true

        if status == 0 {
            statusLabel.stringValue = "导出完成，PDF 路径已复制到剪贴板。"
            return
        }

        let message = [errorOutput, output].filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.joined(separator: "\n")
        showAlert(title: "导出失败", message: message.isEmpty ? "导出进程退出，未返回错误信息。" : message)
        statusLabel.stringValue = "导出失败"
    }

    private func finishWithError(_ message: String) {
        isExporting = false
        exportButton.isEnabled = true
        textView.isEditable = true
        showAlert(title: "导出失败", message: message)
        statusLabel.stringValue = "导出失败"
    }

    private func showAlert(title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .warning
        if let window {
            alert.beginSheetModal(for: window)
        } else {
            alert.runModal()
        }
    }

    func windowWillClose(_ notification: Notification) {
        NSApp.terminate(nil)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var mainWindowController: MainWindowController?
    private var pendingFileURLs: [URL] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        let bundle = Bundle.main
        let pythonPath = bundle.object(forInfoDictionaryKey: "MLEPythonPath") as? String ?? "/usr/bin/python3"
        let cliPath = bundle.object(forInfoDictionaryKey: "MLECLIPath") as? String ?? ""

        let controller = MainWindowController(pythonPath: pythonPath, cliPath: cliPath)
        mainWindowController = controller
        controller.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)

        if let firstURL = pendingFileURLs.first {
            controller.acceptExternalFile(firstURL)
            pendingFileURLs.removeAll()
        }
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        if let controller = mainWindowController {
            if let firstURL = urls.first {
                controller.acceptExternalFile(firstURL)
            }
        } else {
            pendingFileURLs = urls
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            mainWindowController?.showWindow(nil)
        }
        NSApp.activate(ignoringOtherApps: true)
        return true
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
