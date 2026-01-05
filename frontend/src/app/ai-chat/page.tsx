"use client";

import { useState, useRef, useEffect } from "react";
import { 
  ArrowLeftIcon, 
  ChevronDownIcon,
  TrashIcon,
  PaperAirplaneIcon,
  PlusIcon,
  ChatBubbleLeftIcon,
  StopCircleIcon
} from "@heroicons/react/24/outline";
import { api } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useRouter } from "next/navigation";
import {
  AI_CHAT_MODEL_KEY,
  AI_CHAT_SESSIONS_KEY,
  AI_CHAT_CURRENT_SESSION_KEY,
  getBroadcastChannel,
} from "@/components/FloatingAIChatbot";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  lastTimestamp: string;
  model: string;
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
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("gpt-oss:120b");
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; size?: string }>>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [agentIterations, setAgentIterations] = useState<number | null>(null);
  const [agentToolCalls, setAgentToolCalls] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const modelSelectorRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load sessions from localStorage on mount
  useEffect(() => {
    const savedSessions = localStorage.getItem(AI_CHAT_SESSIONS_KEY);
    if (savedSessions) {
      const parsedSessions = JSON.parse(savedSessions).map((s: any) => ({
        ...s,
        messages: s.messages.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        }))
      }));
      setSessions(parsedSessions);
      
      const lastSessionId = localStorage.getItem(AI_CHAT_CURRENT_SESSION_KEY);
      if (lastSessionId) {
        const lastSession = parsedSessions.find((s: any) => s.id === lastSessionId);
        if (lastSession) {
          setCurrentSessionId(lastSessionId);
          setMessages(lastSession.messages);
        }
      }
    }
    
    const storedModel = localStorage.getItem(AI_CHAT_MODEL_KEY);
    if (storedModel) setSelectedModel(storedModel);
    
    loadAvailableModels();
  }, []);

  // Update current session messages when they change
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      setSessions(prev => {
        const updated = prev.map(s => 
          s.id === currentSessionId 
            ? { ...s, messages, lastTimestamp: new Date().toISOString() } 
            : s
        );
        localStorage.setItem(AI_CHAT_SESSIONS_KEY, JSON.stringify(updated));
        return updated;
      });
    }
  }, [messages, currentSessionId]);

  // Create a new chat session
  const createNewSession = () => {
    const sessionId = `session-${Date.now()}`;
    const newSession: ChatSession = {
      id: sessionId,
      title: "New Chat",
      messages: [systemMessage],
      lastTimestamp: new Date().toISOString(),
      model: selectedModel
    };
    
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(sessionId);
    setMessages([systemMessage]);
    localStorage.setItem(AI_CHAT_CURRENT_SESSION_KEY, sessionId);
  };

  const switchSession = (sessionId: string) => {
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      setCurrentSessionId(sessionId);
      setMessages(session.messages);
      localStorage.setItem(AI_CHAT_CURRENT_SESSION_KEY, sessionId);
    }
  };

  const deleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setSessions(prev => {
      const updated = prev.filter(s => s.id !== sessionId);
      localStorage.setItem(AI_CHAT_SESSIONS_KEY, JSON.stringify(updated));
      return updated;
    });
    
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null);
      setMessages([systemMessage]);
      localStorage.removeItem(AI_CHAT_CURRENT_SESSION_KEY);
    }
  };

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
        { name: "llama3.1:8b", size: "8.0B" },
        { name: "deepseek-r1:8b", size: "8.2B" },
      ]);
    } finally {
      setIsLoadingModels(false);
    }
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;

    // Create a new session if none exists
    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
      const sessionId = `session-${Date.now()}`;
      const newSession: ChatSession = {
        id: sessionId,
        title: message.substring(0, 30) + "...",
        messages: [systemMessage],
        lastTimestamp: new Date().toISOString(),
        model: selectedModel
      };
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(sessionId);
      activeSessionId = sessionId;
      localStorage.setItem(AI_CHAT_CURRENT_SESSION_KEY, sessionId);
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: new Date(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Update title if it's the first user message
    if (messages.length <= 1) {
      setSessions(prev => prev.map(s => 
        s.id === activeSessionId ? { ...s, title: message.substring(0, 30) + "..." } : s
      ));
    }

    try {
      const apiMessages = newMessages
        .filter((msg) => msg.role !== "system")
        .map((msg) => ({
          role: msg.role as "user" | "assistant",
          content: msg.content,
        }));

      let response;
      setAgentIterations(null);
      setAgentToolCalls([]);
      
      // Use Agent Mode by default
      response = await api.chatWithAgent(
        apiMessages,
        selectedModel,
        10,
        controller.signal
      );

      let aiResponseContent = "";
      
      if (typeof response === "string") {
        aiResponseContent = response;
      } else if (response && typeof response === "object") {
        // Handle agent metadata
        if (response.iterations) setAgentIterations(response.iterations);
        if (response.tool_calls) setAgentToolCalls(response.tool_calls);

        if (response.answer) {
          aiResponseContent = response.answer;
        } else if (response.response?.message?.content) {
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
      if (error.name === "CanceledError" || error.name === "AbortError") {
        console.log("🛑 Request was canceled by user");
        return;
      }

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
      abortControllerRef.current = null;
    }
  };

  const handleStopRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
      abortControllerRef.current = null;
      console.log("🛑 Stop button clicked, request aborted");
    }
  };

  return (
    <div className="flex h-screen bg-white overflow-hidden text-gray-900">
      {/* Sidebar */}
      <aside className="w-72 bg-gray-50 flex flex-col border-r border-gray-200">
        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={createNewSession}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-white hover:bg-white hover:shadow-md border border-gray-200 rounded-xl transition-all text-sm font-semibold text-gray-700 shadow-sm"
          >
            <PlusIcon className="w-5 h-5 text-purple-600" />
            New Chat
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto px-3 space-y-1">
          <div className="px-2 py-2 text-[10px] font-bold text-gray-400 uppercase tracking-wider">
            Recent Conversations
          </div>
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => switchSession(session.id)}
              className={`group flex items-center justify-between gap-3 px-3 py-3 rounded-xl cursor-pointer transition-all text-sm ${
                currentSessionId === session.id
                  ? "bg-white text-purple-700 shadow-sm border border-purple-100 font-medium"
                  : "text-gray-600 hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-100"
              }`}
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <ChatBubbleLeftIcon className={`w-4 h-4 flex-shrink-0 ${currentSessionId === session.id ? 'text-purple-500' : 'text-gray-400'}`} />
                <span className="truncate">{session.title}</span>
              </div>
              <button
                onClick={(e) => deleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded-lg transition-all"
              >
                <TrashIcon className="w-4 h-4 text-gray-400 hover:text-red-500" />
              </button>
            </div>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50/50 text-[10px] text-gray-400 text-center font-medium">
          ALL-THING-EYE ANALYTICS
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden">
        {/* Header */}
        <header className="bg-white border-b border-gray-100 shadow-sm z-10">
          <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push("/")}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-lg font-bold text-gray-900">AI Data Assistant</h1>
                <p className="text-xs text-gray-600">
                  {currentSessionId ? sessions.find(s => s.id === currentSessionId)?.title : "Start a new conversation"}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 rounded-lg">
                <span className="text-sm font-medium text-purple-900">
                  🤖 Agent Mode
                </span>
              </div>

              {/* Model Selector */}
              <div className="relative" ref={modelSelectorRef}>
                <button
                  onClick={() => setShowModelSelector(!showModelSelector)}
                  className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700"
                  disabled={isLoadingModels}
                >
                  <span className="truncate max-w-[120px]">
                    {selectedModel}
                  </span>
                  <ChevronDownIcon className="w-4 h-4" />
                </button>
                
                {showModelSelector && (
                  <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
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
                          <div className="flex flex-col">
                            <span className="font-medium">{model.name}</span>
                            {model.size && <span className="text-xs text-gray-500">{model.size}</span>}
                          </div>
                          {selectedModel === model.name && <span className="text-purple-600">✓</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-hidden flex flex-col relative">
          {/* Messages */}
          <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-gray-50/30">
            {messages.length <= 1 && !currentSessionId && (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
                <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-blue-500 rounded-2xl flex items-center justify-center shadow-xl text-4xl mb-2">
                  🤖
                </div>
                <h2 className="text-2xl font-bold text-gray-900">How can I help you today?</h2>
                <p className="text-gray-500 max-w-md">
                  Select a past conversation or start a new one to analyze your team's data.
                </p>
              </div>
            )}

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
                      prose-headings:text-gray-900 prose-headings:font-bold
                      prose-p:text-gray-700 prose-strong:text-purple-700 
                      prose-ul:text-gray-700 prose-ol:text-gray-700 prose-li:marker:text-purple-500 
                      prose-table:text-sm prose-table:w-full prose-table:border-collapse
                      prose-th:bg-purple-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-th:border prose-th:border-purple-100
                      prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-100
                      prose-code:bg-purple-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-purple-700 
                      prose-pre:bg-gray-900 prose-pre:text-gray-100
                      [&_table]:w-full [&_table]:border-collapse [&_table]:my-4
                      [&_th]:text-left [&_td]:text-left">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-base whitespace-pre-wrap">{message.content}</p>
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
                    <div className="flex flex-col">
                      <span className="text-sm text-purple-700 font-medium">AI is thinking...</span>
                      {agentIterations !== null && (
                        <span className="text-xs text-purple-500">
                          {agentIterations} iterations, {agentToolCalls.length} tool calls
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Questions (show only if few messages) */}
          {messages.length <= 1 && (
            <div className="px-6 pb-4 max-w-4xl mx-auto w-full">
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
          <div className="p-6 bg-white border-t border-gray-100">
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
                  className="flex-1 px-5 py-4 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all text-base shadow-sm"
                />
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="px-8 py-4 bg-purple-600 text-white rounded-2xl hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-semibold flex items-center gap-2 shadow-lg shadow-purple-100"
                >
                  <span>Send</span>
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
                {isLoading && (
                  <button
                    type="button"
                    onClick={handleStopRequest}
                    className="px-6 py-4 bg-red-50 text-red-600 border border-red-200 rounded-2xl hover:bg-red-100 transition-colors flex items-center gap-2 font-semibold shadow-lg shadow-red-100"
                    title="Stop generation"
                  >
                    <StopCircleIcon className="w-6 h-6" />
                    <span>Stop</span>
                  </button>
                )}
              </div>
              <p className="text-[10px] text-gray-400 mt-3 text-center">
                AI Agent autonomously uses tools to access GitHub, Slack, and project data.
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

