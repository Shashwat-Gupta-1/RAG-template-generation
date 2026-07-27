import React, { useState } from "react";
import { Check, X, Eye } from "lucide-react";

export interface Template {
  template_id: string;
  description: string;
  [key: string]: any;
}

interface TemplateSelectionListProps {
  templates: Template[];
  folder: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  themeColor: "indigo" | "emerald";
  actionText: string;
  twoColumn?: boolean;
}

export default function TemplateSelectionList({
  templates,
  folder,
  selectedId,
  onSelect,
  themeColor,
  actionText,
  twoColumn = false,
}: TemplateSelectionListProps) {
  const [previewId, setPreviewId] = useState<string | null>(null);

  // Theme color mapping
  const colorMap = {
    indigo: {
      borderSelected: "border-indigo-500",
      bgSelected: "bg-indigo-50 dark:bg-indigo-900/20",
      button: "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-600/20",
      buttonText: "text-white",
      ring: "ring-indigo-500/20"
    },
    emerald: {
      borderSelected: "border-emerald-500",
      bgSelected: "bg-emerald-50 dark:bg-emerald-900/20",
      button: "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-600/20",
      buttonText: "text-white",
      ring: "ring-emerald-500/20"
    },
  };

  const theme = colorMap[themeColor];

  if (!templates || templates.length === 0) {
    return null;
  }

  return (
    <div className={twoColumn ? "grid grid-cols-1 xl:grid-cols-2 gap-4" : "space-y-0"}>
      {templates.map((t, index) => {
        const isSelected = selectedId === t.template_id;
        const thumbUrl = folder
          ? `/api/proxy/template-thumbnail/${folder}/${t.template_id}`
          : "";

        return (
          <div key={t.template_id} className="relative group w-full max-w-full">
            <div
              onClick={() => onSelect(t.template_id)}
              className={`w-full max-w-full flex flex-col sm:flex-row gap-4 p-4 rounded-xl border transition-all cursor-pointer box-border ${
                isSelected
                  ? `${theme.borderSelected} ${theme.bgSelected} ring-2 ${theme.ring}`
                  : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 shadow-sm hover:shadow-md"
              }`}
            >
              {/* Left Column (Info) */}
              <div className="flex-1 min-w-0 flex flex-col justify-between space-y-3">
                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 dark:text-white capitalize text-sm">
                    {t.template_id.replace(/_/g, " ")}
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-normal leading-relaxed line-clamp-3">
                    {t.description}
                  </p>
                </div>
                
                <div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(t.template_id);
                    }}
                    className={`px-4 py-2 rounded-full text-xs font-semibold shadow-sm transition-all ${theme.button}`}
                  >
                    <span className="flex items-center gap-1.5">
                      {isSelected && <Check className="h-3.5 w-3.5" />}
                      {actionText}
                    </span>
                  </button>
                </div>
              </div>

              {/* Right Column (Preview Thumbnail) */}
              <div className="w-[120px] max-w-[30%] sm:w-[140px] shrink-0 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-950 relative aspect-[3/4]">
                <img
                  src={thumbUrl}
                  alt={t.template_id}
                  className="w-full h-full max-w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
                
                {/* Enlarge Eye Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPreviewId(t.template_id);
                  }}
                  className="absolute top-2 right-2 bg-black/60 hover:bg-black/90 text-white rounded-full w-7 h-7 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 text-sm shadow-sm"
                  title="Enlarge poster"
                >
                  <Eye className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            {/* Divider (except for last item) */}
            {!twoColumn && index < templates.length - 1 && (
              <hr className="my-4 border-slate-200 dark:border-slate-800" />
            )}
          </div>
        );
      })}

      {/* Enlarge Preview Modal */}
      {previewId && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
          onClick={() => setPreviewId(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            <button 
              className="absolute -top-12 right-0 bg-white/20 hover:bg-white/40 text-white rounded-full p-2 transition-colors"
              onClick={() => setPreviewId(null)}
              title="Close preview"
            >
              <X className="w-6 h-6" />
            </button>
            <img 
              src={folder ? `/api/proxy/template-thumbnail/${folder}/${previewId}` : ""} 
              alt={previewId}
              className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl bg-black/50"
            />
          </div>
        </div>
      )}
    </div>
  );
}
