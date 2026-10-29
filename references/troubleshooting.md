# 故障排查

## 1. 网络：YouTube / B站 / 境外站点拉不到

现象：`curl` 返回 `502 Bad Gateway`、`000`，或 yt-dlp 报 `Unable to download webpage`。

原因：沙箱默认代理（`127.0.0.1:63193` 一类）对部分域名直接拒绝。

处理：

1. `fetch_video.py` 已经内置多代理轮询。如果全部失败，手工确认本机代理端口是否在监听：
   ```bash
   netstat -ano | grep LISTENING | grep -E ":(7890|7891|7897|10809|1080)\b"
   ```
2. 找到端口后直接指定：
   ```bash
   "$PY" -m yt_dlp --proxy "http://127.0.0.1:7890" --dump-json "<URL>" >/dev/null && echo OK
   ```
3. Windows 上 `curl` 报 `schannel ... 吊销` 时加 `--ssl-no-revoke`（Python/yt-dlp 不受影响）。

## 2. 完全没有字幕

现象：`yt-dlp --list-subs` 输出 `has no automatic captions` / `has no subtitles`。

很多中文频道既不挂 CC 也没有自动字幕。这不是配置问题，只能走 ASR。
用 `transcribe.py`，并把 `--prompt` 换成术语清单：

```bash
--prompt "以下是关于价格行为交易的中文教学：K线、实体、上影线、下影线、收盘价、趋势、回调、突破、反转、信号K线、入场K线"
```

## 3. 模型下载失败

| 报错 | 处理 |
|---|---|
| `401 Unauthorized ... cas-server.xethub.hf.co` | Xet 传输协议问题，设 `HF_HUB_DISABLE_XET=1` |
| 连接 `huggingface.co` 超时 | 设 `HF_ENDPOINT=https://hf-mirror.com` |
| 下载到一半卡住 | 删掉 `models/models--Systran--faster-whisper-<size>` 重来 |
| 模型已存在但仍联网 | 设 `HF_HUB_OFFLINE=1`（`transcribe.py` 会自动判断） |

## 4. av / faster-whisper 版本冲突

```
TypeError: open() got an unexpected keyword argument 'metadata_errors'
```

PyAV ≥14 删了该参数。降级：

```bash
"$PY" -m pip install "av==13.1.0"
```

## 5. 抽帧失败 / 全是黑屏

- `av.open` 报错：先确认 `video.mp4` 真的下载完成（看文件大小，几 MB 以上）。
- 全部黑屏：`--threshold` 设得太高，降到 3；或视频开头是纯色封面，脚本已强制保留首帧。
- 帧太少：把 `--gap` 调小（默认 25 秒），或 `--max` 提到 16。

## 6. 转写速度太慢

- 换成 `--model base`（质量下降约 15%，速度快 2 倍）。
- 确认 `cpu_threads` 用满：脚本默认 `os.cpu_count()`。
- 先切 10 分钟试跑，估算全片时间再决定是否换模型。

## 7. 转写出现重复循环

faster-whisper 的 `condition_on_previous_text` 已设为 `False` 来规避。
仍有问题时把 `--beam 1` 降低采样，或把音频按 15 分钟切片分别转写再拼接。

## 8. build_quiz.py 报 invalid questions

按报错逐条修：

- `answer index out of range`：下标写成了 1 起始，改回 0 起始。
- `multi needs >=2 answers`：多选只给了一个答案，要么补答案，要么改成 single。
- `missing ts`：缺时间戳。时间戳是这套题的核心，必须补。
