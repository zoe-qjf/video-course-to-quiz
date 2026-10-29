---
name: video-course-to-quiz
description: 把视频课程转成可复习的三件套：全文转写、结构化大纲、带原视频时间戳的自测题。当用户给出视频链接（YouTube、B站、本地文件）并要求总结内容、出大纲、出题自测、巩固知识点时使用；也适用于把一个播放列表批量转成学习资料。内置下载、本地 ASR 转写、关键帧抽取和题目页渲染脚本。
agent_created: true
---

# 视频 → 大纲 → 自测题

把任意视频课程转成三份东西：**全文转写**（机器用）、**结构化大纲**（人用）、**自测题 HTML**（复习用）。

核心原则：**重活交给脚本，模型只做理解和出题。** 转写、抽帧、渲染 HTML 都不消耗对话 token，只有读进上下文的内容才消耗。

## 何时使用

- 用户给视频链接，要"主要内容 / 大纲 / 笔记 / 出几道题 / 帮我巩固"。
- 用户要把一个播放列表批量转成学习材料。
- 不适用：只要一句视频简介、或视频没有可用音频轨。

## 环境准备（只需一次）

需要 Python **3.10+**。虚拟环境可选，但强烈建议建一个，避免污染系统环境。

```bash
# 建一个专用 venv（推荐，只需一次）
python -m venv .venv
# macOS / Linux
PY=".venv/bin/python"
# Windows (Git Bash)
# PY=".venv/Scripts/python.exe"
# Windows (PowerShell)
# $PY = ".venv\Scripts\python.exe"

"$PY" -c "import yt_dlp, faster_whisper, av, PIL" 2>/dev/null || \
  "$PY" -m pip install --disable-pip-version-check yt-dlp faster-whisper "av==13.1.0" pillow
```

没有 `python` 命令就换成 `python3`。后面所有脚本都用同一个 `$PY` 调用。

`av` 必须是 13.x：14+ 移除了 `metadata_errors`，faster-whisper 会直接崩。**不要升级 av。**

## 工作流

设 `$SK` 为本 skill 目录，`$W` 为工作目录（建议 `./.video-kit/<slug>/`）。

### 1. 拉取素材

```bash
"$PY" "$SK/scripts/fetch_video.py" "<URL>" --out "$W" --video
```

- 自动依次尝试：环境代理 → 本地 7890/7891/7897/10809 端口 → 直连，第一个通的就用。
- 产出 `meta.json`（标题/时长/章节/字幕语言/描述）、`audio.m4a`、`video.mp4`（≤480p，仅抽帧用）。
- **先看 `meta.json` 的 `subtitle_langs`**：非空说明有官方字幕，直接用它，跳过转写。

### 2. 拿到文字（二选一）

```bash
# A. 有字幕：读 subs.*.vtt，去掉时间轴和重复行，整理成 [mm:ss] 一行一段的 transcript.txt

# B. 无字幕：本地 ASR
"$PY" "$SK/scripts/transcribe.py" "$W/audio.m4a" --out "$W" --model small --lang zh
```

- 首次运行下载模型（走 hf-mirror，约 460MB），之后走离线缓存。
- 26 分钟音频在 8 核 CPU 上约 6 分钟，**必须放后台跑**，不要前台等。
- 中文视频把 `--prompt` 换成该领域术语清单，识别率明显提升。

### 3. 抽关键帧（有幻灯片/图表时才需要）

```bash
"$PY" "$SK/scripts/pick_frames.py" "$W/video.mp4" --out "$W/frames" --max 12
```

脚本按帧间差异挑"画面真正变了"的帧，默认最多 12 张。**这一步决定准确率**：术语定义、公式、表格几乎都在画面上，只听音频会漏掉准确措辞。

### 4. 阅读（token 花在这里）

- `transcript.txt` **只读一次**，不要分段反复读。
- 只读 `pick_frames.py` 打印出来的那几张，不要读全量。
- 长视频（>60 分钟）先只读时间戳骨架，锁定 3–5 个核心段落再细读。

### 5. 产出大纲

写成 `<slug>-大纲.md`，固定四段，**不抄原话长段**：

```markdown
# <视频标题>
> 频道 / 时长 / 链接

## 一句话结论

## 论证脉络
| 时间 | 讲了什么 | 关键结论 |
|---|---|---|

## 核心概念（5–12 条）
- **术语**：定义 + 它解决的问题

## 容易误解的点
```

### 6. 产出题目

先写 `questions.json`（结构见下），再渲染，**绝不手写 HTML**：

```bash
"$PY" "$SK/scripts/build_quiz.py" "$W/questions.json" "$W/<slug>-自测题.html"
```

JSON 结构：

```json
{
  "title": "课程名 · 主题 · 自测题",
  "subtitle": "视频标题 · 频道 · 时长",
  "source": "题目依据视频实际讲解内容编写，时间戳对应原视频进度。",
  "knowledge_points": ["要点1", "要点2"],
  "questions": [
    {"type":"judge","ts":"02:11","q":"...","options":["正确","错误"],"answer":[1],"explain":"..."},
    {"type":"single","ts":"04:57","q":"...","options":["A","B","C","D"],"answer":[2],"explain":"..."},
    {"type":"multi","ts":"08:29","q":"...","options":["A","B","C"],"answer":[0,2],"explain":"..."},
    {"type":"open","ts":"24:44","q":"...","sample":"参考答案"}
  ]
}
```

出题规则：

- `answer` 是 **0 起始下标**；多选至少 2 个答案。
- 每题必须带 `ts`，取自转写稿的时间戳——做错的人要能跳回去看。
- `explain` 里用 `<q>原话</q>` 包住讲师的原句，这是这套题唯一比通用题库强的地方。
- 题型配比建议：判断 25% / 单选 45% / 多选 15% / 简答 15%。
- 至少 2 道"陷阱题"：把视频里明确否定的做法做成错误选项。
- 只考视频讲过的内容，不要扩写视频没提的通识。

最后 `present_files` 同时给出 `大纲.md` 和 `自测题.html`。

## Token 纪律（重要）

| 做法 | 后果 |
|---|---|
| 转写全文读两遍 | 白烧 1 倍 token |
| 读全部抽帧 | 白烧约 3 万 token，且大部分是重复画面 |
| 手写 500 行 HTML | 每次约 8k token，还容易写错 |
| 只写 JSON + 跑 build_quiz.py | 约 2k token，零出错概率 |
| 让子代理跑脚本、只回传结果 | 中间日志不进主对话 |

视频超过 90 分钟时，改用子代理执行第 1–3 步，主对话只接收"标题 + 大纲骨架 + 核心段落"。**转写文本是唯一无法压缩的开销**——它必须进上下文，模型才能从中出题。

## 常见故障

代理不通、字幕缺失、模型下载失败、av 版本冲突、抽帧全黑：见 `references/troubleshooting.md`。
