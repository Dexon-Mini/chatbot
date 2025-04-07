import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import "./ChatBot.css";

const BE_endpoint = "https://59a6a449f4bb091e5320675418f354ee.serveo.net";

// Helper: Get or create a session ID for today and reset query count if needed.
function getSessionId() {
  const storedSession = localStorage.getItem("sessionId");
  const storedDate = localStorage.getItem("sessionDate");
  const today = new Date().toISOString().split("T")[0]; // Format: YYYY-MM-DD
  if (storedSession && storedDate === today) {
    return storedSession;
  } else {
    const newSessionId = Date.now().toString();
    localStorage.setItem("sessionId", newSessionId);
    localStorage.setItem("sessionDate", today);
    localStorage.setItem("remainingQueries", "3"); // Reset remaining queries to 3
    return newSessionId;
  }
}

// Helper: Get today's remaining queries from localStorage.
function getRemainingQueries() {
  const storedRemaining = localStorage.getItem("remainingQueries");
  const storedDate = localStorage.getItem("sessionDate");
  const today = new Date().toISOString().split("T")[0];
  if (storedDate === today && storedRemaining) {
    return parseInt(storedRemaining, 10);
  }
  return 3;
}

// Helper: Decrement remaining queries and update localStorage.
function decrementRemainingQueries() {
  const newRemaining = getRemainingQueries() - 1;
  localStorage.setItem("remainingQueries", newRemaining.toString());
  return newRemaining;
}

// Helper: Add a given number of queries to remaining queries.
function addRemainingQueries(amount) {
  const newRemaining = getRemainingQueries() + amount;
  localStorage.setItem("remainingQueries", newRemaining.toString());
  return newRemaining;
}

// Helper: Check if queries are available.
function canQuery() {
  const remaining = getRemainingQueries();
  if (remaining <= 0) {
    return false;
  }
  return true;
}

function ChatBot() {
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => getSessionId());
  const [remainingQueries, setRemainingQueries] = useState(() =>
    getRemainingQueries()
  );
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [showGreeting, setShowGreeting] = useState(true);
  const [threadID, setThreadID] = useState("");
  const endOfChatRef = useRef(null);
  const inputRef = useRef(null);
  const suggestionText = "Gợi ý số may mắn hôm nay";

  const scrollToBottom = useCallback(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading, scrollToBottom]);

  // Handle recharge (dummy): add 3 queries.
  const handleRecharge = () => {
    const newRemaining = addRemainingQueries(3);
    setRemainingQueries(newRemaining);
  };

  // Open chat: refresh session & thread info, reset greeting and chat history.
  const handleOpenChat = async () => {
    const currentSessionId = getSessionId();
    setSessionId(currentSessionId);
    setRemainingQueries(getRemainingQueries());
    // Open the chatbox immediately and show a connecting message.
    setIsChatOpen(true);
    setChatHistory([{ sender: "bot", text: "Đang gọi Cô Đồng" }]);
    try {
      const response = await axios.post(
        BE_endpoint + "/thread",
        { sessionID: currentSessionId },
        { withCredentials: false }
      );
      setThreadID(response.data.threadID);
      setChatHistory([]);
      setMessage("");
      setShowGreeting(true);
    } catch (error) {
      console.error("Error calling /thread:", error);
      // If connection fails, show error message.
      setChatHistory([{ sender: "bot", text: "Cô Đồng đang nghỉ ngơi" }]);
      setShowGreeting(false);
    }
    setLoading(false);
  };

  const handleCloseChat = () => setIsChatOpen(false);

  const handleSendMessage = async (userMessage) => {
    setLoading(true);
    try {
      if (!canQuery()) {
        setChatHistory((prev) => [
          ...prev,
          { sender: "bot", text: "Hết 3 lượt free mỗi ngày. Nạp card đi bạn." },
        ]);
        setLoading(false);
        return;
      }
      setChatHistory((prev) => [
        ...prev,
        { sender: "user", text: userMessage || suggestionText },
      ]);
      setMessage("");
      const { data } = await axios.post(BE_endpoint + "/message", {
        threadID,
        message: userMessage,
      });
      setChatHistory((prev) => [...prev, { sender: "bot", text: data.reply }]);
      const newRemaining = decrementRemainingQueries();
      setRemainingQueries(newRemaining);
    } catch (error) {
      console.error("Error sending message:", error);
      setChatHistory((prev) => [
        ...prev,
        { sender: "bot", text: "Có lỗi xảy ra. Vui lòng thử lại." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = () => handleSendMessage(null);

  const handleDream = () => {
    setShowGreeting(false);
    setMessage("Tôi mơ thấy ");
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  return (
    <div>
      {isChatOpen && (
        <div className="chat-container">
          <div className="chat-header">
            <div className="header-left">
              <span>Thần đề luận số</span>
            </div>
            <div className="header-right">
              <span className="query-info">
                Số lượt còn lại: {remainingQueries}
              </span>
              <button className="recharge-button" onClick={handleRecharge}>
                Nạp Card
              </button>
              <button className="close-chat-button" onClick={handleCloseChat}>
                ✕
              </button>
            </div>
          </div>
          <div className="chat-window">
            <div className="chat-history">
              {showGreeting && (
                <div className="greeting">
                  <p>Tôi là Thần đề luận số, bạn muốn:</p>
                  <div className="greeting-buttons">
                    <button onClick={handleSuggestion}>{suggestionText}</button>
                    <button onClick={handleDream}>Giải mộng / sổ mơ</button>
                  </div>
                </div>
              )}
              {chatHistory.map((chat, index) => (
                <div
                  key={index}
                  className={`chat-message ${
                    chat.sender === "bot" ? "bot" : "user"
                  }`}
                >
                  <p style={{ margin: 0, whiteSpace: "pre-line" }}>
                    {chat.text}
                  </p>
                </div>
              ))}
              {loading && (
                <div className="chat-message bot loading-message">
                  Đang luận số
                  <span className="dot dot1"></span>
                  <span className="dot dot2"></span>
                  <span className="dot dot3"></span>
                </div>
              )}
              <div ref={endOfChatRef} />
            </div>
            <div className="chat-input">
              <textarea
                ref={inputRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={"Nhập câu hỏi của bạn..."}
                disabled={loading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage(message);
                  }
                }}
              ></textarea>
              <button onClick={() => handleSendMessage(message)} disabled={loading}>
              Gửi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Render floating icon only when chatbox is closed */}
      {!isChatOpen && (
        <div className="floating-icon" onClick={handleOpenChat}></div>
      )}
    </div>
  );
}

export default ChatBot;
