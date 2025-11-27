"use client";

import { useState, useRef, useEffect } from "react";

interface AIChatPanelProps {
  selectedFields: string[];
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  };
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

export default function AIChatPanel({
  selectedFields,
  filters,
}: AIChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "system-1",
      role: "system",
      content:
        "👋 Hi! I'm your AI assistant. Ask me anything about the data you've selected. I can help you analyze trends, compare metrics, and generate insights.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    // Scroll within container only, not the entire page
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

    // Simulate AI response (Phase 2: Replace with actual API call)
    setTimeout(() => {
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: getMockAIResponse(message, selectedFields, filters),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
      setIsLoading(false);
    }, 1000);
  };

  const handleQuickQuestion = (question: string) => {
    handleSendMessage(question);
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-blue-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-xl">🤖</span>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">AI Data Assistant</h3>
              <p className="text-xs text-gray-600">
                Ask questions about your selected data
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              Online
            </span>
          </div>
        </div>
      </div>

      {/* Data Context Summary */}
      <div className="p-3 bg-blue-50 border-b border-blue-100">
        <div className="flex items-start gap-2">
          <span className="text-sm">📊</span>
          <div className="flex-1">
            <p className="text-xs font-medium text-blue-900 mb-1">
              Current Data Context:
            </p>
            <div className="flex flex-wrap gap-1">
              <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                {selectedFields.length} fields selected
              </span>
              <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                {filters.startDate} ~ {filters.endDate}
              </span>
              <span className="px-2 py-0.5 bg-white text-blue-700 text-xs rounded border border-blue-200">
                {filters.project === "all" ? "All Projects" : filters.project}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="h-[400px] overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] ${
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
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              <p
                className={`text-xs mt-2 ${
                  message.role === "user" ? "text-blue-200" : "text-gray-500"
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
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
          <p className="text-xs font-medium text-gray-700 mb-2">
            💡 Quick Questions:
          </p>
          <div className="flex flex-wrap gap-2">
            {quickQuestions.map((question, index) => (
              <button
                key={index}
                onClick={() => handleQuickQuestion(question)}
                className="text-xs px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-full hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
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
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium flex items-center gap-2"
          >
            <span>Send</span>
            <span>✨</span>
          </button>
        </form>
        <p className="text-xs text-gray-500 mt-2">
          🚧 AI responses are simulated. Real AI integration coming in Phase 2.
        </p>
      </div>
    </div>
  );
}

// Mock AI Response Generator (Phase 2: Replace with actual AI API)
function getMockAIResponse(
  question: string,
  selectedFields: string[],
  filters: any
): string {
  const lowerQuestion = question.toLowerCase();

  if (lowerQuestion.includes("most active") || lowerQuestion.includes("who")) {
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

Based on your current data selection (${selectedFields.length} fields, ${filters.startDate} to ${filters.endDate}), I can help you analyze:

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





