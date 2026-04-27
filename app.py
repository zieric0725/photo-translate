from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
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

            # 讀圖片並轉 base64
            with open(filepath, "rb") as f:
                image_data = f.read()

            base64_image = base64.b64encode(image_data).decode("utf-8")

            # 🔥 直接用 OpenAI Vision（取代 OCR）
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
                                "image_base64": base64_image
                            }
                        ]
                    }
                ]
            )

            result = response.output[0].content[0].text

    return render_template_string(HTML, result=result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
@app.route("/", methods=["GET", "POST"])
def upload_file():
    result = None

    if request.method == "POST":
        file = request.files["file"]

        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # 讀圖片
            img = Image.open(filepath).convert("RGB")

            # EasyOCR
            import numpy as np
            img_np = np.array(img)

            results = reader.readtext(img_np)

            text = " ".join([res[1] for res in results if res[2] > 0.5])

            print("OCR:", text)

            # 🔥 AI 翻譯（注意縮排）
            prompt = f"""
請修正OCR錯誤並翻譯成繁體中文：
{text}
"""

            response = client.responses.create(
                model="gpt-4.1",
                input=prompt
            )

            result = response.output[0].content[0].text

    return render_template_string(HTML, result=result)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
