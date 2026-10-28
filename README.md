# PDFDon Telugu Shorts Bot

Makes a Telugu YouTube Short about one pdfdon.com tool every Monday, Wednesday and Friday
on GitHub Actions:

topic (`topics.yaml`) → Claude script → Edge Telugu voice → Playwright screenshots of the tool →
HTML frames + ffmpeg → `short.mp4` → YouTube upload as **private** (when YouTube secrets are set).

Setup steps (Telugu): [SETUP-TELUGU.md](SETUP-TELUGU.md)

| Secret | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | Claude-written scripts (without it, the fixed steps in `topics.yaml` are used) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | Upload to YouTube (without them, the video stays as the `short` artifact) |

Manual run: **Actions → PDFDon Shorts → Run workflow**. "Test only" makes the video without
uploading or recording the topic.
