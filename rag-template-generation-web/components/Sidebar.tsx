"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getConversations, deleteConversation, logout, renameConversation } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import SettingsDropdown from "@/components/SettingsDropdown";
import { Conversation } from "@/lib/types";
import { 
  Sparkles, 
  PlusCircle, 
  FileSpreadsheet, 
  Wand2, 
  LayoutGrid, 
  LogOut, 
  History, 
  Image as ImageIcon,
  Layers,
  Library as LibraryIcon,
  ChevronRight,
  Pin,
  Trash2,
  Pencil,
  Check
} from "lucide-react";

interface SidebarProps {
  onSelectConversation?: (convo: Conversation) => void;
  activeConversationId?: string;
}

export default function Sidebar({ onSelectConversation, activeConversationId }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  // Load pinned conversation IDs from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("pinned_conversations");
      if (stored) {
        setPinnedIds(JSON.parse(stored));
      }
    } catch (err) {
      console.warn("Failed to load pinned conversations:", err);
    }
  }, []);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const list = await getConversations();
      setConversations(Array.isArray(list) ? list : []);
    } catch (err) {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await logout();
      router.push("/login");
      router.refresh();
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  const togglePin = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setPinnedIds((prev) => {
      const next = prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id];
      try {
        localStorage.setItem("pinned_conversations", JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this conversation history?")) {
      return;
    }

    const success = await deleteConversation(id);
    if (success) {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setPinnedIds((prev) => {
        const next = prev.filter((i) => i !== id);
        try {
          localStorage.setItem("pinned_conversations", JSON.stringify(next));
        } catch {}
        return next;
      });

      // Automatically refresh history from server
      await fetchHistory();

      if (activeConversationId === id || pathname.includes(id)) {
        router.push("/generate");
        router.refresh();
      }
    }
  };

  const startEditing = (e: React.MouseEvent, id: string, currentTitle: string) => {
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(currentTitle || "Untitled Session");
  };

  const saveRename = async (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
    e.stopPropagation();
    if (!editTitle.trim() || editTitle === conversations.find(c => c.id === id)?.title) {
      setEditingId(null);
      return;
    }
    
    setConversations(prev => prev.map(c => c.id === id ? { ...c, title: editTitle } : c));
    setEditingId(null);
    
    const updated = await renameConversation(id, editTitle);
    if (!updated) {
      fetchHistory();
    }
  };

  const navItems = [
    { label: "Single Poster", href: "/generate", icon: ImageIcon },
    { label: "Bulk Generation", href: "/bulk", icon: FileSpreadsheet },
    { label: "AI Template Agent", href: "/create-template", icon: Wand2 },
  ];

  const completedConversations = conversations.filter((c) => {
    if (c.id.startsWith("sample-")) {
      return c.id !== "sample-3";
    }
    return c.has_image ?? (Boolean(c.template_folder && c.template_id) || Boolean(c.job_completed && c.job_completed > 0));
  });

  const pinnedConvos = completedConversations.filter((c) => pinnedIds.includes(c.id));

  // Calculate date 5 days ago to filter regular convos
  const fiveDaysAgo = new Date();
  fiveDaysAgo.setDate(fiveDaysAgo.getDate() - 5);

  const regularConvos = completedConversations.filter((c) => {
    if (pinnedIds.includes(c.id)) return false;
    if (!c.created_at) return true;
    return new Date(c.created_at) >= fiveDaysAgo;
  });

  const renderConvoCard = (convo: Conversation, isPinned: boolean) => {
    const isSelected = activeConversationId === convo.id;
    let typeBadge = "Single";
    let badgeColor = "bg-blue-500/10 text-blue-400 border-blue-500/20";

    if (convo.conversation_type === "bulk") {
      typeBadge = "Bulk";
      badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    } else if (convo.conversation_type === "creation_agent") {
      typeBadge = "Agent";
      badgeColor = "bg-purple-500/10 text-purple-400 border-purple-500/20";
    }

    return (
      <div
        key={convo.id}
        onClick={() => {
          if (editingId === convo.id) return; // Prevent navigation while editing
          if (onSelectConversation) {
            onSelectConversation(convo);
          } else {
            if (convo.conversation_type === "single") router.push(`/generate?id=${convo.id}`);
            else if (convo.conversation_type === "bulk") router.push(`/bulk?id=${convo.id}`);
            else if (convo.conversation_type === "creation_agent") router.push(`/create-template?id=${convo.id}`);
          }
        }}
        className={`w-full text-left p-2.5 rounded-lg border transition-all flex flex-col gap-1 text-xs group cursor-pointer relative ${
          isSelected
            ? "bg-slate-100 dark:bg-slate-800 border-indigo-500/50 text-slate-900 dark:text-white"
            : "bg-white dark:bg-slate-900/50 border-slate-200 dark:border-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:bg-slate-800/60 hover:text-slate-800 dark:text-slate-200"
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${badgeColor}`}>
              {typeBadge}
            </span>
            {isPinned && (
              <Pin className="h-3 w-3 text-amber-400 fill-amber-400/30" />
            )}
          </div>

          <div className="flex items-center gap-1">
            {/* Quick Actions (Pin & Delete) */}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                onClick={(e) => togglePin(e, convo.id)}
                title={isPinned ? "Unpin conversation" : "Pin conversation"}
                className={`p-1 rounded hover:bg-slate-700/80 transition-colors ${
                  isPinned ? "text-amber-400" : "text-slate-600 dark:text-slate-400 hover:text-amber-300"
                }`}
              >
                <Pin className={`h-3.5 w-3.5 ${isPinned ? "fill-amber-400 text-amber-400" : ""}`} />
              </button>
              <button
                type="button"
                onClick={(e) => startEditing(e, convo.id, convo.title || "")}
                title="Rename conversation"
                className="p-1 rounded text-slate-600 dark:text-slate-400 hover:text-indigo-400 hover:bg-slate-700/80 transition-colors"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={(e) => handleDelete(e, convo.id)}
                title="Delete conversation"
                className="p-1 rounded text-slate-600 dark:text-slate-400 hover:text-red-400 hover:bg-slate-700/80 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            <span className="text-[10px] text-slate-500">
              {convo.created_at ? new Date(convo.created_at).toLocaleDateString() : ""}
            </span>
          </div>
        </div>
        {editingId === convo.id ? (
          <div className="flex items-center gap-1 mt-1 pr-2" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveRename(e, convo.id);
                if (e.key === "Escape") setEditingId(null);
              }}
              autoFocus
              className="w-full text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-1.5 py-0.5 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
            <button
              type="button"
              onClick={(e) => saveRename(e, convo.id)}
              className="p-0.5 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded flex-shrink-0"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <p className="font-medium text-slate-800 dark:text-slate-200 truncate group-hover:text-slate-900 dark:group-hover:text-white pr-2 mt-1">
            {convo.title || "Untitled Session"}
          </p>
        )}
      </div>
    );
  };

  return (
    <aside className="w-72 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col h-screen text-slate-700 dark:text-slate-300 select-none flex-shrink-0">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
          <Sparkles className="h-5 w-5 text-slate-900 dark:text-white" />
        </div>
        <div className="flex-1">
          <h2 className="font-semibold text-slate-900 dark:text-white text-sm tracking-tight">Poster Generator</h2>
          <p className="text-[10px] text-slate-500 font-medium">FastAPI Backend Active</p>
        </div>
        <ThemeToggle />
      </div>

      {/* Main Nav Links */}
      <div className="p-3 space-y-1 border-b border-slate-200 dark:border-slate-800">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600 text-slate-900 dark:text-white shadow-sm shadow-indigo-600/30"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:bg-slate-800/60"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Conversation History Section */}
      <div className="flex-1 overflow-y-auto p-3 pt-10 space-y-4">
        <div className="flex items-center justify-between px-2 text-slate-600 dark:text-slate-400">
          <span className="text-[11px] font-semibold tracking-wider uppercase flex items-center gap-1.5">
            <History className="h-3.5 w-3.5 text-slate-500" />
            Past Conversations
          </span>
          <button
            onClick={fetchHistory}
            className="text-[10px] text-indigo-400 hover:underline"
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="space-y-2 px-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-slate-100 dark:bg-slate-800/50 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : completedConversations.length === 0 ? (
          <p className="text-xs text-slate-500 px-2 py-4 text-center">No past conversations yet</p>
        ) : (
          <div className="space-y-3">
            {/* Pinned Section */}
            {pinnedConvos.length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] uppercase font-semibold text-amber-400 px-2 flex items-center gap-1">
                  <Pin className="h-3 w-3 fill-amber-400/40" />
                  Pinned
                </p>
                {pinnedConvos.map((convo) => renderConvoCard(convo, true))}
              </div>
            )}

            {/* Regular Conversations Section */}
            {regularConvos.length > 0 && (
              <div className="space-y-1">
                {pinnedConvos.length > 0 && (
                  <p className="text-[10px] uppercase font-semibold text-slate-500 px-2 pt-2">
                    Recent
                  </p>
                )}
                {regularConvos.map((convo) => renderConvoCard(convo, false))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer / User & Logout */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
        <SettingsDropdown />
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-slate-100 dark:bg-slate-800/50 hover:bg-red-950/40 hover:text-red-300 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:border-red-900/50 rounded-lg text-xs font-medium transition-all"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
