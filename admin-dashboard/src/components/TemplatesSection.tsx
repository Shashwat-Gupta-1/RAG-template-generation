"use client";

import React, { useState } from 'react';
import { Plus, Edit2, Copy, BarChart2, Folder, File, X, Eye, Image as ImageIcon } from 'lucide-react';
import { TemplatePreset } from '../types';

interface TemplatesSectionProps {
  templates: TemplatePreset[];
  liveAdminTemplates?: any[];
  onOpenAddTemplateModal: () => void;
  onEditTemplate: (template: TemplatePreset) => void;
  onDuplicateTemplate: (template: TemplatePreset) => void;
  onViewAnalytics: (template: TemplatePreset) => void;
}

export const TemplatesSection: React.FC<TemplatesSectionProps> = ({
  templates,
  liveAdminTemplates = [],
  onOpenAddTemplateModal,
  onEditTemplate,
  onDuplicateTemplate,
  onViewAnalytics,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [inspectingTemplate, setInspectingTemplate] = useState<any | null>(null);
  const [previewModalImage, setPreviewModalImage] = useState<string | null>(null);

  const categories = ['All', 'Festival', 'Financial & Branch', 'HR & Hiring', 'Corporate'];

  // Combine live scanned templates from templates/ folder with presets
  const displayTemplates = liveAdminTemplates.length > 0 ? liveAdminTemplates : templates;

  const filteredTemplates = displayTemplates.filter((t) => {
    if (selectedCategory === 'All') return true;
    const cat = t.category || 'Festival';
    return cat.toLowerCase() === selectedCategory.toLowerCase();
  });

  return (
    <section className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-[#0D1B3E]">Workspace Templates Explorer</h2>
          <p className="text-xs text-[#45464e] font-medium mt-1">
            Real-time scanner for <code className="bg-[#f5f3f6] px-1.5 py-0.5 rounded text-[#C0392B] font-mono">templates/</code> workspace & cloud storage ({displayTemplates.length} folders loaded)
          </p>
        </div>
        <button
          onClick={onOpenAddTemplateModal}
          className="bg-[#C0392B] text-white flex items-center gap-2 px-6 py-3 rounded-xl text-xs font-bold hover:bg-red-700 shadow-sm transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" /> Add Template Folder
        </button>
      </div>

      {/* Category Tabs */}
      <div className="flex border-b border-[#DDE3EE] overflow-x-auto gap-6 pb-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-3 text-xs font-bold transition-all border-b-2 ${
              selectedCategory === cat
                ? 'border-[#0D1B3E] text-[#0D1B3E]'
                : 'border-transparent text-[#45464e] hover:text-[#0D1B3E]'
            }`}
          >
            {cat === 'All' ? 'All Templates' : cat}
          </button>
        ))}
      </div>

      {/* Template Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredTemplates.map((template) => {
          const title = template.title || template.folder_name;
          const category = template.category || 'Festival';
          const subfolders = template.subfolders || [];
          const tags = template.tags || [category, 'Active Folder'];
          const bannerImage = template.previewImage;

          return (
            <div
              key={template.id || template.folder_name}
              className="bg-white rounded-xl border border-[#DDE3EE] overflow-hidden shadow-sm hover:shadow-md transition-all group flex flex-col justify-between"
            >
              {/* Top Card Banner with PNG Image */}
              <div>
                <div className="relative h-48 bg-[#0D1B3E] overflow-hidden">
                  {bannerImage ? (
                    <img
                      src={bannerImage}
                      alt={title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      onError={(e) => {
                        // Fallback image if local port image isn't available
                        (e.target as HTMLElement).setAttribute('style', 'display: none;');
                      }}
                    />
                  ) : null}

                  {/* Gradient Overlay for Text Readability */}
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0D1B3E] via-[#0D1B3E]/40 to-transparent p-5 flex flex-col justify-between">
                    <div className="flex justify-between items-start">
                      <span className="bg-amber-400 text-[#0D1B3E] text-[10px] px-2.5 py-1 rounded font-bold uppercase shadow-sm">
                        {category}
                      </span>
                      <span className="bg-emerald-500 text-white text-[10px] px-2.5 py-1 rounded font-bold uppercase shadow-sm">
                        ACTIVE
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-amber-200/90 font-mono uppercase tracking-wider block drop-shadow-sm">
                        templates/{template.folder_name || template.id}/
                      </span>
                      <h3 className="text-lg font-bold text-white capitalize leading-tight drop-shadow-md">
                        {title}
                      </h3>
                    </div>
                  </div>
                </div>

                {/* Body Content */}
                <div className="p-6 space-y-4">
                  <div className="flex justify-between items-center text-xs text-[#45464e]">
                    <span className="font-medium">Subfolders & Variants:</span>
                    <span className="font-bold text-[#0D1B3E] bg-[#f5f3f6] px-2 py-1 rounded-md">
                      {subfolders.length} Subfolder(s)
                    </span>
                  </div>

                  {/* Subfolders badges */}
                  {subfolders.length > 0 ? (
                    <div className="space-y-1.5">
                      {subfolders.slice(0, 3).map((sf: any) => (
                        <div
                          key={sf.name}
                          className="flex justify-between items-center text-[11px] bg-[#f5f3f6] px-3 py-1.5 rounded-lg border border-[#DDE3EE]/60"
                        >
                          <span className="font-mono font-medium text-[#0D1B3E] flex items-center gap-1.5">
                            <Folder className="w-3.5 h-3.5 text-[#C0392B]" /> {sf.name}
                          </span>
                          {sf.has_preview ? (
                            <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                              <ImageIcon className="w-3 h-3" /> template.png
                            </span>
                          ) : (
                            <span className="text-gray-400 text-[10px]">{sf.files_count} file(s)</span>
                          )}
                        </div>
                      ))}
                      {subfolders.length > 3 && (
                        <p className="text-[10px] text-[#C0392B] font-bold text-right pt-0.5">
                          +{subfolders.length - 3} more subfolder(s)
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic">No subfolders detected</p>
                  )}

                  {/* Tags */}
                  <div className="flex gap-1.5 flex-wrap pt-1">
                    {tags.map((tag: string) => (
                      <span
                        key={tag}
                        className="bg-[#f5f3f6] text-[#45464e] text-[10px] font-semibold px-2 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="p-4 bg-[#f5f3f6]/50 border-t border-[#DDE3EE] flex items-center justify-between">
                <button
                  onClick={() => setInspectingTemplate(template)}
                  className="w-full bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-2xs cursor-pointer"
                >
                  <Eye className="w-4 h-4 text-amber-300" /> View Subfolder Files & PNG Preview
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Subfolder File Inspection Modal */}
      {inspectingTemplate && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-3xl w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
            <div className="bg-[#0D1B3E] text-white p-5 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Folder className="w-5 h-5 text-amber-300" />
                <div>
                  <h3 className="font-bold text-base capitalize">
                    {inspectingTemplate.title || inspectingTemplate.folder_name}
                  </h3>
                  <p className="text-[11px] text-gray-300 font-mono">
                    templates/{inspectingTemplate.folder_name}/
                  </p>
                </div>
              </div>
              <button
                onClick={() => setInspectingTemplate(null)}
                className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-full transition-all cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
              <h4 className="text-xs font-bold text-[#0D1B3E] uppercase tracking-wider flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-[#C0392B]" /> Subfolder Directories & PNG Template Assets
              </h4>

              {inspectingTemplate.subfolders && inspectingTemplate.subfolders.length > 0 ? (
                <div className="space-y-4">
                  {inspectingTemplate.subfolders.map((sf: any) => (
                    <div
                      key={sf.name}
                      className="bg-[#f5f3f6] p-4 rounded-xl border border-[#DDE3EE] space-y-3"
                    >
                      <div className="flex justify-between items-center border-b border-[#DDE3EE] pb-2">
                        <span className="font-mono font-bold text-xs text-[#0D1B3E] flex items-center gap-1.5">
                          <Folder className="w-4 h-4 text-[#C0392B]" /> templates/{sf.path}
                        </span>
                        <span className="text-[10px] bg-white border border-[#DDE3EE] px-2 py-0.5 rounded font-bold text-gray-700">
                          {sf.files_count} file(s)
                        </span>
                      </div>

                      {/* Display Template PNG Preview if available */}
                      {sf.preview_url && (
                        <div className="bg-white p-3 rounded-lg border border-[#DDE3EE] flex flex-col sm:flex-row items-center gap-4">
                          <img
                            src={sf.preview_url}
                            alt={`${sf.name} template preview`}
                            className="w-32 h-32 object-contain rounded bg-gray-900 border border-gray-200 cursor-pointer hover:scale-105 transition-transform"
                            onClick={() => setPreviewModalImage(sf.preview_url)}
                          />
                          <div className="space-y-1 text-xs text-[#1b1b1e]">
                            <p className="font-bold text-[#0D1B3E] flex items-center gap-1.5">
                              <ImageIcon className="w-4 h-4 text-emerald-600" /> template.png (Asset Preview)
                            </p>
                            <p className="text-gray-500 font-mono text-[11px]">Path: templates/{sf.path}/template.png</p>
                            <button
                              onClick={() => setPreviewModalImage(sf.preview_url)}
                              className="mt-2 text-xs font-bold text-[#C0392B] hover:underline flex items-center gap-1 cursor-pointer"
                            >
                              <Eye className="w-3.5 h-3.5" /> Fullscreen Image View
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="space-y-1">
                        {sf.files.map((file: string) => (
                          <div
                            key={file}
                            className="flex items-center justify-between text-xs py-1 px-2 hover:bg-white rounded transition-colors"
                          >
                            <span className="font-mono text-[#1b1b1e] flex items-center gap-1.5">
                              <File className="w-3.5 h-3.5 text-gray-400" /> {file}
                            </span>
                            <span className="text-[10px] text-gray-500 uppercase font-semibold">
                              {file.split('.').pop()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 bg-gray-50 rounded-xl text-xs text-gray-500 text-center">
                  Direct Files: {inspectingTemplate.direct_files?.join(', ') || 'None'}
                </div>
              )}
            </div>

            <div className="p-4 bg-gray-50 border-t border-[#DDE3EE] flex justify-end">
              <button
                onClick={() => setInspectingTemplate(null)}
                className="px-5 py-2 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl shadow-sm transition-all cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Image Preview Zoom Modal */}
      {previewModalImage && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="relative max-w-4xl max-h-[90vh] p-2">
            <button
              onClick={() => setPreviewModalImage(null)}
              className="absolute -top-10 right-0 text-white bg-white/10 hover:bg-white/20 p-2 rounded-full cursor-pointer"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={previewModalImage}
              alt="Fullscreen Template Preview"
              className="max-h-[80vh] w-auto object-contain rounded-lg shadow-2xl border border-white/20"
            />
          </div>
        </div>
      )}
    </section>
  );
};
