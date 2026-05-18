from flask import Flask, request, render_template_string, Response
import json
from openai import OpenAI
from PIL import Image
import io
import os
import base64
import mimetypes

from pillow_heif import register_heif_opener
register_heif_opener()

MAX_SIZE = 1600       # 最長邊縮到 1600px
JPEG_QUALITY = 85     # JPEG 壓縮品質（85% 清晰度夠用，檔案小很多）

def compress_image(filepath: str) -> tuple[bytes, str]:
    """把圖片壓縮後回傳 (bytes, mime_type)"""
    with Image.open(filepath) as img:
        # 轉成 RGB（HEIC / PNG with alpha 需要這步）
        if img.mode in ("RGBA", "P", "CMYK"):
            img = img.convert("RGB")

        # 等比例縮小（只縮不放大）
        img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue(), "image/jpeg"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

<form method="post" enctype="multipart/form-data" onsubmit="handleSubmit(event)" id="mainForm">
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
    <div class="loading-text">AI 正在分析圖片，請稍候…</div>
  </div>
</div>

{% if results %}
<div class="result-section">
  {% for item in results %}
  <div class="card">
    <div class="card-label">第 {{ loop.index }} 張 — 原始圖片</div>
    {% if item.size_info %}
    <div style="font-size:12px; color:#7D5C42; background:#F5EDE6; border:1px solid #DEC4B0; border-radius:8px; padding:6px 12px; margin-bottom:12px; display:inline-block;">
      ⚡ 已壓縮：{{ item.size_info }}
    </div>
    {% endif %}
    <img class="original-img" src="{{ item.image }}" alt="圖片 {{ loop.index }}">
  </div>
  <div class="card">
    <div class="card-label">第 {{ loop.index }} 張 — 翻譯結果</div>
    {% if item.result and item.result.startswith('發生錯誤') %}
      <div class="error-box">{{ item.result }}</div>
    {% else %}
      <div class="result-text" id="resultText{{ loop.index }}">{{ item.result }}</div>
      <button class="copy-btn" onclick="copyResult('resultText{{ loop.index }}')">
        <span>📋</span> 複製文字
      </button>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}

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

<script>
// ── 翻譯紀錄（存在 sessionStorage，關閉分頁即清除）──

const HISTORY_KEY = 'translate_history';

function getHistory() {
  try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY)) || []; }
  catch { return []; }
}

function saveHistory(list) {
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}

function formatTime(ts) {
  const d = new Date(ts);
  const h = String(d.getHours()).padStart(2,'0');
  const m = String(d.getMinutes()).padStart(2,'0');
  return `今天 ${h}:${m}`;
}

function renderHistory() {
  const list = getHistory();
  const container = document.getElementById('historyList');
  const empty = document.getElementById('historyEmpty');

  // 清除舊項目（保留 empty）
  Array.from(container.querySelectorAll('.history-item')).forEach(el => el.remove());

  if (list.length === 0) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  list.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'history-item';
    div.innerHTML = `
      <div class="history-item-header" onclick="toggleItem(${idx})">
        <img class="history-thumb" src="${item.image}" alt="縮圖">
        <div class="history-meta">
          <div class="history-time">${formatTime(item.ts)}</div>
          <div class="history-preview">${item.text.slice(0, 40)}…</div>
        </div>
        <span class="history-chevron" id="chev-${idx}">▼</span>
      </div>
      <div class="history-body" id="body-${idx}">
        <img class="history-full-img" src="${item.image}" alt="原圖">
        <div class="history-full-text">${item.text}</div>
        <button class="history-copy-btn" onclick="copyHistory(${idx})">📋 複製</button>
      </div>
    `;
    container.appendChild(div);
  });
}

function toggleItem(idx) {
  const body = document.getElementById(`body-${idx}`);
  const chev = document.getElementById(`chev-${idx}`);
  body.classList.toggle('open');
  chev.classList.toggle('open');
}

function copyHistory(idx) {
  const list = getHistory();
  navigator.clipboard.writeText(list[idx].text);
}

function clearHistory() {
  if (confirm('確定要清除所有紀錄嗎？')) {
    sessionStorage.removeItem(HISTORY_KEY);
    renderHistory();
  }
}

// 頁面載入時，若有新翻譯結果就存進紀錄
window.addEventListener('DOMContentLoaded', () => {
  const resultEls = document.querySelectorAll('[id^="resultText"]');
  const imgEls = document.querySelectorAll('.original-img');

  if (resultEls.length > 0) {
    const list = getHistory();
    resultEls.forEach((el, i) => {
      list.unshift({
        text: el.innerText,
        image: imgEls[i] ? imgEls[i].src : '',
        ts: Date.now() + i
      });
    });
    while (list.length > 20) list.pop();
    saveHistory(list);
  }

  renderHistory();
});

function handleFileChange(input) {
  const zone = document.getElementById('uploadZone');
  const nameEl = document.getElementById('fileName');
  if (input.files && input.files.length > 0) {
    zone.classList.add('has-file');
    const count = input.files.length;
    nameEl.textContent = count === 1
      ? `✓ ${input.files[0].name}`
      : `✓ 已選擇 ${count} 張圖片`;
    nameEl.style.display = 'block';
  }
}

function handleSubmit(e) {
  const fileInput = document.getElementById('fileInput');
  if (!fileInput.files || !fileInput.files[0]) return;
  const btn = document.getElementById('submitBtn');
  const loading = document.getElementById('loadingCard');
  btn.disabled = true;
  btn.textContent = '翻譯中…';
  loading.style.display = 'block';
}

function copyResult(id) {
  const text = document.getElementById(id).innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btns = document.querySelectorAll('.copy-btn');
    btns.forEach(btn => {
      if (btn.getAttribute('onclick') === `copyResult('${id}')`) {
        btn.classList.add('copied');
        btn.innerHTML = '<span>✓</span> 已複製';
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = '<span>📋</span> 複製文字';
        }, 2000);
      }
    });
  });
}
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
</script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    results = []

    if request.method == "POST":
        files = request.files.getlist("files")

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

            try:
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
                                    "image_url": {"url": image_data_url}
                                },
                                {
                                    "type": "text",
                                    "text": "請立即執行以下任務，不可詢問任何問題，直接輸出翻譯結果：\n1. 自動偵測圖片中的語言\n2. 【最重要】逐字擷取圖片中所有文字，絕對不可省略任何項目，包含標題、每一道菜名、價格、小字、備註\n3. 每個項目格式：「原文 → 繁體中文」寫在同一行，價格數字保留，例如：「さしみ 500円 → 生魚片 500円」\n4. 依照原始菜單分區分組，每組之間空一行，並標示區塊標題\n5. 無法辨識的文字標註[?]\n6. 最後加上「---完整翻譯結束---」"
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

    return render_template_string(HTML, results=results)


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
