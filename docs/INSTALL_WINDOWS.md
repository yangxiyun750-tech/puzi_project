# ScoreRebuild Windows 安装指南

适用对象：希望把印刷管弦乐总谱 PDF 重建成可编辑 MuseScore 工程、但不熟悉编程的音乐教师。

本指南只安装和检查环境，不会处理您的乐谱。

## 1. 下载项目

可以使用 Git clone，也可以从代码托管页面下载 ZIP。解压后，目录中应能看到：

```text
score-rebuild-manifest.json
score-rebuild.cmd
.agents\skills\orchestral-score-rebuild\SKILL.md
```

以下命令都在这个项目目录中运行。

## 2. 安装四个外部程序

### Python 3.12

从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/) 安装 Python 3.12（64 位）。本项目当前只验证 Python 3.12，不要直接改用 3.13/3.14。

### MuseScore Studio 4

从 [MuseScore 官方下载页](https://musescore.org/en/download) 安装 MuseScore Studio 4。已验证版本为 4.7.4。普通安装位置通常可以被 doctor 自动发现。

### Audiveris

从 [Audiveris 官方 GitHub Releases](https://github.com/Audiveris/audiveris/releases) 安装 Windows 版本。已验证版本为 5.11.0。保留安装程序附带的 Java runtime。

### Poppler / pdftoppm

Windows 没有由 Poppler 项目直接提供的统一官方安装器。请安装可信的 Windows Poppler 构建，并确认其中存在 `pdftoppm.exe`。如果 doctor 找不到它，可设置：

```powershell
$env:PDFTOPPM_EXE = '您实际安装目录\bin\pdftoppm.exe'
```

不要复制开发者电脑上的 Codex cache 路径。

## 3. 建立 Python 环境

在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`pdfplumber` 不属于核心运行依赖。只有需要旧版/高级 PDF 文字提取辅助程序时才安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
```

## 4. 安装 MusicXML 4.0 schema

```powershell
.\.venv\Scripts\python.exe -m score_rebuild schema-install
```

这些 XSD 不随仓库打包；命令会从固定的 W3C MusicXML v4.0 commit 下载并校验 SHA-256。详情见 `docs/MUSICXML_SCHEMA_SETUP.md`。

## 5. 让 Agent 看到一个 ScoreRebuild Skill

唯一入口是：

```text
.agents\skills\orchestral-score-rebuild\SKILL.md
```

- ZCode：项目配置已经提供 `SCORE_REBUILD` profile，只启用这个 Skill。
- Codex：打开项目根目录，确认任务中能看到 `orchestral-score-rebuild`；使用时明确写 `$orchestral-score-rebuild`。
- 其他 WorkBuddy 风格 Agent：让它在执行前完整阅读上面的 `SKILL.md` 和其中直接引用的文件。

不需要手工依次调用多个内部 Skill。不同 Agent 的兼容说明见 `docs/AGENT_INTEGRATION.md`。

## 6. 运行环境 doctor

```powershell
.\score-rebuild.cmd doctor
```

每项都会显示 `PASS`、`WARN` 或 `FAIL`，并给出版本、路径和修复方法。

如果程序装在非标准位置，可以只在当前 PowerShell 设置：

```powershell
$env:AUDIVERIS_EXE = '实际路径\Audiveris.exe'
$env:MUSESCORE_EXE = '实际路径\MuseScore4.exe'
$env:PDFTOPPM_EXE = '实际路径\pdftoppm.exe'
```

修复所有 `FAIL` 后再次运行 doctor。

## 7. 声明 Agent/人工能力

不要假设 Agent 自动支持看图。示例：代码推理已验证、视觉交给人工：

```powershell
.\score-rebuild.cmd capability-doctor `
  --code-provider '您的 Agent 名称' `
  --code-verified `
  --human-reviewer '人工复核者姓名'
```

结果中 `VISUAL_REVIEW: NOT_CONFIGURED` 不是伪装的 PASS；系统会要求人工逐页视觉检查。

只有已经用图片输入实际验证过视觉能力时，才加入：

```powershell
--visual-provider '视觉模型/Agent 名称' --visual-verified
```

## 8. 运行无版权 smoke test

```powershell
.\score-rebuild.cmd smoke-test
```

它只使用仓库自产的一个小型 MusicXML 文件，检查：

```text
MusicXML → XSD → MuseScore MSCZ → MuseScore PDF → Poppler PNG
```

Audiveris 和 Java 的实际 CLI 启动由 doctor 检查。这个 smoke test 不是音乐识别质量测试，也不会使用《天使的脸》或其他受版权保护谱面。

## 9. 何时可以开始真实项目

只有以下条件同时满足才开始：

- environment doctor 没有 `FAIL`；
- code reasoning 已明确验证；
- visual review 已验证，或者人工视觉复核者已明确可用；
- human review fallback 已明确可用；
- smoke test 通过；
- 您有权处理输入 PDF。

然后只向 Agent 提交一个入口请求：使用 `orchestral-score-rebuild`。不要跳过 Skill 中的 prototype、原调核对和人工歧义处理阶段。
