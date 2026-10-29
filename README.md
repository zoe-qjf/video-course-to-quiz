# video-course-to-quiz

把任意视频课程转成三样东西：**全文转写**、**结构化大纲**、**可自测的题目网页**。

给一个 YouTube / B站链接，或者一个本地视频文件，产出一份能复习的笔记 + 一套带时间戳的题目。做错题能跳回原视频那一秒。

## 它解决什么问题

看完一节两小时的课，三天后只记得"好像讲过什么"。

现有做法有两个坑：

- **让模型总结整段视频**：模型没看画面，术语、公式、表格全丢；而且转写文本会吃掉大量上下文。
- **自己手抄笔记**：抄得慢，抄完不复盘，等于没抄。

这个 skill 的做法是：**重活全部交给脚本，模型只负责理解和出题。**

转写、抽帧、渲染 HTML 都在本地跑，不消耗对话 token。只有真正需要读进上下文的内容（转写稿、关键帧）才花 token，而且规定了只能读一次。

## 产出

```
<slug>/
├── meta.json              标题 / 时长 / 章节 / 字幕语言
├── audio.m4a              音轨
├── video.mp4              低清视频（仅抽帧用）
├── transcript.txt         [mm:ss] 一行一段的全文转写
├── frames/                画面真正变化的关键帧
├── questions.json         题目数据
├── <slug>-大纲.md          四段式大纲：一句话结论 / 论证脉络 / 核心概念 / 容易误解的点
└── <slug>-自测题.html      可交互的自测网页
```

## 安装

这是个 agent skill，目录里必须有 `SKILL.md`。克隆到你的 skills 目录即可：

```bash
# WorkBuddy
git clone https://github.com/zoe-qjf/video-course-to-quiz.git ~/.workbuddy/skills/video-course-to-quiz

# Claude Code
git clone https://github.com/zoe-qjf/video-course-to-quiz.git ~/.claude/skills/video-course-to-quiz
```

Windows 下把 `~` 换成 `C:/Users/<你的用户名>`。

## 依赖

Python 3.10+，以及四个包：

```bash
python -m venv .venv
.venv/bin/python -m pip install yt-dlp faster-whisper "av==13.1.0" pillow
```

**`av` 必须锁在 13.x。** PyAV 14 删掉了 `metadata_errors` 参数，faster-whisper 会直接崩在 `TypeError`。不要升级。

`ffmpeg` 建议另外装一个（yt-dlp 合并音轨时会用到）。

## 脚本

四个独立脚本，都可以脱离 agent 单独跑：

| 脚本 | 作用 |
|---|---|
| `scripts/fetch_video.py` | 拉元数据 + 音轨 + 字幕 + 低清视频。自动轮询常见代理端口，挑第一个通的 |
| `scripts/transcribe.py` | 本地 faster-whisper 转写。首次下载模型走 hf-mirror，之后走离线缓存 |
| `scripts/pick_frames.py` | 按帧间差异挑"画面真的变了"的帧，默认最多 12 张 |
| `scripts/build_quiz.py` | 把 `questions.json` 渲染成自测题 HTML，带校验 |

```bash
PY=".venv/bin/python"

"$PY" scripts/fetch_video.py "<URL>" --out work/ --video
"$PY" scripts/transcribe.py work/audio.m4a --out work/ --model small --lang zh
"$PY" scripts/pick_frames.py work/video.mp4 --out work/frames --max 12
"$PY" scripts/build_quiz.py work/questions.json work/quiz.html
```

## 出题规则

每道题必须带 `ts`（时间戳，取自转写稿），这是这套题唯一比通用题库强的地方——做错了能跳回去看。

`explain` 里用 `<q>原话</q>` 包住讲师原句，复习时能对照原始措辞。

题型配比建议：判断 25% / 单选 45% / 多选 15% / 简答 15%。至少留 2 道"陷阱题"——把视频里明确否定的做法做成错误选项。

只考视频讲过的内容，不扩写视频没提的通识。

## 适用范围

**适用**：有音频轨的教学视频、讲座、播客录像、系列课程批量处理。

**不适用**：只要一句视频简介；纯音乐无讲解；纯幻灯片无人声（这种直接 OCR 更省事）。

## 常见故障

代理不通、没有字幕、模型下载失败、`av` 版本冲突、抽帧全黑、转写重复循环 —— 见 [`references/troubleshooting.md`](references/troubleshooting.md)。

## License

MIT
