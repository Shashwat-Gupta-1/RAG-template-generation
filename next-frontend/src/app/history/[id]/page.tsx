"use client";

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, Download, CheckCircle, XCircle, AlertCircle, ArrowLeft, Image as ImageIcon } from 'lucide-react';

export default function HistoryPage() {
  const { id } = useParams();
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [authToken, setAuthToken] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem("token");
        setAuthToken(token);
        if (!token) {
          router.push("/login");
          return;
        }

        const res = await fetch(`http://localhost:8000/history/conversations/${id}/messages`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (!res.ok) {
          throw new Error("Failed to load history data");
        }
        
        const jsonData = await res.json();
        setData(jsonData);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (id) {
      fetchHistory();
    }
  }, [id, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-[#6366f1] animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center p-6 text-center">
        <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Oops, something went wrong</h2>
        <p className="text-gray-400 mb-6">{error || "Could not find this session."}</p>
        <button onClick={() => router.push('/')} className="px-6 py-2 bg-[#6366f1] text-white rounded-lg hover:bg-[#4f46e5] transition-colors">
          Go Back Home
        </button>
      </div>
    );
  }

  const { conversation, messages } = data;
  const isCreation = conversation.conversation_type === 'creation_agent';
  
  const formatDate = (isoString: string) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    return d.toLocaleString();
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-gray-200 p-6 md:p-10 pb-24 md:pl-[260px] transition-all">
      <div className="max-w-[1000px] mx-auto">
        
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button 
            onClick={() => router.back()} 
            className="w-10 h-10 rounded-full bg-[#1a1a2e] border border-gray-800 flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#1f2937] transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-white">{conversation.title || 'Untitled Session'}</h1>
              <span className={`px-2 py-0.5 text-xs font-bold uppercase tracking-wider rounded text-white ${
                isCreation ? 'bg-[#6366f1]' : conversation.conversation_type === 'bulk' ? 'bg-orange-500' : 'bg-teal-500'
              }`}>
                {conversation.conversation_type.replace('_', ' ')}
              </span>
            </div>
            <p className="text-sm text-gray-500">{formatDate(conversation.created_at)}</p>
          </div>
        </div>

        {/* Content Body */}
        {isCreation ? (
          /* CREATION AGENT UI */
          <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 shadow-xl overflow-hidden flex flex-col h-[700px] max-h-[75vh]">
            <div className="bg-[#111827] px-6 py-4 border-b border-gray-800">
              <h3 className="font-semibold text-white">Chat History</h3>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
              {messages.length === 0 ? (
                <p className="text-gray-500 text-center mt-10">No messages found in this session.</p>
              ) : (
                messages.map((msg: any) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-2xl px-5 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-[#6366f1] text-white rounded-br-none' 
                        : 'bg-[#1f2937] text-gray-200 rounded-bl-none border border-gray-700'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      
                      {msg.role === 'assistant' && msg.output_file_path && (
                        <div className="mt-4 bg-[#111827] p-2 rounded-lg border border-gray-800 flex flex-col items-center">
                          <span className="text-xs text-gray-500 uppercase font-semibold tracking-wider mb-2 flex items-center gap-1">
                            <ImageIcon className="w-3 h-3" /> Generated Poster
                          </span>
                          {/* Fetch the image from the backend via the secure token route */}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img 
                            src={`http://localhost:8000/agent/image?path=${encodeURIComponent(msg.output_file_path)}&token=${authToken}`}
                            alt="Generated template" 
                            className="max-h-[300px] object-contain rounded border border-gray-800"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
          /* BULK / SINGLE JOB UI */
          <div className="space-y-6">
            
            {/* Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-5 shadow-lg">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Total Jobs</p>
                <p className="text-3xl font-bold text-white">{conversation.job_total || 0}</p>
              </div>
              <div className="bg-[#1a1a2e] rounded-xl border border-green-900/30 p-5 shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-20"><CheckCircle className="w-12 h-12 text-green-500" /></div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Completed</p>
                <p className="text-3xl font-bold text-green-400">{conversation.job_completed || 0}</p>
              </div>
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-5 shadow-lg">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Skipped</p>
                <p className="text-3xl font-bold text-gray-400">{conversation.job_skipped || 0}</p>
              </div>
              <div className="bg-[#1a1a2e] rounded-xl border border-red-900/30 p-5 shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-20"><XCircle className="w-12 h-12 text-red-500" /></div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Failed</p>
                <p className="text-3xl font-bold text-red-400">{conversation.job_failed || 0}</p>
              </div>
            </div>

            {/* Download Section */}
            {conversation.job_download_url && (
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-8 shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  <h3 className="text-xl font-bold text-white mb-1">Results Ready</h3>
                  <p className="text-sm text-gray-400">Download the zip file containing all your generated posters.</p>
                </div>
                <a 
                  href={`http://localhost:8000${conversation.job_download_url}`} 
                  target="_blank"
                  className="px-6 py-4 bg-[#6366f1] hover:bg-[#4f46e5] text-white font-bold rounded-xl transition-colors shadow-lg shadow-[#6366f1]/20 flex items-center gap-3 whitespace-nowrap"
                >
                  <Download className="w-5 h-5" />
                  Download ZIP
                </a>
              </div>
            )}
            
            {/* Error Section */}
            {conversation.job_error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-5">
                <h4 className="text-red-400 font-bold mb-1 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" /> Job Error
                </h4>
                <p className="text-sm text-red-300">{conversation.job_error}</p>
              </div>
            )}

            {/* Logs / Messages */}
            {messages.length > 0 && (
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 shadow-xl overflow-hidden mt-8">
                <div className="bg-[#111827] px-6 py-4 border-b border-gray-800">
                  <h3 className="font-semibold text-white">Job Logs</h3>
                </div>
                <div className="p-6 max-h-[400px] overflow-y-auto custom-scrollbar font-mono text-sm space-y-2">
                  {messages.map((msg: any) => (
                    <div key={msg.id} className="text-gray-300 border-b border-gray-800 pb-2 last:border-0 last:pb-0">
                      <span className="text-gray-600 mr-3">[{formatDate(msg.created_at)}]</span>
                      <span className={msg.role === 'error' ? 'text-red-400' : 'text-gray-300'}>{msg.content}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
