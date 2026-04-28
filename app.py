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

HTML = """
<!doctype html>
<html>
<head>
<title>Photo Translate</title>
<style>
/* 基礎修正：讓手機版顯示正確 */
body {
    padding: 20px;         /* 讓內容不要貼死螢幕邊邊 */
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
}

h2 {
    font-size: 28px;       /* 稍微調小一點，避免太長 */
    margin-bottom: 20px;
    color: #333;
}

form {
    display: flex;         /* 使用 Flexbox 讓元件排列更靈活 */
    flex-direction: column; /* 改為垂直排列，適合手機單手操作 */
    gap: 15px;             /* 元件之間的間距 */
}

input[type="file"] {
    font-size: 16px;       /* 檔案選擇器不需要太大 */
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 8px;
}

input[type="submit"] {
    font-size: 20px;
    padding: 15px;         /* 增加高度，大拇指才好按 */
    border-radius: 10px;
    border: none;
    background-color: #007AFF;
    color: white;
    width: 100%;           /* 讓按鈕變寬，像 App 的感覺 */
    font-weight: bold;
}


/* 圖片 */
img {
    max-width: 100%;
    border-radius: 10px;
}

/* 翻譯區塊 */
pre {
    font-size: 20px;        /* 🔥 重點：翻譯字變大 */
    line-height: 1.8;
    white-space: pre-wrap;
    background: #f5f5f5;
    padding: 15px;
    border-radius: 10px;
}

/* 手機排版（重點） */
.container {
    display: flex;
    flex-direction: column;   /* 🔥 垂直排列 */
    gap: 20px;
}
</style>

<script>
function showLoading() {
    document.getElementById("loading").style.display = "block";
}
</script>
</head>

<body>
<h2>上傳照片翻譯</h2>

<form method=post enctype=multipart/form-data onsubmit="showLoading()">
  <input type=file name=file required>
  <input type=submit value=上傳>
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

            # 👉 給前端顯示用
            image_data_url = f"data:{mime_type};base64,{base64_image}"

            try:
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

                result = response.output[0].content[0].text

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG ERROR:", e)

    return render_template_string(HTML, result=result, image=image_data_url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
