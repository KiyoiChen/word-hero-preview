# AI Cat News Prototype

「毒舌懶貓 AI 新知」短影片 MVP。

## 目標
用一張固定的懶貓主視覺，自動組成 9:16 短影片：
- 固定標題區
- 主視覺
- 逐句字幕
- TTS 旁白
- 輸出 MP4

目前先驗證內容與版型，不做嘴型同步，也不做複雜動畫。

## 本機需求
- ffmpeg
- 一張主視覺：`assets/cat.jpg`
- 一段旁白：`voice.wav`

## 產生影片
在 ai-cat-news 目錄執行：

```bash
./render.sh
```

輸出：`output/prototype_001.mp4`

## #001 測試腳本
主題：Gemini Skills 到底能幹嘛？

語氣：
> 愚蠢的人類……AI 都快把你們淘汰了，你還在每次重打同一串指令？

後續可接：
AI 新聞來源 → 應用化改寫 → 貓式腳本 → ElevenLabs → render.sh → MP4
