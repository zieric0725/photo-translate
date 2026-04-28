from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
import mimetypes

# 支援 iPhone HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

app = Flask(__name__)
client = OpenAI()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 這裡是針對手機版優化的 HTML/CSS，解決了縮小問題
HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<!-- 這行是解決手機縮小問題的關鍵 -->
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
    font-size: 32px; /* 標題文字加大 */
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

/* 檔案選擇器美化 */
input[type="file"] {
    font-size: 18px;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 8px;
    background: white;
}

/* 上傳按鈕：寬度 100% 方便拇指點擊 */
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

/* 翻譯內容字體加大 */
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
    document.getElementById("submit-btn").value = "翻譯處理中...";
}
</script>
</head>

<body>
<h2>📸 上傳照片翻譯</h2>

<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file accept="image/*" required>
  <input type=submit id="submit-btn" value="開始上傳">
</form>

<p id="loading" class="loading" style="display:none;">
⏳ 翻譯中，請稍候...
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
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            with open(filepath, "rb") as f:
                image_data = f.read()

            base64_image = base64.b64encode(image_data).decode("utf-8")

            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                mime_type = "image/jpeg"

            image_data_url = f"data:{mime_type};base64,{base64_image}"

            try:
                # 維持你原本的寫法與模型名稱
                response = client.responses.create(
                    model="gpt-4.1",
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": """
請執行以下任務：
1. 自動偵測圖片中的語言
2. 擷取所有文字內容（包含標題、條列）
3. 修正可能的辨識錯誤
4. 翻譯成繁體中文
5. 保持原本的段落與條列格式
"""
                                },
                                {
                                    "type": "input_image",
                                    "image_url": image_data_url
                                }
                            ]
                        }
                    ]
                )

                # 維持原本的結果取值方式
                result = response.output[0].content[0].text

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG ERROR:", e)

    return render_template_string(HTML, result=result, image=image_data_url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
