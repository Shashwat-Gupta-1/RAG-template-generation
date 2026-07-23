"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { LogOut, Image as ImageIcon, Copy } from "lucide-react";
import { SinglePoster } from "@/components/SinglePoster";
import { BulkPoster } from "@/components/BulkPoster";

export default function Home() {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState<"single" | "bulk">("single");

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col">
      {/* Navbar */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
              <ImageIcon className="w-5 h-5 text-indigo-400" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">RAG Templates</h1>
          </div>
          
          <button
            onClick={logout}
            className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-400 hover:text-white transition-colors rounded-lg hover:bg-zinc-800"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-4 py-8 w-full">
        {/* Tabs */}
        <div className="flex p-1 space-x-1 bg-zinc-900/50 rounded-xl mb-8 w-fit border border-zinc-800">
          <button
            onClick={() => setActiveTab("single")}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === "single"
                ? "bg-zinc-800 text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            Single Poster
          </button>
          <button
            onClick={() => setActiveTab("bulk")}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === "bulk"
                ? "bg-zinc-800 text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            }`}
          >
            <Copy className="w-4 h-4" />
            Bulk Generation
          </button>
        </div>

        {/* Tab Content */}
        <div className="bg-zinc-900/30 border border-zinc-800/50 rounded-2xl min-h-[500px]">
          {activeTab === "single" ? (
            <div className="p-8">
              <SinglePoster />
            </div>
          ) : (
            <div className="p-8">
              <BulkPoster />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
