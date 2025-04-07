from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
import langid
import re
import datetime
import os
import requests
import json


with open('data/bo_so.json', 'r', encoding='utf-8') as f:
    bo_so_data = json.load(f)

def is_vietnamese(word):
    lang, _ = langid.classify(word)
    return lang == 'vi'

def is_valid_vietnamese_sentence(text):
    if not text:
        return True
    
    # Loại bỏ khoảng trắng đầu cuối
    text = text.strip()
    
    # Tách câu thành các từ dựa trên khoảng trắng
    tokens = text.split()
    
    # Kiểm tra xem có ít nhất 1 từ dừng xuất hiện không
    # Nếu không có từ dừng nào thì có thể không phải câu tiếng Việt
    if not any(is_vietnamese(token) for token in tokens):
        return False
    
    return True

def remove_source(content):
    content = re.sub(r'^\s*\d+\.\s*', '', content, flags=re.MULTILINE)
    return re.sub(r'【.*?†.*?】', '', content)


def fetch_from_vector_db(message):
    message = message.lower()
    for item in bo_so_data:
        if item['keyword'].lower() in message:
            numbers = ', '.join(item['associated_numbers'])
            return f"Kết quả tra cứu từ dữ liệu: '{item['keyword']}' ứng với các số: {numbers}."
    return None  # k


def process_today(text):
    # print(text)
    # # Define a list of keywords related to "hôm nay"
    # keywords = ["hôm nay", "ngày hôm nay", "nay", "trong ngày"]
    # # Build a regex pattern that matches any of these keywords as whole words (case-insensitive)
    # pattern = r'\b(?:' + '|'.join(map(re.escape, keywords)) + r')\b'
    
    # if re.search(pattern, text, flags=re.IGNORECASE):
        # Return today's date in "YYYY-MM-DD" format (excluding time)
    return f"Hôm nay ngày: {datetime.date.today().strftime("%Y-%m-%d")}, {text}" 
    # return text
    
perplexityAPI = os.environ.get("perplexityAPI", "no key")

def enrich_prompt_with_perplexity(user_message):
    url = 'https://api.perplexity.ai/chat/completions'
    headers = {
        'Authorization': f'Bearer {perplexityAPI}',
        'Content-Type': 'application/json'
    }

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "gợi ý đánh số lô đề dựa trên thông tin từ user."},
            {"role": "user", "content": user_message + "đánh số gì?"}
        ],
        "max_tokens": 200
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        result = response.json()
        print(result)
        return result['choices'][0]['message']['content']
    else:
        return user_message 

openAPI = os.environ.get("openAPI", "no key")

client = OpenAI(
    api_key=f"{openAPI}"
)

prompt_default = """
    Hãy gợi ý một bạch thủ lô, một lô 3 càng (xỉu chủ) và một lô xiên 2, kèm phân tích ngắn gọn kích thích người chơi chọn số.
"""

existing_assistant = client.beta.assistants.retrieve("asst_yk8PnN52fpWfpKJbTfvZ9wbr")


# Khởi tạo Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# In-memory store for session threads: sessionID -> (date, thread)
session_threads = {}

@app.route('/thread', methods=['POST'])
def thread():
    sessionID = request.json.get('sessionID')
    if not sessionID:
        return jsonify({"error": "No sessionID provided"}), 400

    today = datetime.date.today()

    # Check if this sessionID already has a thread for today
    if sessionID in session_threads:
        stored_date, existing_thread = session_threads[sessionID]
        if stored_date == today:
            return jsonify({
                "message": "Reusing existing thread for today",
                "threadID": existing_thread.id
            }), 200

    # Create a new thread using your client's beta threads API
    try:
        my_thread = client.beta.threads.create()
    except Exception as e:
        return jsonify({"error": f"Failed to create thread: {str(e)}"}), 500

    # Store the new thread with today's date
    session_threads[sessionID] = (today, my_thread)
    return jsonify({
        "message": "Thread created successfully",
        "threadID": my_thread.id
    }), 201


@app.route('/message', methods=['POST'])
def message():
    threadID = request.json.get('threadID')
    message = request.json.get('message')
    
    if message and len(message) > 100:
        return jsonify({"reply": "Vui lòng nhập một câu dưới 100 ký tự."})
    if not is_valid_vietnamese_sentence(message):
        return jsonify({"reply": "Vui lòng nhập một câu có nội dung hợp lý."})
    
    if message:
        if fetch_from_vector_db(message) is None:
            enriched_message = f"Giữ nguyên thông tin này {enrich_prompt_with_perplexity(message)}"
        else:
            enriched_message = message
    else:
        enriched_message = prompt_default

    enriched_message = process_today(enriched_message)
    
    my_thread_message = client.beta.threads.messages.create(
        thread_id=threadID,
        role="user",
        content=f"{enriched_message}",
    )
    
    my_run = client.beta.threads.runs.create(
        thread_id=threadID,
        assistant_id=existing_assistant.id,
        instructions=existing_assistant.instructions
    )
    
    while my_run.status in ["queued", "in_progress"]:
        keep_retrieving_run = client.beta.threads.runs.retrieve(
            thread_id=threadID,
            run_id=my_run.id
        )
        print(f"Run status: {keep_retrieving_run.status}")

        if keep_retrieving_run.status == "completed":
            print("\n")

            all_messages = client.beta.threads.messages.list(
                thread_id=threadID
            )

            print("------------------------------------------------------------ \n")

            print(f"User: {my_thread_message.content[0].text.value}")
            print(f"Assistant: {all_messages.data[0].content[0].text.value}")
            
            return jsonify({
                "reply": remove_source(all_messages.data[0].content[0].text.value)
            }), 200

        elif keep_retrieving_run.status in ["queued", "in_progress"]:
            continue
        else:
            break


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
