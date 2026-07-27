"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getConversations, deleteConversation, renameConversation } from "@/lib/api";
import { Conversation } from "@/lib/types";
import {
  History as HistoryIcon,
  Search,
  Sparkles,
  FileSpreadsheet,
  Image as ImageIcon,
  Wand2,
  Trash2,
  ArrowRight,
  Pin,
  Calendar,
  Film,
  Layers,
  FileText,
  Pencil,
  Check,
  Eye,
  X,
  ChevronLeft,
  ChevronRight,
  Loader2
} from "lucide-react";

type FilterType = "all" | "drafts" | "completed";

// Modal Component for Viewing All Versions
function VersionsModal({ convoId, onClose }: { convoId: string, onClose: () => void }) {
  const [images, setImages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (!convoId) return;
    
    // Fallback logic for sample items
    if (convoId.startsWith("sample-")) {
      const type = convoId.replace("sample-", "");
      setImages([`/api/proxy/sample-thumbnail/${type}`]);
      setLoading(false);
      return;
    }

    const fetchVersions = async () => {
      try {
        setLoading(true);
        const res = await fetch(`/api/proxy/history/conversations/${convoId}/messages`);
        if (res.ok) {
          const data = await res.json();
          // Filter messages that have output files (images)
          const imgMessages = data.messages.filter((m: any) => m.output_file_path);
          const urls = imgMessages.map((m: any) => `/api/proxy/history/messages/${m.id}/image`);
          setImages(urls.length > 0 ? urls : []);
        } else {
          // fallback to single image if messages endpoint fails
          setImages([`/api/proxy/history/conversations/${convoId}/image`]);
        }
      } catch (err) {
        setImages([`/api/proxy/history/conversations/${convoId}/image`]);
      } finally {
        setLoading(false);
      }
    };
    fetchVersions();
  }, [convoId]);

  if (!convoId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="relative bg-white dark:bg-slate-900 w-full max-w-4xl rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            Template Versions <span className="text-slate-500 font-normal text-sm ml-2">({images.length > 0 ? currentIndex + 1 : 0} of {images.length})</span>
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="flex-1 min-h-[500px] flex items-center justify-center bg-slate-100/50 dark:bg-slate-900/50 relative p-6">
          {loading ? (
            <div className="flex flex-col items-center text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin mb-2" />
              <span>Loading versions...</span>
            </div>
          ) : images.length === 0 ? (
            <div className="text-slate-500">No images found for this session.</div>
          ) : (
            <div className="relative flex items-center justify-center w-full h-full">
              {images.length > 1 && (
                <button 
                  onClick={() => setCurrentIndex(prev => prev > 0 ? prev - 1 : images.length - 1)}
                  className="absolute left-2 z-10 p-2 bg-white/90 dark:bg-slate-800/90 rounded-full shadow-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 hover:scale-105 transition-all"
                >
                  <ChevronLeft className="w-6 h-6" />
                </button>
              )}
              
              <img 
                src={images[currentIndex]} 
                alt={`Version ${currentIndex + 1}`}
                className="max-h-[600px] max-w-full object-contain rounded-lg shadow-md"
                onError={(e) => {
                  const target = e.currentTarget;
                  target.style.display = 'none';
                  const placeholder = document.createElement('div');
                  placeholder.className = 'flex flex-col items-center gap-2 text-slate-400 dark:text-slate-500 py-12';
                  placeholder.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg><p class="text-sm font-medium">Image no longer available</p><p class="text-xs text-slate-400">The source file may have been deleted.</p>`;
                  target.parentNode?.appendChild(placeholder);
                }}
              />
              
              {images.length > 1 && (
                <button 
                  onClick={() => setCurrentIndex(prev => prev < images.length - 1 ? prev + 1 : 0)}
                  className="absolute right-2 z-10 p-2 bg-white/90 dark:bg-slate-800/90 rounded-full shadow-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 hover:scale-105 transition-all"
                >
                  <ChevronRight className="w-6 h-6" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Sample creations matching the exact prompt specification for demonstration
const SAMPLE_CREATIONS: Conversation[] = [
  {
    id: "sample-1",
    user_id: "demo",
    title: "Lead Gen Campaign",
    conversation_type: "bulk",
    job_status: "completed",
    created_at: new Date(Date.now() - 86400000 * 1).toISOString(),
  },
  {
    id: "sample-2",
    user_id: "demo",
    title: "Holi Festival Poster",
    conversation_type: "single",
    job_status: "completed",
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
  },
  {
    id: "sample-3",
    user_id: "demo",
    title: "Winter Sale Story",
    conversation_type: "draft" as any,
    job_status: "draft",
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
  },
  {
    id: "sample-4",
    user_id: "demo",
    title: "Product Launch Motion Banner",
    conversation_type: "motion" as any,
    job_status: "completed",
    created_at: new Date(Date.now() - 86400000 * 4).toISOString(),
  },
];

function CardThumbnail({ convo }: { convo: Conversation }) {
  const [imgError, setImgError] = useState(false);

  const type = convo.conversation_type || "single";
  const isDraft = 
    convo.job_status === "draft" || 
    convo.title?.toLowerCase().includes("draft") ||
    (type === "agent" && !convo.template_id);
  const isMotion = type === "motion" || convo.title?.toLowerCase().includes("motion");
  const isBulk = type === "bulk";

  let imageUrl = "";
  if (convo.template_folder && convo.template_id) {
    imageUrl = `/api/proxy/template-thumbnail/${convo.template_folder}/${convo.template_id}`;
  } else if (convo.id && !convo.id.startsWith("sample-")) {
    imageUrl = `/api/proxy/history/conversations/${convo.id}/image`;
  }

  if (isDraft) {
    return (
      <div className="w-full aspect-[16/10] bg-slate-100 dark:bg-slate-800/60 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 border-b border-slate-200 dark:border-slate-800 transition-colors">
        <ImageIcon className="h-9 w-9 stroke-[1.5] text-slate-400 dark:text-slate-500 mb-1" />
        <span className="text-[10px] font-semibold tracking-wider uppercase text-slate-400 dark:text-slate-500">Draft Content</span>
      </div>
    );
  }

  if (isMotion) {
    return (
      <div className="w-full aspect-[16/10] bg-amber-500/5 dark:bg-amber-500/10 flex flex-col items-center justify-center text-amber-500/70 border-b border-slate-200 dark:border-slate-800 transition-colors">
        <Film className="h-9 w-9 stroke-[1.5] text-amber-500/80 mb-1" />
        <span className="text-[10px] font-semibold tracking-wider uppercase text-amber-600/80 dark:text-amber-400/80">Motion Graphic</span>
      </div>
    );
  }

  if (isBulk) {
    return (
      <div className="w-full aspect-[16/10] bg-emerald-500/5 dark:bg-emerald-500/10 p-3 flex gap-2 border-b border-slate-200 dark:border-slate-800 relative overflow-hidden group-hover:bg-emerald-500/10 transition-colors">
        {/* Split Two-Panel Preview */}
        <div className="flex-1 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col items-center justify-center p-1 text-emerald-500 overflow-hidden">
          {!imgError && imageUrl ? (
            <img src={imageUrl} alt="Panel 1" className="w-full h-full object-cover rounded" onError={() => setImgError(true)} />
          ) : (
            <FileSpreadsheet className="h-7 w-7 text-emerald-500/70" />
          )}
        </div>
        <div className="flex-1 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col items-center justify-center p-1 text-emerald-500 overflow-hidden opacity-90">
          {!imgError && imageUrl ? (
            <img src={imageUrl} alt="Panel 2" className="w-full h-full object-cover rounded opacity-80" onError={() => setImgError(true)} />
          ) : (
            <Layers className="h-7 w-7 text-emerald-500/70" />
          )}
        </div>
      </div>
    );
  }

  // Single Poster / Social Post
  return (
    <div className="w-full aspect-[16/10] bg-slate-100 dark:bg-slate-800/60 flex items-center justify-center border-b border-slate-200 dark:border-slate-800 relative overflow-hidden">
      {!imgError && imageUrl ? (
        <img
          src={imageUrl}
          alt={convo.title || "Creation Preview"}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onError={() => setImgError(true)}
        />
      ) : (
        <div className="flex flex-col items-center justify-center gap-1.5 text-slate-400 dark:text-slate-500">
          <ImageIcon className="h-9 w-9 stroke-[1.5]" />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Poster Preview</span>
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [versionsModalId, setVersionsModalId] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("pinned_conversations");
      if (stored) {
        setPinnedIds(JSON.parse(stored));
      }
    } catch (err) {}
  }, []);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const list = await getConversations();
      if (Array.isArray(list) && list.length > 0) {
        setConversations(list);
      } else {
        // Fallback to sample items so design is immediately previewable
        setConversations(SAMPLE_CREATIONS);
      }
    } catch (err) {
      setConversations(SAMPLE_CREATIONS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this creation history?")) {
      return;
    }
    if (!id.startsWith("sample-")) {
      await deleteConversation(id);
    }
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setPinnedIds((prev) => {
      const next = prev.filter((i) => i !== id);
      try {
        localStorage.setItem("pinned_conversations", JSON.stringify(next));
      } catch {}
      return next;
    });
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

  const startEditing = (e: React.MouseEvent, id: string, currentTitle: string) => {
    e.stopPropagation();
    if (id.startsWith("sample-")) return;
    setEditingId(id);
    setEditTitle(currentTitle || "Untitled Creation");
  };

  const saveRename = async (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
    e.stopPropagation();
    if (!editTitle.trim() || editTitle === conversations.find(c => c.id === id)?.title) {
      setEditingId(null);
      return;
    }
    
    // Optimistic update
    setConversations(prev => prev.map(c => c.id === id ? { ...c, title: editTitle } : c));
    setEditingId(null);
    
    const updated = await renameConversation(id, editTitle);
    if (!updated) {
      // Revert if failed
      fetchHistory();
    }
  };

  const filteredConvos = conversations.filter((c) => {
    const q = searchQuery.toLowerCase().trim();
    const matchesSearch =
      !q ||
      (c.title && c.title.toLowerCase().includes(q)) ||
      (c.conversation_type && c.conversation_type.toLowerCase().includes(q));

    const isDraft = 
      c.job_status === "draft" || 
      c.title?.toLowerCase().includes("draft") ||
      (c.conversation_type === "agent" && !c.template_id);
      
    let matchesFilter = true;
    if (filter === "drafts") matchesFilter = isDraft;
    if (filter === "completed") matchesFilter = !isDraft;

    return matchesSearch && matchesFilter;
  });

  const sortedConvos = [...filteredConvos].sort((a, b) => {
    const aPinned = pinnedIds.includes(a.id);
    const bPinned = pinnedIds.includes(b.id);
    if (aPinned && !bPinned) return -1;
    if (!aPinned && bPinned) return 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 pr-16 select-none">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
            Recent Creations
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
            Manage and organize your visual campaign history
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Filter Pills */}
          <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-semibold">
            {(["all", "drafts", "completed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3.5 py-1.5 rounded-lg capitalize transition-all ${
                  filter === f
                    ? "bg-indigo-600 text-white shadow-sm shadow-indigo-600/20"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search creations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full sm:w-56 pl-9 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/40 text-slate-900 dark:text-white placeholder-slate-400"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-4"></div>
        </div>
      ) : sortedConvos.length === 0 ? (
        <div className="text-center py-20 bg-slate-50 dark:bg-slate-900/50 rounded-3xl border border-slate-200 dark:border-slate-800 border-dashed">
          <HistoryIcon className="h-12 w-12 mx-auto text-slate-300 dark:text-slate-700 mb-4" />
          <h3 className="text-lg font-medium text-slate-900 dark:text-slate-100 mb-1">
            No creations found
          </h3>
          <p className="text-slate-500 dark:text-slate-400 text-sm max-w-sm mx-auto">
            We couldn't find any creations matching your search/filter criteria.
          </p>
        </div>
      ) : (
        /* Responsive 4-Column Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {sortedConvos.map((convo) => {
            const isPinned = pinnedIds.includes(convo.id);
            const isDraft = 
              convo.job_status === "draft" || 
              convo.title?.toLowerCase().includes("draft") ||
              (convo.conversation_type === "agent" && !convo.template_id);
            const isMotion = convo.conversation_type === "motion" || convo.title?.toLowerCase().includes("motion");

            let typeBadge = "SINGLE POSTER";
            let badgeStyle = "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/80";
            let link = `/generate?id=${convo.id}`;

            if (isDraft) {
              typeBadge = "DRAFT";
              badgeStyle = "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20";
            } else if (isMotion) {
              typeBadge = "MOTION GRAPHIC";
              badgeStyle = "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20";
            } else if (convo.conversation_type === "bulk") {
              typeBadge = "BULK BATCH";
              badgeStyle = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20";
              link = `/bulk?id=${convo.id}`;
            } else if (convo.conversation_type === "creation_agent") {
              typeBadge = "AI TEMPLATE AGENT";
              badgeStyle = "bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20";
              link = `/create-template?id=${convo.id}`;
            }

            const formattedDate = convo.created_at
              ? new Date(convo.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })
              : "Recent";

            return (
              <div
                key={convo.id}
                onClick={() => {
                  if (!convo.id.startsWith("sample-")) router.push(link);
                }}
                className="group flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden hover:-translate-y-1 hover:shadow-xl hover:shadow-slate-200/50 dark:hover:shadow-black/60 transition-all duration-200 cursor-pointer relative"
              >
                {/* 1. Thumbnail Preview Region */}
                <div className="relative">
                  <CardThumbnail convo={convo} />

                  {/* Pin & Delete Action Overlay (Top Right of Thumbnail) */}
                  <div className="absolute top-2.5 right-2.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900/80 backdrop-blur-sm p-1 rounded-xl border border-slate-700/60 shadow-lg z-10">
                    <button
                      type="button"
                      onClick={(e) => togglePin(e, convo.id)}
                      title={isPinned ? "Unpin" : "Pin"}
                      className={`p-1 rounded-lg hover:bg-slate-800 transition-colors ${
                        isPinned ? "text-amber-400" : "text-slate-300 hover:text-amber-400"
                      }`}
                    >
                      <Pin className={`h-3.5 w-3.5 ${isPinned ? "fill-amber-400" : ""}`} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setVersionsModalId(convo.id);
                      }}
                      title="View All Versions"
                      className="p-1 rounded-lg text-slate-300 hover:text-blue-400 hover:bg-slate-800 transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => startEditing(e, convo.id, convo.title || "")}
                      title="Rename"
                      className="p-1 rounded-lg text-slate-300 hover:text-indigo-400 hover:bg-slate-800 transition-colors"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, convo.id)}
                      title="Delete"
                      className="p-1 rounded-lg text-slate-300 hover:text-red-400 hover:bg-slate-800 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* 2. Content & Metadata Section */}
                <div className="p-4 flex-1 flex flex-col justify-between gap-3">
                  <div className="space-y-1.5">
                    {/* Type Badge */}
                    <div className="flex items-center justify-between">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider ${badgeStyle}`}>
                        {typeBadge}
                      </span>
                      {isPinned && (
                        <Pin className="h-3 w-3 text-amber-500 fill-amber-500" />
                      )}
                    </div>

                    {/* Title */}
                    {editingId === convo.id ? (
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveRename(e, convo.id);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          autoFocus
                          className="w-full text-sm bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                        />
                        <button
                          type="button"
                          onClick={(e) => saveRename(e, convo.id)}
                          className="p-1 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <h3 className="font-bold text-slate-900 dark:text-white text-base line-clamp-1 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                        {convo.title || "Untitled Creation"}
                      </h3>
                    )}
                  </div>

                  {/* 3. Metadata Row */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800/80 text-slate-500 dark:text-slate-400 text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      <span>Edited {formattedDate}</span>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-500 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      
      {/* Versions Gallery Modal */}
      {versionsModalId && (
        <VersionsModal 
          convoId={versionsModalId} 
          onClose={() => setVersionsModalId(null)} 
        />
      )}
    </div>
  );
}
