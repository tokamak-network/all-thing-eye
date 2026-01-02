"use client";

import { useState, useRef, useEffect } from "react";
import { 
  ArrowLeftIcon, 
  ChevronDownIcon,
  TrashIcon,
  PaperAirplaneIcon
} from "@heroicons/react/24/outline";
import { api } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useRouter } from "next/navigation";
import {
  AI_CHAT_STORAGE_KEY,
  AI_CHAT_MODEL_KEY,
  AI_CHAT_MCP_KEY,
  loadMessagesFromStorage,
  saveMessagesToStorage,
  getBroadcastChannel,
} from "@/components/FloatingAIChatbot";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

const quickQuestions = [
  "Who is the most active contributor this month?",
  "Show me GitHub vs Slack activity comparison",
  "What are the top 5 most active repositories?",
  "Summarize the overall productivity trends",
  "What's the status of project OOO?",
  "Compare activity across all projects",
  "Who has the best code review ratio?",
  "Show me weekly activity breakdown",
];

const systemMessage: Message = {
  id: "system-1",
  role: "system",
  content:
    "👋 Hi! I'm your AI assistant with access to All-Thing-Eye data. I can answer questions about team members, projects, GitHub commits, Slack messages, and more. Try asking about specific projects or team members!",
  timestamp: new Date(),
};

export default function AIChat() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([systemMessage]);
  const [useMCP, setUseMCP] = useState(true);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("gpt-oss:120b");
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; size?: string }>>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const modelSelectorRef = useRef<HTMLDivElement>(null);

  // Load messages from localStorage on mount
  useEffect(() => {
    const stored = loadMessagesFromStorage();
    if (stored.length > 0) {
      setMessages(stored);
    }
    
    const storedModel = localStorage.getItem(AI_CHAT_MODEL_KEY);
    if (storedModel) setSelectedModel(storedModel);
    
    const storedMCP = localStorage.getItem(AI_CHAT_MCP_KEY);
    if (storedMCP) setUseMCP(storedMCP === "true");
    
    loadAvailableModels();
  }, []);

  // Listen for BroadcastChannel messages from floating chat
  useEffect(() => {
    const channel = getBroadcastChannel();
    if (!channel) return;

    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === "messages_updated") {
        const newMessages = event.data.messages.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        }));
        setMessages(newMessages);
      }
    };

    channel.addEventListener("message", handleMessage);
    return () => {
      channel.removeEventListener("message", handleMessage);
    };
  }, []);

  // Save messages whenever they change
  useEffect(() => {
    if (messages.length > 1) {
      saveMessagesToStorage(messages);
      localStorage.setItem(AI_CHAT_MODEL_KEY, selectedModel);
      localStorage.setItem(AI_CHAT_MCP_KEY, String(useMCP));
    }
  }, [messages, selectedModel, useMCP]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Close model selector when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        showModelSelector &&
        modelSelectorRef.current &&
        !modelSelectorRef.current.contains(event.target as Node)
      ) {
        setShowModelSelector(false);
      }
    };

    if (showModelSelector) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showModelSelector]);

  const loadAvailableModels = async () => {
    try {
      setIsLoadingModels(true);
      const models = await api.listAIModels();
      
      let modelList: Array<{ name: string; size?: string }> = [];
      if (Array.isArray(models)) {
        modelList = models;
      } else if (models.tags && Array.isArray(models.tags)) {
        modelList = models.tags;
      } else if (models.models && Array.isArray(models.models)) {
        modelList = models.models;
      }

      modelList.sort((a, b) => {
        const sizeA = parseFloat(a.size?.replace(/[^0-9.]/g, '') || '0');
        const sizeB = parseFloat(b.size?.replace(/[^0-9.]/g, '') || '0');
        return sizeB - sizeA;
      });

      setAvailableModels(modelList);
    } catch (error) {
      console.error("Failed to load models:", error);
      setAvailableModels([
        { name: "gpt-oss:120b", size: "116.8B" },
        { name: "gpt-oss:20b", size: "20.9B" },
        { name: "qwen3:30b", size: "30.5B" },
        { name: "gemma3:27b", size: "27.4B" },
        { name: "qwen3:8b", size: "8.2B" },
      ]);
    } finally {
      setIsLoadingModels(false);
    }
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const apiMessages = messages
        .filter((msg) => msg.role !== "system")
        .map((msg) => ({
          role: msg.role as "user" | "assistant",
          content: msg.content,
        }));

      apiMessages.push({ role: "user", content: message });

      let response;
      
      if (useMCP) {
        response = await api.chatWithMCPContext(apiMessages, selectedModel, {});
      } else {
        response = await api.chatWithAI(apiMessages, selectedModel, {});
      }

      let aiResponseContent = "";
      
      if (typeof response === "string") {
        aiResponseContent = response;
      } else if (response && typeof response === "object") {
        if (response.response?.message?.content) {
          aiResponseContent = response.response.message.content;
        } else if (response.message?.content) {
          aiResponseContent = response.message.content;
        } else if (typeof response.response === "string") {
          aiResponseContent = response.response;
        } else if (typeof response.message === "string") {
          aiResponseContent = response.message;
        } else if (typeof response.content === "string") {
          aiResponseContent = response.content;
        } else {
          aiResponseContent = JSON.stringify(response, null, 2);
        }
      } else {
        aiResponseContent = String(response);
      }
      
      if (typeof aiResponseContent !== "string") {
        aiResponseContent = JSON.stringify(aiResponseContent, null, 2);
      }

      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: aiResponseContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error: any) {
      console.error("AI API Error:", error);
      const errorDetail = error.response?.data?.detail || error.message || "Unknown error";
      
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: `⚠️ **Error connecting to AI service**: ${errorDetail}\n\nPlease try again or check the AI service status.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([systemMessage]);
    localStorage.removeItem(AI_CHAT_STORAGE_KEY);
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-gray-50 to-purple-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.back()}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
              </button>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-500 rounded-xl flex items-center justify-center shadow-lg">
                  <span className="text-2xl">🤖</span>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">AI Data Assistant</h1>
                  <p className="text-sm text-gray-600">Ask anything about your team's activity data</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {/* MCP Toggle */}
              <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 rounded-lg">
                <span className="text-sm font-medium text-purple-900">
                  {useMCP ? "🔌 MCP Active" : "Direct Mode"}
                </span>
                <button
                  onClick={() => setUseMCP(!useMCP)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    useMCP ? "bg-purple-600" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      useMCP ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {/* Model Selector */}
              <div className="relative" ref={modelSelectorRef}>
                <button
                  onClick={() => setShowModelSelector(!showModelSelector)}
                  className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700"
                  disabled={isLoadingModels}
                >
                  <span>
                    {selectedModel.split(':')[0]}
                    {availableModels.find(m => m.name === selectedModel)?.size 
                      ? ` (${availableModels.find(m => m.name === selectedModel)?.size})`
                      : ''}
                  </span>
                  <ChevronDownIcon className="w-4 h-4" />
                </button>
                
                {showModelSelector && (
                  <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
                    {isLoadingModels ? (
                      <div className="p-4 text-center text-sm text-gray-500">Loading models...</div>
                    ) : (
                      <div className="py-1">
                        {availableModels.map((model) => (
                          <button
                            key={model.name}
                            onClick={() => {
                              setSelectedModel(model.name);
                              setShowModelSelector(false);
                            }}
                            className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center justify-between ${
                              selectedModel === model.name ? "bg-purple-50 text-purple-700" : "text-gray-700"
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{model.name.split(':')[0]}</span>
                              {model.size && <span className="text-gray-500">({model.size})</span>}
                            </div>
                            {selectedModel === model.name && <span className="text-purple-600">✓</span>}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Clear Chat */}
              <button
                onClick={clearChat}
                className="p-2 hover:bg-red-50 text-gray-500 hover:text-red-600 rounded-lg transition-colors"
                title="Clear chat"
              >
                <TrashIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-hidden max-w-6xl mx-auto w-full">
        <div className="h-full flex flex-col">
          {/* Messages */}
          <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-3xl ${
                    message.role === "user"
                      ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-md"
                      : message.role === "system"
                      ? "bg-white text-gray-700 border border-gray-200 shadow-sm"
                      : "bg-white text-gray-800 border border-purple-200 shadow-md"
                  } rounded-2xl p-5`}
                >
                  {message.role === "assistant" && (
                    <div className="flex items-center gap-2 mb-3 pb-3 border-b border-purple-100">
                      <span className="text-xl">🤖</span>
                      <span className="text-sm font-semibold text-purple-700">AI Assistant</span>
                    </div>
                  )}
                  
                  {message.role === "assistant" || message.role === "system" ? (
                    <div className="prose prose-sm max-w-none prose-purple 
                      prose-headings:text-gray-900 prose-headings:font-semibold 
                      prose-p:text-gray-700 prose-strong:text-gray-900 
                      prose-ul:text-gray-700 prose-ol:text-gray-700 prose-li:marker:text-purple-500 
                      prose-table:text-sm prose-table:w-full prose-table:border-collapse
                      prose-th:bg-purple-100 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-th:border prose-th:border-purple-200
                      prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-200
                      prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-purple-700 
                      prose-pre:bg-gray-900 prose-pre:text-gray-100
                      [&_table]:w-full [&_table]:border-collapse [&_table]:my-4
                      [&_th]:text-left [&_td]:text-left">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {typeof message.content === "string" 
                          ? message.content 
                          : JSON.stringify(message.content, null, 2)}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-base whitespace-pre-wrap">
                      {typeof message.content === "string" 
                        ? message.content 
                        : JSON.stringify(message.content, null, 2)}
                    </p>
                  )}
                  
                  <p className={`text-xs mt-3 ${
                    message.role === "user" ? "text-blue-200" : "text-gray-400"
                  }`}>
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white border border-purple-200 rounded-2xl p-5 shadow-md">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-bounce"></div>
                      <div className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                      <div className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                    </div>
                    <span className="text-sm text-purple-700 font-medium">AI is thinking...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Questions (show only if few messages) */}
          {messages.length <= 2 && (
            <div className="px-6 pb-4">
              <p className="text-sm font-medium text-gray-600 mb-3">💡 Suggested questions:</p>
              <div className="flex flex-wrap gap-2">
                {quickQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleSendMessage(question)}
                    className="text-sm px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-full hover:bg-purple-50 hover:border-purple-300 hover:text-purple-700 transition-colors shadow-sm"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="p-6 bg-white border-t border-gray-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(input);
              }}
              className="max-w-4xl mx-auto"
            >
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask me anything about your team's data..."
                  disabled={isLoading}
                  className="flex-1 px-5 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed text-base shadow-sm"
                />
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-semibold flex items-center gap-2 shadow-lg shadow-purple-200"
                >
                  <span>Send</span>
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
              </div>
              {useMCP && (
                <p className="text-xs text-purple-600 mt-2 text-center">
                  🔌 MCP is active - AI has access to your GitHub, Slack, and project data
                </p>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

