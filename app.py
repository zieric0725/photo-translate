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

# 手機版優化介面 (保持之前的大字體與 Viewport 設定)
HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Photo Translate</title>
<style>
body { padding: 20px; font-family: -apple-system, sans-serif; margin: 0; background-color: #f8f9fa; }
h2 { font-size: 32px; margin-bottom: 20px; text-align: center; }
form { display: flex; flex-direction: column; gap: 15px; margin-bottom: 28px; }
input[type="file"] { font-size: 18px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; background: white; }
input[type="submit"] { font-size: 24px; padding: 18px; border-radius: 12px; border: none; background-color: #007AFF; color: white; font-weight: bold; width: 100%; -webkit-appearance: none; }
pre { font-size: 22px; line-height: 1.8; white-space: pre-wrap; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; color: #1a1a1a; }
.loading { font-size: 26px; font-weight: bold; color: #007AFF; text-align: center; margin-top: 15px; }
img { max-width: 100%; border-radius: 10px; }
.container { display: flex; flex-direction: column; gap: 25px; }
</style>
<script>
function showLoading() {
    document.getElementById("loading").style.display = "block";
    document.getElementById("submit-btn").disabled = true;
    document.getElementById("submit-btn").value = "翻譯分析中...";
}
</script>
</head>
<body>
<h2>📸 精確照片翻譯</h2>
<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file accept="image/*" required>
  <input type=submit id="submit-btn" value="開始翻譯">
</form>
<p id="loading" class="loading" style="display:none;">⏳ 正在深度辨識內容...</p>
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
                # 1. 圖片處理：維持高品質以利精確翻譯
                img = Image.open(file)
                if img.width > 1600:
                    new_height = int(img.height * (1600 / img.width))
                    img = img.resize((1600, new_height), Image.Resampling.LANCZOS)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=90)
                base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
                image_data_url = f"data:image/jpeg;base64,{base64_image}"

                # 2. 使用 Responses API
                response = client.responses.create(
                    model="gpt-4o",
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "請逐字辨識圖片中所有文字，完整翻譯成繁體中文，絕對不要遺漏任何內容，並保持原本格式。"},
                            {"type": "input_image", "image_url": image_data_url}
                        ]
                    }]
                )

                # 🔥 修正後的穩定解析邏輯 🔥
                # 遍歷所有的 output 區塊，抓取所有文字內容
                full_text_list = []
                for item in response.output:
                    if hasattr(item, 'content'):
                        # content 也是清單，抓取裡面所有的 text 物件
                        for c in item.content:
                            if hasattr(c, 'text'):
                                full_text_list.append(c.text)
                
                result = "\n".join(full_text_list)
                if not result:
                    result = "API 回傳成功，但未從圖片中提取出文字。"

            except Exception as e:
                result = f"系統錯誤：{str(e)}"
                print("DEBUG:", e)

    return render_template_string(HTML, result=result, image=image_data_url)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
