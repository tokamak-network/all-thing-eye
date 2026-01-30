"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowsPointingOutIcon } from "@heroicons/react/24/outline";

interface DataAIChatPanelProps {
  selectedFields: string[];
  filters: {
    startDate: string;
    endDate: string;
    project: string;
    selectedMembers: string[];
  };
}

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: Date;
}

const AI_CHAT_SESSIONS_KEY = "ai-chat-sessions";
const AI_CHAT_CURRENT_SESSION_KEY = "ai-chat-current-session";
const AI_CHAT_MODEL_KEY = "ai-chat-model";

export default function DataAIChatPanel({
  selectedFields,
  filters,
}: DataAIChatPanelProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [cachedData, setCachedData] = useState<any>(null);
  const [dataStats, setDataStats] = useState<{ total: number; sources: Record<string, number> } | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom within container only (not the page)
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Reset when selection changes
  useEffect(() => {
    setCachedData(null);
    setDataStats(null);
    setMessages([]);
  }, [
    selectedFields,
    filters.startDate,
    filters.endDate,
    filters.selectedMembers,
    filters.project,
  ]);

  // Load data from custom export API
  const loadData = async () => {
    if (selectedFields.length === 0) {
      setMessages([{
        role: "assistant",
        content: "⚠️ Please select fields to analyze from the left panel first.",
        timestamp: new Date(),
      }]);
      return;
    }

    setIsLoading(true);
    setMessages([]);
    
    try {
      // Determine sources from selected fields
      const sources: string[] = [];
      if (selectedFields.some(f => f.startsWith('github'))) sources.push('github');
      if (selectedFields.some(f => f.startsWith('slack'))) sources.push('slack');
      if (selectedFields.some(f => f.startsWith('notion'))) sources.push('notion');
      if (selectedFields.some(f => f.startsWith('recording'))) sources.push('recordings');
      
      const data = await api.fetchCustomExportData({
        selected_members: filters.selectedMembers.length > 0 ? filters.selectedMembers : undefined,
        start_date: filters.startDate,
        end_date: filters.endDate,
        project: filters.project !== 'all' ? filters.project : undefined,
        selected_fields: selectedFields,
        sources: sources.length > 0 ? sources : undefined,
        limit: 1000,
      });

      setCachedData(data);

      // Calculate stats
      const stats: Record<string, number> = {};
      let total = 0;

      if (data.activities) {
        data.activities.forEach((activity: any) => {
          const source = activity.source_type || activity.sourceType || 'unknown';
          stats[source] = (stats[source] || 0) + 1;
          total++;
        });
      }

      if (data.members) {
        stats['members'] = data.members.length;
        total += data.members.length;
      }

      setDataStats({ total, sources: stats });

      setMessages([{
        role: "assistant",
        content: `✅ **Data loaded!** Total ${total} records\n\nAsk me anything about the data!`,
        timestamp: new Date(),
      }]);

    } catch (error: any) {
      console.error("Data load error:", error);
      setMessages([{
        role: "assistant",
        content: `⚠️ Data load failed: ${error.message || "Unknown error"}`,
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    if (!cachedData) {
      setMessages(prev => [...prev, {
        role: "user",
        content: inputValue,
        timestamp: new Date(),
      }, {
        role: "assistant",
        content: "⚠️ Please click **\"Load\"** button first to load data.",
        timestamp: new Date(),
      }]);
      setInputValue("");
      return;
    }

    const userMessage: ChatMessage = {
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await api.chatWithMCPContext(
        [
          ...messages.filter(m => m.role !== 'system').map(m => ({
            role: m.role,
            content: m.content,
          })),
          { role: "user", content: inputValue },
        ],
        "qwen3-235b",
        {
          raw_data: cachedData,
          data_stats: dataStats,
          filters: {
            startDate: filters.startDate,
            endDate: filters.endDate,
            project: filters.project,
            selectedMembers: filters.selectedMembers,
          },
          selected_fields: selectedFields,
        }
      );

      // Parse response
      let assistantContent = "";
      if (response?.response?.message?.content) {
        assistantContent = response.response.message.content;
      } else if (response?.message?.content) {
        assistantContent = response.message.content;
      } else if (typeof response === "string") {
        assistantContent = response;
      } else {
        assistantContent = JSON.stringify(response, null, 2);
      }

      setMessages(prev => [...prev, {
        role: "assistant",
        content: assistantContent,
        timestamp: new Date(),
      }]);
    } catch (error: any) {
      console.error("AI Chat error:", error);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `⚠️ Error: ${error.message || "Unknown error"}`,
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickQuestions = [
    "Most active member?",
    "Activity summary",
    "Trend analysis",
  ];

  const openFullscreen = () => {
    const sessionId = `data-analysis-${Date.now()}`;
    const sessionsJson = localStorage.getItem(AI_CHAT_SESSIONS_KEY);
    const sessions = sessionsJson ? JSON.parse(sessionsJson) : [];

    const contextMessage = cachedData ? {
      id: `ctx-${Date.now()}`,
      role: "system" as const,
      content: `📊 **Data Analysis Context Loaded**\n\n` +
        `**Period:** ${filters.startDate} ~ ${filters.endDate}\n` +
        `**Fields:** ${selectedFields.join(", ")}\n` +
        `**Total Records:** ${dataStats?.total || 0}\n\n` +
        `Ask me anything about this data!`,
      timestamp: new Date(),
    } : null;

    const sessionMessages = contextMessage 
      ? [contextMessage, ...messages.filter(m => m.role !== "system")]
      : messages;

    const newSession = {
      id: sessionId,
      title: `📊 Data Analysis (${filters.startDate})`,
      messages: sessionMessages,
      lastTimestamp: new Date().toISOString(),
      model: "qwen3-235b",
      dataContext: cachedData ? {
        raw_data: cachedData,
        data_stats: dataStats,
        filters: {
          startDate: filters.startDate,
          endDate: filters.endDate,
          project: filters.project,
          selectedMembers: filters.selectedMembers,
        },
        selected_fields: selectedFields,
      } : null,
    };

    sessions.unshift(newSession);
    localStorage.setItem(AI_CHAT_SESSIONS_KEY, JSON.stringify(sessions));
    localStorage.setItem(AI_CHAT_CURRENT_SESSION_KEY, sessionId);
    localStorage.setItem(AI_CHAT_MODEL_KEY, "qwen3-235b");
    
    router.push("/ai-chat");
  };

  // Format selected fields for display
  const fieldsBySource = selectedFields.reduce((acc, field) => {
    const [source] = field.split('.');
    if (!acc[source]) acc[source] = [];
    acc[source].push(field.split('.').slice(1).join('.'));
    return acc;
  }, {} as Record<string, string[]>);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-[600px] flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-gray-200 bg-gradient-to-r from-blue-500 to-purple-500 rounded-t-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <h3 className="font-semibold text-white text-sm">AI Data Analysis</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={loadData}
              disabled={isLoading || selectedFields.length === 0}
              className="px-2 py-1 bg-white/20 hover:bg-white/30 text-white text-xs rounded transition-colors disabled:opacity-50"
            >
              {isLoading ? "⏳" : "🔄"} Load
            </button>
            <button
              onClick={openFullscreen}
              className="p-1 bg-white/20 hover:bg-white/30 text-white rounded transition-colors"
              title="Open in fullscreen"
            >
              <ArrowsPointingOutIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Selected Fields Display */}
      <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 text-xs">
        <div className="flex flex-wrap gap-1 mb-1">
          {Object.entries(fieldsBySource).map(([source, fields]) => (
            <span key={source} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px]">
              {source}: {fields.length}
            </span>
          ))}
        </div>
        <div className="text-gray-500 text-[10px]">
          📅 {filters.startDate} ~ {filters.endDate}
          {filters.project !== 'all' && ` | 🏷️ ${filters.project}`}
          {filters.selectedMembers.length > 0 && ` | 👥 ${filters.selectedMembers.length}명`}
        </div>
      </div>

      {/* Data Stats Bar */}
      {dataStats && (
        <div className="px-3 py-1.5 bg-green-50 border-b border-green-100 flex items-center gap-1 text-[10px]">
          <span className="text-green-600 font-medium">✅</span>
          {Object.entries(dataStats.sources).map(([source, count]) => (
            <span key={source} className="px-1 py-0.5 bg-green-100 text-green-700 rounded">
              {source}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && !cachedData && (
          <div className="text-center text-gray-400 text-sm py-8">
            <p>👆 Click &quot;Load&quot; to start</p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[90%] rounded-lg p-2 ${
                message.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {message.role === "assistant" ? (
                <div className="prose prose-xs max-w-none text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm">{message.content}</p>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-2">
              <div className="flex items-center gap-2">
                <div className="animate-spin h-3 w-3 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                <span className="text-xs text-gray-600">
                  {cachedData ? "Analyzing..." : "Loading..."}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Questions */}
      {cachedData && (
        <div className="px-3 pb-1">
          <div className="flex flex-wrap gap-1">
            {quickQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => setInputValue(q)}
                className="text-[10px] px-1.5 py-0.5 bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={cachedData ? "Ask a question..." : "Load data first"}
            className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
            disabled={isLoading || !cachedData}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim() || !cachedData}
            className="px-3 py-1.5 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
