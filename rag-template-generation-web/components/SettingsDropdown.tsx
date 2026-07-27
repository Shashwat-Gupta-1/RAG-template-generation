"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Settings, Library, LayoutGrid, Wand2, History } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function SettingsDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative w-full text-left z-50" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        type="button"
        className={`w-full py-2 px-3 rounded-lg border transition-all flex items-center justify-center gap-2 shadow-sm ${
          isOpen
            ? "bg-indigo-600 text-white border-indigo-500 shadow-indigo-500/20"
            : "bg-slate-100 dark:bg-slate-800/50 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
        }`}
        aria-expanded={isOpen}
        aria-label="Settings"
      >
        <Settings className={`h-4 w-4 transition-transform duration-300 ${isOpen ? "rotate-90" : ""}`} />
        <span className="text-xs font-medium">Settings</span>
      </button>

      {isOpen && (
        <div className="origin-bottom-left absolute bottom-full left-0 mb-2 w-full rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl z-50 p-2 space-y-1 animate-in fade-in zoom-in-95 duration-150">
          <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800/80 mb-1">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Quick Menu & Settings
            </p>
          </div>

          <button
            onClick={() => {
              setIsOpen(false);
              router.push("/history");
            }}
            className="w-full text-left px-3 py-2.5 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-blue-50 dark:hover:bg-blue-950/40 hover:text-blue-600 dark:hover:text-blue-400 transition-all flex items-center gap-2.5 group"
          >
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500 group-hover:bg-blue-500 group-hover:text-white transition-colors">
              <History className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold">User History</span>
              <span className="text-[10px] text-slate-400 font-normal">View past generations</span>
            </div>
          </button>

          <button
            onClick={() => {
              setIsOpen(false);
              router.push("/library");
            }}
            className="w-full text-left px-3 py-2.5 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all flex items-center gap-2.5 group"
          >
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 group-hover:bg-indigo-500 group-hover:text-white transition-colors">
              <Library className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold">Library</span>
              <span className="text-[10px] text-slate-400 font-normal">Browse all template collections</span>
            </div>
          </button>

          <button
            onClick={() => {
              setIsOpen(false);
              router.push("/add-template");
            }}
            className="w-full text-left px-3 py-2.5 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 hover:text-emerald-600 dark:hover:text-emerald-400 transition-all flex items-center gap-2.5 group"
          >
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
              <LayoutGrid className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold">Save Templates</span>
              <span className="text-[10px] text-slate-400 font-normal">Save template manually</span>
            </div>
          </button>

          <button
            onClick={() => {
              setIsOpen(false);
              router.push("/create-template");
            }}
            className="w-full text-left px-3 py-2.5 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-purple-50 dark:hover:bg-purple-950/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all flex items-center gap-2.5 group"
          >
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-500 group-hover:bg-purple-500 group-hover:text-white transition-colors">
              <Wand2 className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold">AI Template Agent</span>
              <span className="text-[10px] text-slate-400 font-normal">Generate template via AI</span>
            </div>
          </button>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between px-3 py-1.5">
            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Theme</span>
            <ThemeToggle />
          </div>
        </div>
      )}
    </div>
  );
}
