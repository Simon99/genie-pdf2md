# genie-pdf2md

PDF → 圖檔 + Markdown/HTML:PyMuPDF 逐頁轉圖,vision LLM 解析每頁內容(含流程圖、表格)。

## 需求

- genie-core(`[pdf]` extra)
- LM Studio 跑一顆 vision 模型(qwen3-vl 系或 qwen3.6-35b 這類 text+vision 模型)

## 用法

```bash
genie-pdf2md slides.pdf                          # 輸出 slides_output/
genie-pdf2md slides.pdf -o outdir --dpi 200      # model 不指定 → 自動挑 vision 模型
genie-pdf2md slides.pdf --model "qwen/qwen3-vl-30b"
```

| 參數 | 預設 | 說明 |
|---|---|---|
| `input` | — | PDF 檔 |
| `-o, --output` | `<input>_output/` | 輸出目錄 |
| `--model` | 自動挑選 | vision 模型(讀 LM Studio 能力標記) |
| `--url` | `http://localhost:1234/v1` | LM Studio API |
| `--dpi` | 200 | 頁面轉圖解析度 |

## 輸出

```
outdir/
  pages/page_001.png / page_001.md   # 逐頁圖檔 + 逐頁解析(checkpoint)
  output.md                          # 合併 Markdown
  output.html                        # 頁圖與文字並排的 HTML
```

## 斷點續跑(resume)

每頁解析完立即落盤 `pages/page_NNN.md`。中途斷線(LM Studio 掛掉、Ctrl-C)後**重跑同一指令**:已成功的頁直接跳過,只補失敗頁。單頁失敗會留 placeholder 並繼續,結尾列出失敗頁清單。

## 已知坑

- 100 頁 PDF × vision 呼叫很花時間,先用小檔驗證 prompt 效果再上大檔
- 表格密集頁若解析不佳,可提高 `--dpi` 到 300
