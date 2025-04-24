import os
from quart import Quart, request, jsonify
from quart_cors import cors
import datetime
import langid
import re
import time
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model

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


def process_today(text):
    # print(text)
    # Define a list of keywords related to "hôm nay"
    keywords = ["hôm nay", "ngày hôm nay", "nay", "trong ngày"]
    # Build a regex pattern that matches any of these keywords as whole words (case-insensitive)
    pattern = r'\b(?:' + '|'.join(map(re.escape, keywords)) + r')\b'
    
    if re.search(pattern, text, flags=re.IGNORECASE):
        # Return today's date in "YYYY-MM-DD" format (excluding time)
        return f"Hôm nay ngày: {datetime.date.today().strftime("%Y-%m-%d")}, {text}" 
    return text


def load_system_instructions(path: str = "data/system_instructions.txt", encoding: str = "utf-8") -> str:
    try:
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
        return content
    except FileNotFoundError:
        raise FileNotFoundError(f"Không tìm thấy file tại đường dẫn: {path}")
    except IOError as e:
        raise IOError(f"Lỗi khi đọc file {path}: {e}")


if not os.environ.get("FIREWORKS_API_KEY"):
    os.environ["FIREWORKS_API_KEY"] = "fw_3ZbGMBj2ZMJ1VvSLF2nFx1Ld"

model = init_chat_model("accounts/fireworks/models/deepseek-v3", model_provider="fireworks")

# Define the function that calls the model
async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": response}


# Define a new graph
workflow = StateGraph(state_schema=MessagesState)
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
fireworks = workflow.compile(checkpointer=MemorySaver())


# Khởi tạo Quart app
app = cors(Quart(__name__), allow_origin="*")

# In-memory store for session threads: sessionID -> (date, thread)
session_threads = {}

@app.route('/thread', methods=['POST'])
async def thread():
    data = await request.get_json()
    sessionID = data.get("sessionID")
    if not sessionID:
        return jsonify({"error": "No sessionID provided"}), 400

    today = datetime.date.today()

    # Check if this sessionID already has a thread for today
    if sessionID in session_threads:
        stored_date, existing_thread = session_threads[sessionID]
        if stored_date == today:
            time.sleep(1)
            return jsonify({
                "message": "Reusing existing thread for today",
                "threadID": existing_thread
            }), 200

    # Create a new thread using your client's beta threads API
    try:
        config = {"configurable": {"thread_id": sessionID}}
        await fireworks.ainvoke({"messages": [SystemMessage(
            content=load_system_instructions()
        )]}, config)
    except Exception as e:
        return jsonify({"error": f"Failed to create thread: {str(e)}"}), 500

    # Store the new thread with today's date
    session_threads[sessionID] = (today, sessionID)
    return jsonify({
        "message": "Thread created successfully",
        "threadID": sessionID
    }), 201


@app.route('/message', methods=['POST'])
async def message():
    data = await request.get_json()
    threadID = data.get("threadID")
    message = data.get("message")
    
    if message and len(message) > 100:
        return jsonify({"reply": "Vui lòng nhập một câu dưới 100 ký tự."})
    if not is_valid_vietnamese_sentence(message):
        return jsonify({"reply": "Vui lòng nhập một câu có nội dung hợp lý."})
    
    message = message or "Hãy gợi ý một bạch thủ lô, một lô 3 càng (xỉu chủ) và một lô xiên 2 cho hôm nay."
    config = {"configurable": {"thread_id": threadID}}
    
    message = process_today(message)
    
    print(message)

    output = await fireworks.ainvoke(
        {"messages": [
            HumanMessage(
                content=message
            )
        ], "language": "Vietnamese"},
        config
    )

    print(output["messages"][-1].content)
    
    return jsonify({
        "reply": output["messages"][-1].content
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)