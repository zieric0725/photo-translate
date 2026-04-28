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
client = OpenAI() # 確保你的環境變數中已設定 OPENAI_API_KEY

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 手機優化界面
HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Photo Translate</title>
<style>
body { padding: 20px; font-family: -apple-system, sans-serif; margin: 0; background-color: #f8f9fa; color: #333; }
h2 { font-size: 32px; margin-bottom: 20px; text-align: center; }
form { display: flex; flex-direction: column; gap: 15px; margin-bottom: 28px; }
input[type="file"] { font-size: 18px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; background: white; }
input[type="submit"] { font-size: 24px; padding: 18px; border-radius: 12px; border: none; background-color: #007AFF; color: white; font-weight: bold; width: 100%; -webkit-appearance: none; }
pre { font-size: 20px; line-height: 1.7; white-space: pre-wrap; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; }
.loading { font-size: 24px; font-weight: bold; color: #007AFF; text-align: center; margin-top: 15px; }
img { max-width: 100%; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
.container { display: flex; flex-direction: column; gap: 25px; margin-top: 20px; }
</style>
<script>
function showLoading() {
    document.getElementById("loading").style.display = "block";
    document.getElementById("submit-btn").disabled = true;
    document.getElementById("submit-btn").value = "正在翻譯中...";
}
</script>
</head>
<body>
<h2>📸 穩定版翻譯器</h2>
<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file accept="image/*" required>
  <input type=submit id="submit-btn" value="開始上傳翻譯">
</form>
<p id="loading" class="loading" style="display:none;">⏳ AI 正在全力辨識中...</p>
{% if image %}
<hr>
<div class="container">
  <div><h3>原圖：</h3><img src="{{ image }}"></div>
  <div><h3>翻譯結果：</h3><pre>{{ result }}</pre></div>
</div>
{% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    result = ""
    image_data_url = None

    if request.method == "POST":
        file = request.files["file"]
        if file:
            try:
                # 1. 圖片縮修：提升至 1600px 確保清晰，但減少檔案大小
                img = Image.open(file)
                if img.width > 1600:
                    new_height = int(img.height * (1600 / img.width))
                    img = img.resize((1600, new_height), Image.Resampling.LANCZOS)
                
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=88)
                base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                image_data_url = f"data:image/jpeg;base64,{base64_image}"

                # 2. 改用最穩定的 Chat Completions 介面
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "請逐字辨識圖片中的所有文字，並翻譯成繁體中文。請保持原本的段落格式，不要遺漏任何內容。"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_data_url,
                                        "detail": "high" # 強制高清晰度辨識
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=2000
                )

                # 3. 穩定的取值方式
                result = response.choices[0].message.content

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG:", e)

    return render_template_string(HTML, result=result, image=image_data_url)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
