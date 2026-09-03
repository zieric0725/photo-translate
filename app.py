from flask import Flask, request, render_template_string, Response, jsonify, send_from_directory
import json
from openai import OpenAI
from PIL import Image, ImageEnhance, ImageFilter
import io
import os
import base64
import mimetypes
import threading
import uuid
import requests

from pillow_heif import register_heif_opener
register_heif_opener()

MAX_SIZE = 1600
JPEG_QUALITY = 85

def compress_image(filepath: str) -> tuple[bytes, str]:
    """壓縮圖片"""
    with Image.open(filepath) as img:
        if img.mode in ("RGBA", "P", "CMYK"):
            img = img.convert("RGB")
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue(), "image/jpeg"


def enhance_image(image_bytes: bytes) -> bytes:
    """方案二：圖片前處理，提升文字辨識效果"""
    with Image.open(io.BytesIO(image_bytes)) as img:
        if img.mode in ("RGBA", "P", "CMYK"):
            img = img.convert("RGB")

        # 1. 提高對比度（讓文字更清晰）
        img = ImageEnhance.Contrast(img).enhance(1.4)

        # 2. 提高銳利度（讓模糊的字變清晰）
        img = ImageEnhance.Sharpness(img).enhance(2.0)

        # 3. 輕微銳化濾鏡
        img = img.filter(ImageFilter.SHARPEN)

        # 4. 稍微提高亮度（改善光線不均）
        img = ImageEnhance.Brightness(img).enhance(1.1)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()


def google_vision_ocr(image_bytes: bytes) -> str:
    """方案三：用 Google Cloud Vision 辨識圖片文字"""
    # Debug：印出所有環境變數名稱
    env_keys = [k for k in os.environ.keys()]
    print(f"所有環境變數：{env_keys}")

    api_key_str = os.environ.get("GOOGLE_VISION_CREDENTIALS", "")
    print(f"GOOGLE_VISION_CREDENTIALS 長度：{len(api_key_str)}")

    if not api_key_str:
        print("Google Vision: 找不到 GOOGLE_VISION_CREDENTIALS 環境變數")
        return None

    try:
        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import service_account

        creds_dict = json.loads(api_key_str)
        print(f"Google Vision: 憑證載入成功，project_id={creds_dict.get('project_id')}")

        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        print("Google Vision: Token 取得成功")

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "requests": [{
                "image": {"content": b64_image},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
            }]
        }
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            "https://vision.googleapis.com/v1/images:annotate",
            json=payload,
            headers=headers,
            timeout=30
        )
        print(f"Google Vision: API 回應狀態碼 {resp.status_code}")
        data = resp.json()

        if "error" in data:
            print(f"Google Vision API 錯誤: {data['error']}")
            return None

        if not data.get("responses"):
            print("Google Vision: responses 為空")
            return None

        text = data["responses"][0].get("fullTextAnnotation", {}).get("text", "")
        print(f"Google Vision: 辨識文字長度 {len(text)}")
        return text if text else None

    except Exception as e:
        print(f"Google Vision 例外錯誤: {type(e).__name__}: {e}")
        return None

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 任務儲存（記憶體）
tasks = {}

HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>照片翻譯器</title>
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="照片翻譯器">
<meta name="theme-color" content="#A0785A">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' rx='18' fill='%23A0785A'/><rect x='14' y='14' width='38' height='38' rx='8' fill='%23F5EDE6'/><rect x='14' y='14' width='38' height='38' rx='8' fill='none' stroke='%23DEC4B0' stroke-width='1.5'/><circle cx='24' cy='24' r='4' fill='%23DEC4B0'/><path d='M14 42 L24 32 L32 38 L42 28 L52 36' fill='none' stroke='%23A0785A' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/><rect x='40' y='42' width='26' height='12' rx='6' fill='%237D5C42'/><line x1='44' y1='48' x2='62' y2='48' stroke='%23F5EDE6' stroke-width='2' stroke-linecap='round'/><rect x='40' y='58' width='26' height='12' rx='6' fill='%23DEC4B0'/><line x1='44' y1='64' x2='62' y2='64' stroke='%237D5C42' stroke-width='2' stroke-linecap='round'/></svg>">
<link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' rx='18' fill='%23A0785A'/><rect x='14' y='14' width='38' height='38' rx='8' fill='%23F5EDE6'/><rect x='14' y='14' width='38' height='38' rx='8' fill='none' stroke='%23DEC4B0' stroke-width='1.5'/><circle cx='24' cy='24' r='4' fill='%23DEC4B0'/><path d='M14 42 L24 32 L32 38 L42 28 L52 36' fill='none' stroke='%23A0785A' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/><rect x='40' y='42' width='26' height='12' rx='6' fill='%237D5C42'/><line x1='44' y1='48' x2='62' y2='48' stroke='%23F5EDE6' stroke-width='2' stroke-linecap='round'/><rect x='40' y='58' width='26' height='12' rx='6' fill='%23DEC4B0'/><line x1='44' y1='64' x2='62' y2='64' stroke='%237D5C42' stroke-width='2' stroke-linecap='round'/></svg>">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --primary: #A0785A;
    --primary-dark: #7D5C42;
    --primary-light: #F5EDE6;
    --primary-border: #DEC4B0;
    --bg: #FAF6F2;
    --card: #FFFFFF;
    --text: #3B2A1E;
    --muted: #9C7E6E;
    --border: #EAD9CE;
    --radius: 20px;
  }

  body {
    font-family: 'Noto Sans TC', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 0 0 48px;
  }

  /* ── Header ── */
  .header {
    background: linear-gradient(135deg, #A0785A 0%, #C49A7A 100%);
    padding: 24px 20px 32px;
    text-align: center;
    border-radius: 0 0 32px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(160,120,90,0.25);
  }
  .header-icon {
    font-size: 44px;
    display: block;
    margin-bottom: 8px;
  }
  .header h1 {
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.5px;
  }
  .header p {
    font-size: 13px;
    color: rgba(255,255,255,0.8);
    margin-top: 5px;
  }

  /* ── Card ── */
  .card {
    background: var(--card);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    margin: 0 16px 20px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(160,120,90,0.08);
  }
  .card-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }

  /* ── Upload area ── */
  .upload-zone {
    border: 2px dashed var(--primary-border);
    border-radius: 16px;
    padding: 28px 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    position: relative;
    background: var(--primary-light);
  }
  .upload-zone:hover, .upload-zone.has-file {
    border-color: var(--primary);
    background: #EFE0D4;
  }
  .upload-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }
  .upload-icon { font-size: 36px; display: block; margin-bottom: 8px; }
  .upload-text {
    font-size: 15px;
    font-weight: 500;
    color: var(--text);
  }
  .upload-hint {
    font-size: 12px;
    color: var(--muted);
    margin-top: 4px;
  }
  .upload-filename {
    font-size: 13px;
    color: var(--primary);
    font-weight: 500;
    margin-top: 8px;
    display: none;
  }

  /* ── Submit button ── */
  .btn {
    display: block;
    width: calc(100% - 32px);
    margin: 0 16px 0;
    padding: 16px;
    background: linear-gradient(135deg, #A0785A 0%, #C49A7A 100%);
    color: #fff;
    font-size: 16px;
    font-weight: 700;
    font-family: inherit;
    border: none;
    border-radius: 20px;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
    letter-spacing: 0.3px;
    box-shadow: 0 4px 12px rgba(160,120,90,0.35);
  }
  .btn:active { transform: scale(0.98); }
  .btn:hover { opacity: 0.9; }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  /* ── Loading ── */
  .loading-card {
    margin: 20px 16px 0;
    display: none;
  }
  .loading-inner {
    background: var(--primary-light);
    border: 1px solid var(--primary-border);
    border-radius: var(--radius);
    padding: 20px;
    text-align: center;
  }
  .spinner {
    width: 36px; height: 36px;
    border: 3px solid var(--primary-border);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 12px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-text {
    font-size: 14px;
    font-weight: 500;
    color: var(--primary);
  }
  .loading-stages {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 14px;
    text-align: left;
  }
  .stage {
    font-size: 13px;
    color: var(--muted);
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    transition: all 0.3s;
  }
  .stage.active {
    color: var(--primary);
    background: var(--primary-light);
    border-color: var(--primary-border);
    font-weight: 600;
  }
  .stage.done {
    color: #16A34A;
    background: #F0FDF4;
    border-color: #86EFAC;
  }
  .cancel-btn {
    margin-top: 14px;
    padding: 8px 18px;
    background: none;
    border: 1px solid #FECACA;
    border-radius: 10px;
    color: #B91C1C;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
  }
  .cancel-btn:hover { background: #FEF2F2; }
  .error-retry-box {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    border-radius: 12px;
    padding: 16px;
    margin: 0 16px 20px;
  }
  .error-retry-box p {
    color: #B91C1C;
    font-size: 14px;
    margin-bottom: 12px;
  }
  .retry-btn {
    padding: 9px 20px;
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-family: inherit;
    font-weight: 600;
    cursor: pointer;
  }

  /* ── Result section ── */
  .result-section { margin-top: 28px; }
  .original-img {
    width: 100%;
    border-radius: 12px;
    display: block;
    border: 1px solid var(--border);
  }
  .result-text {
    font-size: 16px;
    line-height: 1.9;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
  }
  .result-text-bilingual {
    font-size: 15px;
    line-height: 1.8;
    word-break: break-word;
  }
  .bilingual-block {
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }
  .bilingual-block:last-child {
    border-bottom: none;
    margin-bottom: 0;
  }
  .bilingual-original {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.6;
    margin-bottom: 3px;
  }
  .bilingual-translation {
    color: var(--text);
    font-size: 16px;
    font-weight: 500;
    line-height: 1.7;
  }
  .bilingual-end {
    font-size: 12px;
    color: #16A34A;
    margin-top: 12px;
    text-align: center;
  }

  /* ── Copy button ── */
  .copy-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 14px;
    padding: 8px 16px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    color: var(--muted);
    cursor: pointer;
    transition: background 0.15s;
  }
  .copy-btn:hover { background: var(--border); }
  .copy-btn.copied { color: #16A34A; border-color: #86EFAC; background: #F0FDF4; }

  /* ── Error ── */
  .error-box {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    border-radius: 12px;
    padding: 16px;
    color: #B91C1C;
    font-size: 14px;
    line-height: 1.6;
  }

  /* ── History ── */
  .history-section { margin-top: 32px; }
  .history-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 0 16px 12px;
  }
  .history-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
  }
  .clear-btn {
    font-size: 12px;
    color: #EF4444;
    background: none;
    border: 1px solid #FECACA;
    border-radius: 8px;
    padding: 4px 10px;
    font-family: inherit;
    cursor: pointer;
  }
  .history-empty {
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    padding: 20px;
  }
  .history-item {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin: 0 16px 12px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }
  .history-item-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    cursor: pointer;
    user-select: none;
  }
  .history-thumb {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
    border: 1px solid var(--border);
  }
  .history-meta {
    flex: 1;
    min-width: 0;
  }
  .history-time {
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 2px;
  }
  .history-preview {
    font-size: 13px;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .history-chevron {
    font-size: 12px;
    color: var(--muted);
    transition: transform 0.2s;
  }
  .history-chevron.open { transform: rotate(180deg); }
  .history-body {
    display: none;
    border-top: 1px solid var(--border);
    padding: 14px;
  }
  .history-body.open { display: block; }
  .history-full-img {
    width: 100%;
    border-radius: 8px;
    margin-bottom: 12px;
    border: 1px solid var(--border);
  }
  .history-full-text {
    font-size: 14px;
    line-height: 1.8;
    white-space: pre-wrap;
    color: var(--text);
  }
  .history-copy-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-top: 10px;
    padding: 6px 12px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 12px;
    font-family: inherit;
    color: var(--muted);
    cursor: pointer;
  }
</style>
</head>

<body>

<div class="header">
  <span class="header-icon">📸</span>
  <h1>照片翻譯器</h1>
  <p>上傳圖片，自動偵測語言並翻譯成繁體中文</p>
</div>

<form id="mainForm" onsubmit="handleSubmit(event)">
  <div class="card">
    <div class="card-label">選擇圖片</div>
    <div class="upload-zone" id="uploadZone">
      <input type="file" name="files" accept="image/*" required id="fileInput" multiple onchange="handleFileChange(this)">
      <span class="upload-icon">🖼️</span>
      <div class="upload-text">點擊選擇或拍照上傳</div>
      <div class="upload-hint">支援 JPG、PNG、HEIC，可一次選多張</div>
      <div class="upload-filename" id="fileName"></div>
    </div>
  </div>

  <button type="submit" class="btn" id="submitBtn">開始翻譯</button>
</form>

<div class="loading-card" id="loadingCard">
  <div class="loading-inner">
    <div class="spinner"></div>
    <div class="loading-text" id="loadingText">上傳中…</div>
    <div class="loading-stages" id="loadingStages">
      <div class="stage" id="stage1">📤 上傳中</div>
      <div class="stage" id="stage2">🔍 辨識文字</div>
      <div class="stage" id="stage3">🌐 翻譯中</div>
      <div class="stage" id="stage4">✨ 整理結果</div>
    </div>
    <button class="cancel-btn" id="cancelBtn" onclick="cancelTranslation()">取消本次翻譯</button>
  </div>
</div>

<!-- 翻譯結果（由 JS 動態填入）-->
<div id="resultSection"></div>

<!-- 翻譯紀錄 -->
<div class="history-section">
  <div class="history-header">
    <span class="history-title">📋 翻譯紀錄</span>
    <button class="clear-btn" onclick="clearHistory()">全部清除</button>
  </div>
  <div id="historyList">
    <div class="history-empty" id="historyEmpty">還沒有翻譯紀錄</div>
  </div>
</div>

<script src="/static/app.js"></script>
</body>
</html>
"""

def translate_images(task_id, files_data):
    """背景執行翻譯，結果存到 tasks dict"""
    results = []
    for item in files_data:
        image_data_url = item["image_data_url"]
        image_bytes = item["image_bytes"]
        size_info = item["size_info"]
        try:
            # 方案二：圖片前處理（提升辨識率）
            enhanced_bytes = enhance_image(image_bytes)

            # 方案三：先用 Google Vision OCR 辨識文字
            ocr_text = google_vision_ocr(enhanced_bytes)

            if ocr_text:
                # OCR 成功 → 只用 GPT 翻譯文字（不需要看圖）
                print(f"Google Vision OCR 成功，文字長度：{len(ocr_text)}")
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一位專業翻譯員。請將以下文字翻譯成繁體中文，不可省略任何內容，直接輸出結果。"
                        },
                        {
                            "role": "user",
                            "content": f"""以下是從圖片辨識出的文字，請依照原始分區分組，用上下對照格式輸出：

格式規則：
- 每個區塊先顯示原文，下一行顯示繁體中文翻譯
- 原文和翻譯之間不加任何符號，直接換行
- 每個區塊之間空一行
- 價格數字保留
- 無法判斷的文字標註[?]
- 最後加上「---完整翻譯結束---」

範例格式：
さしみ 500円
生魚片 500円

トッピング
配料
キムチ
泡菜

辨識文字：
{ocr_text}"""
                        }
                    ],
                    max_tokens=4000
                )
            else:
                # OCR 失敗 → 退回用 GPT 直接看圖翻譯
                print("Google Vision OCR 無結果，改用 GPT 視覺翻譯")
                enhanced_b64 = base64.b64encode(enhanced_bytes).decode("utf-8")
                enhanced_data_url = f"data:image/jpeg;base64,{enhanced_b64}"
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一位專業翻譯員。使用者會傳來圖片，你必須立即執行翻譯，不可詢問使用者任何問題，不可要求確認，直接輸出結果。"
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": enhanced_data_url}
                                },
                                {
                                    "type": "text",
                                    "text": "請立即執行以下任務，不可詢問任何問題，直接輸出翻譯結果：\n1. 自動偵測圖片中的語言\n2. 【最重要】逐字擷取圖片中所有文字，絕對不可省略任何項目\n3. 用上下對照格式輸出：原文在上，繁體中文翻譯在下，直接換行不加符號\n4. 每個區塊之間空一行，價格數字保留\n範例：\nさしみ 500円\n生魚片 500円\n\nトッピング\n配料\n5. 無法辨識的文字標註[?]\n6. 最後加上「---完整翻譯結束---」"
                                }
                            ]
                        }
                    ],
                    max_tokens=4000
                )

            raw = response.choices[0].message.content
            result = raw if raw else "翻譯結果為空，請重試。"

        except Exception as e:
            result = f"發生錯誤：{str(e)}"
            print("ERROR:", e)

        results.append({
            "image": image_data_url,
            "result": result,
            "size_info": size_info
        })

    tasks[task_id] = {"status": "done", "results": results}

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload_file():
    files = request.files.getlist("files")
    files_data = []

    for file in files:
        if not file or not file.filename:
            continue

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        original_size = os.path.getsize(filepath)
        image_data, mime_type = compress_image(filepath)
        compressed_size = len(image_data)
        size_info = f"{original_size/1024/1024:.1f}MB → {compressed_size/1024:.0f}KB"

        base64_image = base64.b64encode(image_data).decode("utf-8")
        image_data_url = f"data:{mime_type};base64,{base64_image}"

        files_data.append({
            "image_data_url": image_data_url,
            "image_bytes": image_data,
            "size_info": size_info
        })

    # 建立任務 ID，背景執行翻譯
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "processing", "results": []}
    thread = threading.Thread(target=translate_images, args=(task_id, files_data))
    thread.daemon = True
    thread.start()

    return jsonify({"task_id": task_id, "count": len(files_data)})


@app.route("/status/<task_id>")
def check_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"status": "not_found"})
    return jsonify(task)


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/manifest.json")
def manifest():
    data = {
        "name": "照片翻譯器",
        "short_name": "翻譯器",
        "description": "上傳圖片自動翻譯成繁體中文",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#FAF6F2",
        "theme_color": "#A0785A",
        "orientation": "portrait",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'><rect width='80' height='80' rx='18' fill='%23A0785A'/><rect x='14' y='14' width='38' height='38' rx='8' fill='%23F5EDE6'/><rect x='14' y='14' width='38' height='38' rx='8' fill='none' stroke='%23DEC4B0' stroke-width='1.5'/><circle cx='24' cy='24' r='4' fill='%23DEC4B0'/><path d='M14 42 L24 32 L32 38 L42 28 L52 36' fill='none' stroke='%23A0785A' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/><rect x='40' y='42' width='26' height='12' rx='6' fill='%237D5C42'/><line x1='44' y1='48' x2='62' y2='48' stroke='%23F5EDE6' stroke-width='2' stroke-linecap='round'/><rect x='40' y='58' width='26' height='12' rx='6' fill='%23DEC4B0'/><line x1='44' y1='64' x2='62' y2='64' stroke='%237D5C42' stroke-width='2' stroke-linecap='round'/></svg>",
                "sizes": "any",
                "type": "image/svg+xml"
            }
        ]
    }
    return Response(json.dumps(data), mimetype="application/json")


@app.route("/sw.js")
def service_worker():
    sw = """
const CACHE = 'photo-translate-v1';
const ASSETS = ['/'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
"""
    return Response(sw, mimetype="application/javascript")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
