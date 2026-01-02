"use client";

import { useState, useRef, useEffect } from "react";
import { XMarkIcon, ChatBubbleLeftRightIcon, ChevronDownIcon } from "@heroicons/react/24/outline";
import { api } from "@/lib/api";

interface FloatingAIChatbotProps {
  selectedFields?: string[];
  filters?: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  };
  contextData?: Record<string, any>;
}

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

const quickQuestions = [
  "Who is the most active contributor?",
  "Show me GitHub vs Slack activity comparison",
  "Which team member has the best code review ratio?",
  "Summarize the overall productivity trends",
  "Are there any outliers in the data?",
];

export default function FloatingAIChatbot({
  selectedFields = [],
  filters,
  contextData,
}: FloatingAIChatbotProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "system-1",
      role: "system",
      content:
        "👋 Hi! I'm your AI assistant. Ask me anything about the data. I can help you analyze trends, compare metrics, and generate insights.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("gpt-oss:120b");
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; size?: string }>>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const chatWindowRef = useRef<HTMLDivElement>(null);
  const modelSelectorRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop =
        messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load available models when chat opens
  useEffect(() => {
    if (isOpen && availableModels.length === 0) {
      loadAvailableModels();
    }
  }, [isOpen]);

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
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [showModelSelector]);

  const loadAvailableModels = async () => {
    try {
      setIsLoadingModels(true);
      const models = await api.listAIModels();
      
      // Handle different response formats
      let modelList: Array<{ name: string; size?: string }> = [];
      if (Array.isArray(models)) {
        modelList = models;
      } else if (models.tags && Array.isArray(models.tags)) {
        modelList = models.tags;
      } else if (models.models && Array.isArray(models.models)) {
        modelList = models.models;
      }

      // Sort by size (largest first) if size information is available
      modelList.sort((a, b) => {
        const sizeA = parseFloat(a.size?.replace(/[^0-9.]/g, '') || '0');
        const sizeB = parseFloat(b.size?.replace(/[^0-9.]/g, '') || '0');
        return sizeB - sizeA;
      });

      setAvailableModels(modelList);
    } catch (error: any) {
      console.error("Failed to load models:", error);
      // Fallback to default models if API fails
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

  // Close chat when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isOpen &&
        chatWindowRef.current &&
        !chatWindowRef.current.contains(event.target as Node) &&
        !(event.target as HTMLElement).closest('[data-chatbot-button]')
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [isOpen]);

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;

    // Add user message
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
      // Prepare context data
      const requestContext: Record<string, any> = {};
      if (selectedFields.length > 0) {
        requestContext.selectedFields = selectedFields;
      }
      if (filters) {
        requestContext.filters = filters;
      }
      // Merge additional context if provided via props
      if (contextData) {
        Object.assign(requestContext, contextData);
      }

      // Prepare messages for API (exclude system message for API call)
      const apiMessages = messages
        .filter((msg) => msg.role !== "system")
        .map((msg) => ({
          role: msg.role as "user" | "assistant",
          content: msg.content,
        }));

      // Add current user message
      apiMessages.push({
        role: "user",
        content: message,
      });

      // Call AI API with selected model
      const response = await api.chatWithAI(apiMessages, selectedModel, requestContext);

      // Extract response content
      // Handle various response formats from AI API
      let aiResponseContent = "";
      
      if (typeof response === "string") {
        aiResponseContent = response;
      } else if (response && typeof response === "object") {
        // Check if response has a nested object with content
        if (response.response) {
          // response.response might be a string or an object
          if (typeof response.response === "string") {
            aiResponseContent = response.response;
          } else if (response.response.content && typeof response.response.content === "string") {
            aiResponseContent = response.response.content;
          } else if (response.response.message && typeof response.response.message === "string") {
            aiResponseContent = response.response.message;
          } else {
            aiResponseContent = JSON.stringify(response.response);
          }
        } else if (response.message) {
          if (typeof response.message === "string") {
            aiResponseContent = response.message;
          } else if (response.message.content && typeof response.message.content === "string") {
            aiResponseContent = response.message.content;
          } else {
            aiResponseContent = JSON.stringify(response.message);
          }
        } else if (response.content && typeof response.content === "string") {
          // Direct content field
          aiResponseContent = response.content;
        } else {
          // Fallback: stringify the entire response
          aiResponseContent = JSON.stringify(response, null, 2);
        }
      } else {
        aiResponseContent = String(response);
      }
      
      // Ensure content is always a string
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
      
      // Extract error details
      const errorDetail = error.response?.data?.detail || error.message || "Unknown error";
      const statusCode = error.response?.status;
      
      // Determine if it's a server-side issue (503, 502, or backend error messages)
      const isServerError = statusCode >= 500 || 
                           errorDetail.includes("Backend error") || 
                           errorDetail.includes("All backend servers failed") ||
                           errorDetail.includes("Service Temporarily Unavailable");
      
      // Fallback to mock response on error
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: isServerError
          ? `⚠️ **AI Service Temporarily Unavailable**\n\nThe AI API server is currently experiencing issues (${statusCode ? `HTTP ${statusCode}` : "Connection Error"}).\n\n**Error Details:** ${errorDetail}\n\n📝 **Using mock response for demonstration:**\n\n${getMockAIResponse(
              message,
              selectedFields,
              filters || {
                startDate: "",
                endDate: "",
                project: "all",
                selectedMembers: [],
              }
            )}`
          : `⚠️ **Error connecting to AI service**: ${errorDetail}\n\nFalling back to mock response:\n\n${getMockAIResponse(
              message,
              selectedFields,
              filters || {
                startDate: "",
                endDate: "",
                project: "all",
                selectedMembers: [],
              }
            )}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickQuestion = (question: string) => {
    handleSendMessage(question);
  };

  return (
    <>
      {/* Floating Button */}
      <button
        data-chatbot-button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 z-[9999] w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all duration-300 ${
          isOpen
            ? "bg-red-500 hover:bg-red-600"
            : "bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
        } text-white`}
        style={{ zIndex: 9999 }}
        aria-label="Open AI Assistant"
      >
        {isOpen ? (
          <XMarkIcon className="w-6 h-6" />
        ) : (
          <ChatBubbleLeftRightIcon className="w-6 h-6" />
        )}
        {!isOpen && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white animate-pulse"></span>
        )}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div
          ref={chatWindowRef}
          className="fixed bottom-24 right-6 z-[9999] w-96 h-[600px] bg-white rounded-lg shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
          style={{ zIndex: 9999 }}
        >
          {/* Header */}
          <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-blue-50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
                  <span className="text-xl">🤖</span>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">
                    AI Data Assistant
                  </h3>
                  <p className="text-xs text-gray-600">
                    Ask questions about your data
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Model Selector */}
                <div className="relative" ref={modelSelectorRef}>
                  <button
                    onClick={() => setShowModelSelector(!showModelSelector)}
                    className="flex items-center gap-1 px-2 py-1 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-xs text-gray-700"
                    disabled={isLoadingModels}
                  >
                    <span className="font-medium">
                      {selectedModel.split(':')[0]}
                      {availableModels.find(m => m.name === selectedModel)?.size 
                        ? ` (${availableModels.find(m => m.name === selectedModel)?.size})`
                        : ''}
                    </span>
                    <ChevronDownIcon className="w-3 h-3" />
                  </button>
                  
                  {showModelSelector && (
                    <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
                      {isLoadingModels ? (
                        <div className="p-3 text-center text-xs text-gray-500">
                          Loading models...
                        </div>
                      ) : (
                        <div className="py-1">
                          {availableModels.map((model) => (
                            <button
                              key={model.name}
                              onClick={() => {
                                setSelectedModel(model.name);
                                setShowModelSelector(false);
                              }}
                              className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center justify-between ${
                                selectedModel === model.name
                                  ? "bg-blue-50 text-blue-700"
                                  : "text-gray-700"
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{model.name.split(':')[0]}</span>
                                {model.size && (
                                  <span className="text-gray-500">({model.size})</span>
                                )}
                              </div>
                              {selectedModel === model.name && (
                                <span className="text-blue-600">✓</span>
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  Online
                </span>
              </div>
            </div>
          </div>

          {/* Data Context Summary (if available) */}
          {(selectedFields.length > 0 || filters) && (
            <div className="p-3 bg-blue-50 border-b border-blue-100">
              <div className="flex items-start gap-2">
                <span className="text-sm">📊</span>
                <div className="flex-1">
                  <p className="text-xs font-medium text-blue-900 mb-1">
                    Current Data Context:
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {selectedFields.length > 0 && (
                      <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                        {selectedFields.length} fields selected
                      </span>
                    )}
                    {filters && (
                      <>
                        <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                          {filters.startDate} ~ {filters.endDate}
                        </span>
                        <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                          {filters.project === "all"
                            ? "All Projects"
                            : filters.project}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] ${
                    message.role === "user"
                      ? "bg-blue-600 text-white"
                      : message.role === "system"
                      ? "bg-gray-100 text-gray-700"
                      : "bg-purple-50 text-gray-800 border border-purple-200"
                  } rounded-lg p-3`}
                >
                  {message.role === "assistant" && (
                    <div className="flex items-center gap-2 mb-2 pb-2 border-b border-purple-200">
                      <span className="text-lg">🤖</span>
                      <span className="text-xs font-medium text-purple-700">
                        AI Assistant
                      </span>
                    </div>
                  )}
                  <p className="text-sm whitespace-pre-wrap">
                    {typeof message.content === "string" 
                      ? message.content 
                      : JSON.stringify(message.content, null, 2)}
                  </p>
                  <p
                    className={`text-xs mt-2 ${
                      message.role === "user"
                        ? "text-blue-200"
                        : "text-gray-500"
                    }`}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce"></div>
                      <div
                        className="w-2 h-2 bg-purple-500 rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-purple-500 rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      ></div>
                    </div>
                    <span className="text-xs text-purple-700">
                      AI is thinking...
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Questions */}
          {messages.length <= 1 && (
            <div className="px-4 py-3 border-t border-gray-200 bg-white">
              <p className="text-xs font-medium text-gray-700 mb-2">
                💡 Quick Questions:
              </p>
              <div className="flex flex-wrap gap-2">
                {quickQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleQuickQuestion(question)}
                    className="text-xs px-3 py-1.5 bg-gray-50 border border-gray-300 text-gray-700 rounded-full hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-4 border-t border-gray-200 bg-white">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(input);
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything about the data..."
                disabled={isLoading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:bg-gray-100 disabled:cursor-not-allowed text-sm"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium flex items-center gap-1 text-sm"
              >
                <span>Send</span>
                <span>✨</span>
              </button>
            </form>
            <p className="text-xs text-gray-500 mt-2">
              🚧 AI responses are simulated. Real AI integration coming in
              Phase 2.
            </p>
          </div>
        </div>
      )}
    </>
  );
}

// Mock AI Response Generator (Phase 2: Replace with actual AI API)
function getMockAIResponse(
  question: string,
  selectedFields: string[],
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  }
): string {
  const lowerQuestion = question.toLowerCase();

  if (
    lowerQuestion.includes("most active") ||
    lowerQuestion.includes("who")
  ) {
    return `Based on the selected data (${filters.startDate} to ${filters.endDate}), **Jake** appears to be the most active contributor with:

• **32 commits** (highest)
• **1,560 lines added**
• **56 Slack messages**
• **10 PRs submitted**

This represents approximately **35% of total team activity** during this period.

💡 **Insight**: Jake's high activity is consistent across both code and communication, indicating strong engagement.`;
  }

  if (
    lowerQuestion.includes("comparison") ||
    lowerQuestion.includes("compare")
  ) {
    return `Here's a **GitHub vs Slack** activity comparison for your selected period:

**Developers** (Monica, Bernard, Jake):
• Avg GitHub: 25 commits
• Avg Slack: 44 messages
• **Ratio**: 1 commit per 1.8 messages

**Non-Developers** (Jamie, Alice):
• Avg GitHub: 2.5 commits
• Avg Slack: 85 messages
• **Ratio**: 1 commit per 34 messages

📊 **Pattern**: Developers maintain balanced communication, while designers/managers show higher Slack engagement relative to code contributions.`;
  }

  if (lowerQuestion.includes("review") || lowerQuestion.includes("ratio")) {
    return `**Code Review Analysis:**

**Bernard** has the best code review ratio:
• 15 reviews given
• 6 PRs submitted
• **Review Ratio**: 2.5 (reviews per PR)

This indicates Bernard is actively participating in quality assurance beyond their own code contributions.

Other team members:
• Jake: 0.8 ratio
• Monica: 1.5 ratio

💡 **Recommendation**: Encourage Jake to increase code review participation to match Bernard's engagement level.`;
  }

  if (
    lowerQuestion.includes("trend") ||
    lowerQuestion.includes("productivity")
  ) {
    return `**Productivity Trends** for ${filters.startDate} to ${filters.endDate}:

📈 **Positive Indicators**:
• High commit velocity (75 total commits)
• Strong communication (203 Slack messages)
• Active collaboration (35 code reviews)

⚠️ **Areas to Monitor**:
• Notion usage is low (47 total edits)
• Drive activity concentrated in design team
• Code review distribution uneven

🎯 **Overall Assessment**: Team shows healthy activity levels with balanced code and communication. Consider promoting cross-functional documentation practices.`;
  }

  if (lowerQuestion.includes("outlier") || lowerQuestion.includes("anomaly")) {
    return `**Outlier Detection** in selected data:

🔍 **Identified Outliers**:

1. **Jamie** (Designer):
   • 0 GitHub commits vs team avg of 16
   • 78 Slack messages (above avg)
   • 35 Drive files (3x team avg)
   
   **Analysis**: Normal pattern for design-focused role.

2. **Alice** (Manager):
   • 92 Slack messages (highest)
   • 20 Notion pages (2x team avg)
   
   **Analysis**: Expected for coordination role.

✅ **Conclusion**: All outliers are justified by role differences. No concerning anomalies detected.`;
  }

  // Default response
  return `I understand you're asking: "${question}"

Based on your current data selection${selectedFields.length > 0 ? ` (${selectedFields.length} fields` : ""}${filters.startDate ? `, ${filters.startDate} to ${filters.endDate}` : ""}${selectedFields.length > 0 || filters.startDate ? ")" : ""}, I can help you analyze:

• **Activity patterns** and trends
• **Member comparisons** and rankings
• **Cross-platform insights** (GitHub, Slack, Notion, Drive)
• **Productivity metrics** and recommendations

Try asking more specific questions like:
• "Who contributed the most to GitHub?"
• "Show me Slack activity by team member"
• "What's the average PR count?"
• "Compare developers vs designers"

🤖 **Note**: This is a simulated response. Real AI will provide more detailed analysis based on your actual data.`;
}

