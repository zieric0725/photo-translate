from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
import mimetypes
import io
from PIL import Image

# 支援 iPhone HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

app = Flask(__name__)
client = OpenAI()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 手機版優化介面 (包含 viewport 修正與大字體)
HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Photo Translate</title>
<style>
body {
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    background-color: #f8f9fa;
}

h2 {
    font-size: 32px;
    margin-bottom: 20px;
    text-align: center;
}

h3 {
    font-size: 24px;
}

form {
    display: flex;
    flex-direction: column;
    gap: 15px;
    margin-bottom: 28px;
}

input[type="file"] {
    font-size: 18px;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 8px;
    background: white;
}

input[type="submit"] {
    font-size: 24px;
    padding: 18px;
    border-radius: 12px;
    border: none;
    background-color: #007AFF;
    color: white;
    font-weight: bold;
    width: 100%;
    -webkit-appearance: none;
}

pre {
    font-size: 22px;
    line-height: 1.8;
    white-space: pre-wrap;
    background: #ffffff;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #eee;
    color: #1a1a1a;
}

.loading {
    font-size: 26px;
    font-weight: bold;
    color: #007AFF;
    text-align: center;
    margin-top: 15px;
}

img {
    max-width: 100%;
    border-radius: 10px;
}

.container {
    display: flex;
    flex-direction: column;
    gap: 25px;
}
</style>

<script>
function showLoading() {
    document.getElementById("loading").style.display = "block";
    document.getElementById("submit-btn").disabled = true;
    document.getElementById("submit-btn").value = "加速處理中...";
}
</script>
</head>

<body>
<h2>📸 快速照片翻譯</h2>

<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file accept="image/*" required>
  <input type=submit id="submit-btn" value="開始翻譯">
</form>

<p id="loading" class="loading" style="display:none;">
🚀 正在極速翻譯，請稍候...
</p>

{% if image %}
<hr>
<div class="container">
  <div>
    <h3>原圖：</h3>
    <img src="{{ image }}">
  </div>

  <div>
    <h3>翻譯結果：</h3>
    <pre>{{ result }}</pre>
  </div>
</div>
{% endif %}

</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    result = None
    image_data_url = None

    if request.method == "POST":
        file = request.files["file"]

        if file:
            try:
                # --- 加速處理 1: 縮小圖片尺寸與品質 ---
                img = Image.open(file)
                
                # 如果寬度超過 1200px 則縮放，減少 API 傳輸負擔
                if img.width > 1200:
                    new_height = int(img.height * (1200 / img.width))
                    img = img.resize((1200, new_height), Image.Resampling.LANCZOS)
                
                # 轉成 RGB 並轉為 JPEG Byte 流
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                image_data_url = f"data:image/jpeg;base64,{base64_image}"

                # --- 加速處理 2: 使用快速模型 gpt-4o-mini ---
                response = client.responses.create(
                    model="gpt-4o-mini", # 切換為 mini 模型，速度最快
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "自動偵測語言並翻譯成繁體中文，保持段落格式。"
                                },
                                {
                                    "type": "input_image",
                                    "image_url": image_data_url
                                }
                            ]
                        }
                    ]
                )

                result = response.output.content.text

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG ERROR:", e)

    return render_template_string(HTML, result=result, image=image_data_url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
