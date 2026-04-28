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

# --- 這裡我更新了 HTML 的部分 ---
HTML = """
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<!-- 重要：這行是解決你圖片中縮小問題的關鍵 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Photo Translate</title>
<style>
/* 基礎修正：讓手機版顯示正確 */
body {
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    background-color: #fcfcfc;
}

h2 {
    font-size: 28px;
    margin-bottom: 20px;
    color: #1a1a1a;
    text-align: center;
}

form {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* 檔案選擇器美化 */
input[type="file"] {
    font-size: 16px;
    padding: 12px;
    border: 2px dashed #ccc;
    border-radius: 8px;
    background: #fff;
}

/* 上傳按鈕：大且好按 */
input[type="submit"] {
    font-size: 20px;
    padding: 16px;
    border-radius: 12px;
    border: none;
    background-color: #007AFF;
    color: white;
    width: 100%;
    font-weight: bold;
    cursor: pointer;
    -webkit-appearance: none; /* 移除 iOS 預設按鈕外觀 */
}

input[type="submit"]:active {
    background-color: #0056b3; /* 按下去的視覺反饋 */
}

/* 圖片顯示 */
img {
    max-width: 100%;
    height: auto;
    border-radius: 10px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}

/* 翻譯區塊 */
pre {
    font-size: 18px; /* 手機上 18px 閱讀最舒適 */
    line-height: 1.6;
    white-space: pre-wrap;
    background: #fff;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #eee;
    color: #333;
}

/* loading 字體放大 */
.loading {
    font-size: 22px;
    font-weight: bold;
    color: #007AFF;
    text-align: center;
    margin: 20px 0;
}

.container {
    display: flex;
    flex-direction: column;
    gap: 25px;
    margin-top: 20px;
}

h3 {
    margin-bottom: 10px;
    color: #555;
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
<h2>📸 照片翻譯器</h2>

<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file accept="image/*" required>
  <input type=submit id="submit-btn" value="開始上傳翻譯">
</form>

<p id="loading" class="loading" style="display:none;">
⏳ 正在分析圖片內容...
</p>

{% if image %}
<div class="container">
  <hr>
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
            # 儲存與處理圖片
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
                # GPT-4o 辨識與翻譯 (確保模型名稱正確，通常是 gpt-4o)
                response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "請擷取圖片中所有文字，並翻譯成繁體中文，保持原本段落格式。"},
                                {"type": "image_url", "image_url": {"url": image_data_url}}
                            ]
                        }
                    ]
                )
                result = response.choices[0].message.content

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG ERROR:", e)

    return render_template_string(HTML, result=result, image=image_data_url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
