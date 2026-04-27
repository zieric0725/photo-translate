from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
import mimetypes
from PIL import Image

# 支援 iPhone HEIC
from pillow_heif import register_heif_opener
register_heif_opener()

app = Flask(__name__)
client = OpenAI()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML = """
<!doctype html>
<title>Photo Translate</title>
<h2>上傳照片翻譯</h2>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value=上傳>
</form>

{% if result %}
<hr>
<h3>翻譯結果：</h3>
<pre>{{ result }}</pre>
{% endif %}
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    result = None

    if request.method == "POST":
        file = request.files["file"]

        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # 讀圖片
            with open(filepath, "rb") as f:
                image_data = f.read()

            # 轉 base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # 🔥 自動判斷圖片格式
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                mime_type = "image/jpeg"

            image_url = f"data:{mime_type};base64,{base64_image}"

            try:
                response = client.responses.create(
                    model="gpt-4.1",
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "請讀取圖片中的英文內容，修正錯誤並翻譯成繁體中文，保持條列與排版"
                                },
                                {
                                    "type": "input_image",
                                    "image_url": image_url
                                }
                            ]
                        }
                    ]
                )

                # 取得結果
                result = response.output[0].content[0].text

            except Exception as e:
                result = f"發生錯誤：{str(e)}"
                print("DEBUG ERROR:", e)

    return render_template_string(HTML, result=result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
