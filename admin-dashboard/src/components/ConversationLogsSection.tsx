"use client";

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Bot, CheckCircle, Sparkles, AlertCircle, RefreshCw, Search } from 'lucide-react';
import { ConversationLog } from '../types';

interface ConversationLogsSectionProps {
  logs: ConversationLog[];
  onAnalyzeLogWithAI: (log: ConversationLog) => Promise<void>;
  analyzingLogId: string | null;
}

export const ConversationLogsSection: React.FC<ConversationLogsSectionProps> = ({
  logs,
  onAnalyzeLogWithAI,
  analyzingLogId,
}) => {
  const [activeTab, setActiveTab] = useState<'All' | 'Flagged' | 'Support'>('All');
  const [sortOrder, setSortOrder] = useState<'Newest' | 'Oldest'>('Newest');
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  const filteredLogs = logs
    .filter((log) => {
      if (activeTab === 'Flagged' && !log.isFlagged) return false;
      if (activeTab === 'Support' && log.category !== 'Support') return false;

      if (userSearchQuery.trim()) {
        const q = userSearchQuery.toLowerCase().trim();
        const matchName = (log.user || '').toLowerCase().includes(q);
        const matchEmail = (log.userEmail || '').toLowerCase().includes(q);
        const matchTitle = (log.sessionTitle || '').toLowerCase().includes(q);
        return matchName || matchEmail || matchTitle;
      }
      return true;
    })
    .sort((a, b) => {
      const timeA = a.timestamp ? new Date(a.timestamp).getTime() : (a.date ? new Date(a.date).getTime() : 0);
      const timeB = b.timestamp ? new Date(b.timestamp).getTime() : (b.date ? new Date(b.date).getTime() : 0);

      if (sortOrder === 'Newest') {
        return timeB - timeA || b.id.localeCompare(a.id);
      }
      return timeA - timeB || a.id.localeCompare(b.id);
    });

  const toggleExpand = (id: string) => {
    setExpandedLogId(expandedLogId === id ? null : id);
  };

  return (
    <section className="animate-fade-in space-y-6">
      {/* Header Filters & User Search Bar */}
      <div className="bg-white rounded-xl border border-[#DDE3EE] p-6 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <h2 className="text-xl font-bold text-[#0D1B3E]">AI Interaction & Conversation Logs</h2>
            <p className="text-xs text-[#45464e] font-medium mt-0.5">
              Viewing conversation history across all users (ordered chronologically by timestamp)
            </p>
          </div>
          <div className="flex gap-2">
            {(['All', 'Flagged', 'Support'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  activeTab === tab
                    ? 'bg-[#1E3A6E] text-white shadow-sm'
                    : 'bg-[#f5f3f6] text-[#45464e] hover:bg-[#eae7eb]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* User Search & Time Sort Controls */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-64 min-w-[200px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#76767f]" />
            <input
              type="text"
              value={userSearchQuery}
              onChange={(e) => setUserSearchQuery(e.target.value)}
              placeholder="Search by user or email..."
              className="w-full pl-9 pr-8 py-2 bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg text-xs font-semibold text-[#0D1B3E] placeholder:text-[#76767f] focus:outline-none focus:ring-1 focus:ring-[#0D1B3E]"
            />
            {userSearchQuery && (
              <button
                onClick={() => setUserSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-[#76767f] hover:text-[#0D1B3E]"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-[#45464e]">Sort:</span>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as 'Newest' | 'Oldest')}
              className="bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg text-xs font-semibold text-[#0D1B3E] px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#0D1B3E]"
            >
              <option value="Newest">Newest First</option>
              <option value="Oldest">Oldest First</option>
            </select>
          </div>
        </div>
      </div>

      {/* Logs List */}
      <div className="space-y-4">
        {filteredLogs.map((log) => {
          const isExpanded = expandedLogId === log.id;
          const isAnalyzing = analyzingLogId === log.id;

          return (
            <div
              key={log.id}
              className={`bg-white rounded-xl border transition-all shadow-sm overflow-hidden ${
                isExpanded ? 'border-[#0D1B3E] ring-1 ring-[#0D1B3E]' : 'border-[#DDE3EE]'
              }`}
            >
              {/* Collapsed Header Bar */}
              <div
                onClick={() => toggleExpand(log.id)}
                className="p-6 flex items-center justify-between cursor-pointer hover:bg-[#f5f3f6] transition-all select-none"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-[#0D1B3E] flex items-center justify-center text-white font-bold text-sm shadow-xs">
                    {log.userInitials}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-base font-bold text-[#0D1B3E] leading-none">{log.user}</h4>
                      {log.isFlagged && (
                        <span className="bg-red-100 text-red-700 text-[10px] px-2 py-0.5 rounded-md font-bold flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Flagged
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#45464e] font-medium mt-1">
                      Session #{log.id.replace('log-', '')} • {log.sessionTitle}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="text-xs font-bold text-[#0D1B3E]">{log.date}</p>
                    <p className="text-[11px] text-[#45464e]">{log.messageCount} Messages</p>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-[#76767f]" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-[#76767f]" />
                  )}
                </div>
              </div>

              {/* Expanded Session Thread */}
              {isExpanded && (
                <div className="p-8 bg-[#ffffff] border-t border-[#DDE3EE] animate-slide-down space-y-6">
                  {/* AI Analysis Summary Bar if available */}
                  {log.aiAnalysis ? (
                    <div className="bg-gradient-to-r from-[#0D1B3E] to-[#1E3A6E] text-white p-5 rounded-xl shadow-md border border-white/10 space-y-2">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wider">
                          <Sparkles className="w-4 h-4" /> Gemini AI Audit Report
                        </div>
                        <span className="bg-green-500/20 text-green-300 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-green-400/30">
                          Score: {log.aiAnalysis.complianceScore}
                        </span>
                      </div>
                      <p className="text-xs leading-relaxed text-slate-100">{log.aiAnalysis.summary}</p>
                      <div className="flex flex-wrap gap-2 pt-2 border-t border-white/10 text-[11px] text-slate-300">
                        <span><b>Sentiment:</b> {log.aiAnalysis.sentiment}</span>
                        <span>•</span>
                        <span><b>Recommendation:</b> {log.aiAnalysis.recommendation}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-end items-center bg-[#f5f3f6] p-3 rounded-xl border border-[#DDE3EE]">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onAnalyzeLogWithAI(log);
                        }}
                        disabled={isAnalyzing}
                        className="px-4 py-2 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {isAnalyzing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Analyzing Log...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Audit Log with AI
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  {/* Messages Thread */}
                  <div className="space-y-6 max-w-4xl mx-auto">
                    {log.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex gap-4 ${
                          msg.sender === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        {(msg.sender === 'system' || msg.sender === 'assistant') && (
                          <div className="w-8 h-8 rounded bg-[#0D1B3E] flex-shrink-0 flex items-center justify-center text-white shadow-xs">
                            <Bot className="w-4 h-4 text-amber-300" />
                          </div>
                        )}

                        <div
                          className={`p-5 rounded-2xl max-w-[85%] text-sm leading-relaxed shadow-sm relative ${
                            msg.sender === 'system' || msg.sender === 'assistant'
                              ? 'bg-[#0D1B3E] text-white rounded-tl-none'
                              : 'bg-[#eae7eb] text-[#1b1b1e] rounded-tr-none'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{msg.text}</p>

                          {/* Render Image or ZIP Artifact Output if present */}
                          {msg.output_file_path && (
                            <div className="mt-4 pt-3 border-t border-white/20">
                              {msg.output_file_path.endsWith('.zip') || (msg as any).is_bulk ? (
                                <div className="flex items-center justify-between bg-black/20 p-3 rounded-lg border border-white/10 text-xs">
                                  <div className="flex items-center gap-2">
                                    <span className="font-bold text-amber-300">📦 Bulk Package (.ZIP)</span>
                                  </div>
                                  <a
                                    href={msg.output_file_path}
                                    download
                                    target="_blank"
                                    rel="noreferrer"
                                    className="px-3 py-1 bg-amber-400 text-black font-bold rounded hover:bg-amber-300 transition-all text-xs"
                                  >
                                    Download ZIP
                                  </a>
                                </div>
                              ) : (
                                <div className="space-y-2">
                                  <span className="text-[11px] font-bold text-amber-300 uppercase tracking-wider block">Generated Poster Output</span>
                                  <img
                                    src={msg.output_file_path}
                                    alt="Generated Poster"
                                    className="w-full max-h-72 object-contain rounded-lg border border-white/10 shadow-sm"
                                    onError={(e) => {
                                      const target = e.currentTarget;
                                      if (!target.src.includes('template.png')) {
                                        target.src = '/templates/branch%20opening/branch_opening01/template.png';
                                      }
                                    }}
                                  />
                                  <a
                                    href={msg.output_file_path}
                                    download
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-block mt-1 text-xs font-bold text-amber-300 hover:underline"
                                  >
                                    Download Full Image ↓
                                  </a>
                                </div>
                              )}
                            </div>
                          )}

                          <div className="flex justify-between items-center mt-2 pt-1 text-[10px] opacity-70">
                            <span>{msg.time}</span>
                            {(msg.sender === 'system' || msg.sender === 'assistant') && (
                              <CheckCircle className="w-3 h-3 text-green-400 inline" />
                            )}
                          </div>
                        </div>

                        {msg.sender === 'user' && (
                          <div className="w-8 h-8 rounded-full bg-[#dbd9dd] flex-shrink-0 flex items-center justify-center font-bold text-xs text-[#0D1B3E]">
                            {log.userInitials}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
