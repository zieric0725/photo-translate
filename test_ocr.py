from openai import OpenAI
import pytesseract
from PIL import Image
import os

from pillow_heif import register_heif_opener
register_heif_opener()

# ✅ 用環境變數（不要寫死 API key）
client = OpenAI()

# Debug（確認有抓到 API key）
print("API KEY:", os.getenv("OPENAI_API_KEY")[:10], "...")

# 讀圖片
files = [f for f in os.listdir() if f.lower().endswith((".png", ".jpg", ".jpeg", ".heic"))]

if not files:

    print("❌ 沒有找到圖片")

    exit()

latest = max(files, key=os.path.getctime)

print("使用圖片：", latest)

img = Image.open(latest)

img = img.convert("RGB")

# OCR
text = pytesseract.image_to_string(img)

print("===== OCR 原始結果 =====")
print(text)

# AI 修正 + 翻譯
prompt = f"""
以下是從圖片OCR出來的內容，可能有錯字。
請幫我：
1. 修正可能的錯誤
2. 翻譯成繁體中文
3. 如果是技術內容，保留專有名詞

內容：
{text}
"""

response = client.responses.create(
    model="gpt-4.1",
    input=prompt
)

result = response.output[0].content[0].text

print("===== AI 修正 + 翻譯 =====")
print(result)
