"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { sendChatMessage, ChatMessage, ApiError, downloadStatement } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { TithelyButton } from "@/components/tithe-button";

const QUICK_ACTIONS = [
  { label: "What do I owe?", message: "What is my current outstanding balance and what are my open obligations?" },
  { label: "My benefits", message: "What benefits am I entitled to as a member of Addis Kidan?" },
  { label: "Payment history", message: "Show me a summary of my recent payments." },
  { label: "How to pay", message: "How can I make a payment for my contribution?" },
  { label: "Death benefit", message: "How does the death benefit work and who is covered?" },
  { label: "Annual fee", message: "Tell me about the $50 annual maintenance fee." },
];

function BotIcon() {
  return (
    <div className="w-7 h-7 rounded-full bg-green-700 flex items-center justify-center shrink-0">
      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <BotIcon />
      <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 150, 300].map((delay) => (
            <div
              key={delay}
              className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const lines = msg.content.split("\n");

  return (
    <div className={`flex items-end gap-2 ${isUser ? "flex-row-reverse" : ""}`}>
      {!isUser && <BotIcon />}
      <div
        className={`max-w-[80%] px-4 py-3 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-green-700 text-white rounded-br-sm"
            : "bg-white border border-gray-100 text-gray-800 rounded-bl-sm"
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: `Hello${user?.first_name ? `, ${user.first_name}` : ""}! I'm the Addis Kidan virtual assistant. I can help you with your account balance, obligations, benefits, and any questions about the association.\n\nHow can I help you today?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPayment, setShowPayment] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setError("");
      setInput("");
      setShowPayment(false);

      const userMsg: ChatMessage = { role: "user", content: trimmed };
      const newMessages: ChatMessage[] = [...messages, userMsg];
      setMessages(newMessages);
      setLoading(true);

      // Only send the last 10 turns (excluding the greeting)
      const history = newMessages.slice(1, -1).slice(-10);

      try {
        const response = await sendChatMessage(trimmed, history);
        setMessages((prev) => [...prev, { role: "assistant", content: response }]);

        // If the response mentions payment, offer the payment widget
        if (/pay|tithe|online|contribut/i.test(response)) {
          setShowPayment(true);
        }
      } catch (err) {
        if (err instanceof ApiError) setError(err.message);
        else setError("Something went wrong. Please try again.");
        // Remove the user message on error so they can retry
        setMessages(messages);
      } finally {
        setLoading(false);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
    },
    [messages, loading]
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function handleDownloadStatement() {
    downloadStatement().catch(() => setError("Failed to download statement."));
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-4 shrink-0">
        <h1 className="text-xl font-bold text-gray-900">Assistant</h1>
        <p className="text-sm text-gray-500 mt-0.5">Ask about your account, benefits, or obligations</p>
      </div>

      {/* Quick actions */}
      <div className="flex gap-2 overflow-x-auto pb-2 shrink-0 scrollbar-hide">
        {QUICK_ACTIONS.map((a) => (
          <button
            key={a.label}
            onClick={() => send(a.message)}
            disabled={loading}
            className="shrink-0 px-3 py-1.5 text-xs font-medium bg-green-50 text-green-800 border border-green-200 rounded-full hover:bg-green-100 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {a.label}
          </button>
        ))}
        <button
          onClick={handleDownloadStatement}
          className="shrink-0 px-3 py-1.5 text-xs font-medium bg-gray-50 text-gray-700 border border-gray-200 rounded-full hover:bg-gray-100 transition-colors whitespace-nowrap"
        >
          Download statement
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 py-4 min-h-0">
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {loading && <TypingIndicator />}

        {/* Inline payment widget after relevant replies */}
        {showPayment && !loading && (
          <div className="flex items-end gap-2">
            <BotIcon />
            <div className="bg-green-50 border border-green-100 rounded-2xl rounded-bl-sm p-3 max-w-[80%]">
              <p className="text-xs text-green-800 font-medium mb-2">Pay securely via Tithe.ly:</p>
              <TithelyButton label="Pay Now" />
            </div>
          </div>
        )}

        {error && (
          <div className="text-center">
            <span className="text-xs text-red-600 bg-red-50 px-3 py-1.5 rounded-full">{error}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 pt-3 border-t border-gray-100">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question… (Enter to send)"
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent disabled:opacity-50 max-h-32 overflow-y-auto leading-relaxed"
            style={{ minHeight: "42px" }}
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="w-10 h-10 rounded-xl bg-green-700 text-white flex items-center justify-center hover:bg-green-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1.5 text-center">
          Powered by AI · For urgent matters contact the association office
        </p>
      </div>
    </div>
  );
}
