"use client";

import React, { useState } from 'react';
import { LayoutGrid, List, Download, Eye, FileArchive, User } from 'lucide-react';
import { AssetPoster } from '../types';

interface LibrarySectionProps {
  posters: AssetPoster[];
  onSelectPoster: (poster: AssetPoster) => void;
  onDownloadPoster: (poster: AssetPoster) => void;
}

export const LibrarySection: React.FC<LibrarySectionProps> = ({
  posters,
  onSelectPoster,
  onDownloadPoster,
}) => {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [sortBy, setSortBy] = useState<'Newest' | 'Popularity'>('Newest');

  const sortedPosters = [...posters].sort((a, b) => {
    if (sortBy === 'Popularity') return b.downloads - a.downloads;
    return b.id.localeCompare(a.id);
  });

  const FALLBACK_TEMPLATE_IMAGE = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80";

  return (
    <section className="animate-fade-in space-y-6">
      {/* Header Toolbar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-[#0D1B3E]">Asset Library & Output Manager</h2>
          <p className="text-xs text-[#45464e] mt-1 font-medium">
            Viewing {sortedPosters.length} generated poster outputs & bulk export ZIP packages across all templates
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* View Toggle */}
          <div className="flex bg-white border border-[#DDE3EE] rounded-lg p-1 shadow-2xs">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-all cursor-pointer ${
                viewMode === 'grid'
                  ? 'bg-[#eae7eb] text-[#0D1B3E] font-bold shadow-xs'
                  : 'text-[#45464e] hover:bg-[#f5f3f6]'
              }`}
              title="Grid View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all cursor-pointer ${
                viewMode === 'list'
                  ? 'bg-[#eae7eb] text-[#0D1B3E] font-bold shadow-xs'
                  : 'text-[#45464e] hover:bg-[#f5f3f6]'
              }`}
              title="List View"
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          {/* Sort Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'Newest' | 'Popularity')}
            className="bg-white border border-[#DDE3EE] rounded-lg text-xs font-semibold text-[#0D1B3E] px-4 py-2.5 focus:outline-none focus:ring-1 focus:ring-[#0D1B3E] cursor-pointer"
          >
            <option value="Newest">Newest Uploads</option>
            <option value="Popularity">User Popularity</option>
          </select>
        </div>
      </div>

      {/* Grid or List Display */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
          {sortedPosters.map((poster) => (
            <div
              key={poster.id}
              onClick={() => onSelectPoster(poster)}
              className="bg-white rounded-xl border border-[#DDE3EE] overflow-hidden flex flex-col justify-between group hover:border-[#0D1B3E] transition-all shadow-sm cursor-pointer"
            >
              {/* Image Preview / Bulk Badge */}
              <div className="relative aspect-[3/4] overflow-hidden bg-[#0D1B3E] flex items-center justify-center">
                <img
                  src={poster.imageUrl || FALLBACK_TEMPLATE_IMAGE}
                  alt={poster.dataAlt}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    if (target.src !== FALLBACK_TEMPLATE_IMAGE) {
                      target.src = FALLBACK_TEMPLATE_IMAGE;
                    }
                  }}
                />

                {/* Bulk ZIP Badge */}
                {poster.isBulk && (
                  <div className="absolute top-2 left-2 bg-[#0D1B3E]/90 backdrop-blur-md text-amber-300 text-[10px] font-bold px-2 py-1 rounded flex items-center gap-1 border border-amber-400/30">
                    <FileArchive className="w-3 h-3" /> BULK ZIP ({poster.totalPostersInBulk || 1} posters)
                  </div>
                )}

                {/* Hover Action Overlay */}
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-3 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDownloadPoster(poster);
                    }}
                    className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#0D1B3E] hover:bg-slate-100 shadow-md transition-all cursor-pointer"
                    title={poster.isBulk ? "Download Bulk ZIP Package" : "Download Poster"}
                  >
                    <Download className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => onSelectPoster(poster)}
                    className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#0D1B3E] hover:bg-slate-100 shadow-md transition-all cursor-pointer"
                    title="View Output Details"
                  >
                    <Eye className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Title & Author Info */}
              <div className="p-3.5 space-y-1">
                <p className="text-xs font-bold text-[#1b1b1e] truncate" title={poster.filename}>
                  {poster.filename}
                </p>
                <div className="flex justify-between items-center text-[10px] text-[#45464e]">
                  <span className="font-semibold text-[#0D1B3E] flex items-center gap-1">
                    <User className="w-3 h-3 text-[#C0392B]" /> {poster.author}
                  </span>
                  <span>{poster.timeAgo}</span>
                </div>
                {poster.authorEmail && (
                  <p className="text-[10px] text-gray-400 truncate">{poster.authorEmail}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* List View */
        <div className="space-y-3">
          {sortedPosters.map((poster) => (
            <div
              key={poster.id}
              className="bg-white rounded-xl border border-[#DDE3EE] p-4 flex items-center justify-between hover:border-[#0D1B3E] transition-all shadow-sm"
            >
              <div className="flex items-center gap-4">
                <div className="relative w-16 h-20 bg-[#0D1B3E] rounded-lg overflow-hidden flex items-center justify-center flex-shrink-0 border border-[#DDE3EE]">
                  <img
                    src={poster.imageUrl || FALLBACK_TEMPLATE_IMAGE}
                    alt={poster.dataAlt}
                    className="w-full h-full object-cover cursor-pointer"
                    onClick={() => onSelectPoster(poster)}
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      if (target.src !== FALLBACK_TEMPLATE_IMAGE) {
                        target.src = FALLBACK_TEMPLATE_IMAGE;
                      }
                    }}
                  />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-[#0D1B3E]">{poster.filename}</h4>
                    {poster.isBulk && (
                      <span className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded font-bold">
                        ZIP BULK ({poster.totalPostersInBulk} posters)
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#45464e] mt-1 font-medium">
                    Generated by: <b className="text-[#0D1B3E]">{poster.author}</b> ({poster.authorEmail || 'User'}) • {poster.timeAgo}
                  </p>
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    Template: <b>{poster.templateFolder || 'Standard Preset'}</b> • Downloads: {poster.downloads}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => onSelectPoster(poster)}
                  className="px-4 py-2 bg-[#f5f3f6] hover:bg-[#eae7eb] text-[#0D1B3E] text-xs font-bold rounded-lg transition-all cursor-pointer"
                >
                  View Details
                </button>
                <button
                  onClick={() => onDownloadPoster(poster)}
                  className="p-2.5 bg-[#0D1B3E] text-white hover:bg-[#1E3A6E] rounded-lg transition-all cursor-pointer flex items-center gap-1.5 text-xs font-bold"
                  title="Download File"
                >
                  <Download className="w-4 h-4" /> {poster.isBulk ? 'ZIP' : 'Download'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
