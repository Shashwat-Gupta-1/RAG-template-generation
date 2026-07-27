"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Library as LibraryIcon,
  Search,
  Sparkles,
  FileSpreadsheet,
  Image as ImageIcon,
  Layers,
  ArrowRight,
  RefreshCw,
  Folder,
  Sliders,
  CheckCircle,
  Plus
} from "lucide-react";

interface LayerMeta {
  id: string;
  type: string;
  llm_can_invent: boolean;
}

interface TemplateItem {
  template_id: string;
  folder: string;
  description: string;
  thumbnail_url: string;
  canvas: { width?: number; height?: number };
  layers: LayerMeta[];
}

interface CategoryItem {
  folder: string;
  display_name: string;
  templates: TemplateItem[];
}

export default function LibraryPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const fetchLibrary = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/proxy/templates/library");
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories || []);
      }
    } catch (err) {
      console.warn("Failed to fetch template library:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLibrary();
  }, []);

  // Filter templates based on search & selected category
  const allTemplates: (TemplateItem & { category_display: string })[] = [];
  categories.forEach((cat) => {
    cat.templates.forEach((t) => {
      allTemplates.push({
        ...t,
        category_display: cat.display_name,
      });
    });
  });

  const filteredTemplates = allTemplates.filter((t) => {
    const matchesCat = selectedCategory === "all" || t.folder === selectedCategory;
    const q = searchQuery.toLowerCase().trim();
    const matchesSearch =
      !q ||
      t.template_id.toLowerCase().includes(q) ||
      t.folder.toLowerCase().includes(q) ||
      t.category_display.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.layers.some((l) => l.id.toLowerCase().includes(q));

    return matchesCat && matchesSearch;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 pr-16">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2.5">
            <LibraryIcon className="h-7 w-7 text-indigo-500" />
            Template Library
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Browse all saved poster design templates, explore placeholder zones, and launch Single or Bulk generation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/add-template")}
            className="py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/20 flex items-center gap-2 transition-all"
          >
            <Plus className="h-4 w-4" />
            <span>Create New Template</span>
          </button>
        </div>
      </div>

      {/* Search & Category Filter Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search templates by category, name, or field tags..."
            className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-sm transition-all"
          />
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
          <button
            onClick={() => setSelectedCategory("all")}
            className={`px-3 py-2 rounded-xl text-xs font-medium transition-all whitespace-nowrap ${
              selectedCategory === "all"
                ? "bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm"
                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:border-slate-400"
            }`}
          >
            All Templates ({allTemplates.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat.folder}
              onClick={() => setSelectedCategory(cat.folder)}
              className={`px-3 py-2 rounded-xl text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${
                selectedCategory === cat.folder
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20"
                  : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:border-slate-400"
              }`}
            >
              <Folder className="h-3.5 w-3.5 opacity-70" />
              <span>{cat.display_name}</span>
              <span className="text-[10px] opacity-60">({cat.templates.length})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Grid Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
          <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
          <p className="text-xs font-medium">Loading Template Library...</p>
        </div>
      ) : filteredTemplates.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <LibraryIcon className="h-12 w-12 text-slate-400 mx-auto stroke-[1.5]" />
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">No templates found</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Try adjusting your search query or select another category tab above.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((t) => (
            <div
              key={`${t.folder}_${t.template_id}`}
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xl hover:shadow-2xl hover:border-indigo-500/50 transition-all flex flex-col group"
            >
              {/* Image Preview Thumbnail */}
              <div className="relative h-56 bg-slate-100 dark:bg-slate-950 overflow-hidden flex items-center justify-center border-b border-slate-200 dark:border-slate-800">
                {/* eslint-disable-next-html-element-suppression */}
                <img
                  src={t.thumbnail_url}
                  alt={t.template_id}
                  className="w-full h-full object-contain p-2 transition-transform duration-300 group-hover:scale-105"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />

                {/* Top Badge */}
                <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-md border border-slate-700/80 text-white text-[10px] px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
                  <Folder className="h-3 w-3 text-indigo-400" />
                  <span>{t.category_display}</span>
                </div>
              </div>

              {/* Body Info */}
              <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-sm text-slate-900 dark:text-white capitalize tracking-tight">
                      {t.template_id.replace(/_/g, " ")}
                    </h3>
                    <span className="text-[10px] font-mono text-slate-400">
                      {t.canvas?.width || 1024} × {t.canvas?.height || 1536}
                    </span>
                  </div>

                  <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">
                    {t.description || "Design poster template with pre-configured layout placeholders."}
                  </p>

                  {/* Layer Tags */}
                  <div className="flex flex-wrap gap-1.5 pt-2">
                    {t.layers.map((layer) => (
                      <span
                        key={layer.id}
                        className={`text-[10px] px-2 py-0.5 rounded-md font-mono border flex items-center gap-1 ${
                          layer.type === "image"
                            ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                            : layer.llm_can_invent
                            ? "bg-purple-500/10 text-purple-500 border-purple-500/20"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700"
                        }`}
                      >
                        <span>{layer.id}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-100 dark:border-slate-800/80">
                  <button
                    onClick={() => router.push(`/generate?folder=${t.folder}&template_id=${t.template_id}`)}
                    className="py-2 px-3 bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-600 hover:text-white text-indigo-600 dark:text-indigo-400 text-xs font-semibold rounded-xl border border-indigo-200 dark:border-indigo-800/60 transition-all flex items-center justify-center gap-1.5"
                  >
                    <ImageIcon className="h-3.5 w-3.5" />
                    <span>Single</span>
                  </button>

                  <button
                    onClick={() => router.push(`/bulk?folder=${t.folder}&template_id=${t.template_id}`)}
                    className="py-2 px-3 bg-emerald-50 dark:bg-emerald-950/50 hover:bg-emerald-600 hover:text-white text-emerald-600 dark:text-emerald-400 text-xs font-semibold rounded-xl border border-emerald-200 dark:border-emerald-800/60 transition-all flex items-center justify-center gap-1.5"
                  >
                    <FileSpreadsheet className="h-3.5 w-3.5" />
                    <span>Bulk Batch</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
