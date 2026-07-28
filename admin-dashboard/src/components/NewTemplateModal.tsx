"use client";

import React, { useState } from 'react';
import { X, Save, Layers } from 'lucide-react';
import { TemplatePreset } from '../types';

interface NewTemplateModalProps {
  isOpen: boolean;
  editingTemplate?: TemplatePreset | null;
  onClose: () => void;
  onSave: (template: TemplatePreset) => void;
}

export const NewTemplateModal: React.FC<NewTemplateModalProps> = ({
  isOpen,
  editingTemplate,
  onClose,
  onSave,
}) => {
  const [title, setTitle] = useState(editingTemplate?.title || '');
  const [category, setCategory] = useState<string>(
    editingTemplate?.category || 'Festival'
  );
  const [description, setDescription] = useState(editingTemplate?.description || '');
  const [defaultPrompt, setDefaultPrompt] = useState(
    editingTemplate?.defaultPrompt || 'Generate poster with high contrast navy and tricolor branding.'
  );

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newTmpl: TemplatePreset = {
      id: editingTemplate?.id || `tmpl-${Date.now()}`,
      title: title || 'New Preset Template',
      category,
      status: 'ACTIVE',
      description: description || 'Custom AI rendering preset.',
      uses: editingTemplate?.uses || '0',
      version: editingTemplate?.version || 'v1.0',
      tags: ['#New', `#${category}`],
      previewImage:
        editingTemplate?.previewImage ||
        'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=600&q=80',
      dataAlt: description || title,
      defaultPrompt,
    };
    onSave(newTmpl);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-lg w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        <div className="bg-[#0D1B3E] text-white p-5 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-amber-300" />
            <h3 className="font-bold text-base">
              {editingTemplate ? 'Edit Template Preset' : 'Create New Template Preset'}
            </h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-full transition-all text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Template Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Festival Freedom Special"
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as any)}
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            >
              <option value="Festival">Festival</option>
              <option value="Planning">Planning</option>
              <option value="HR">HR & Corporate</option>
              <option value="Emergency">Emergency</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Multi-festival adaptive model with corporate color tokens."
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Default AI System Directive</label>
            <textarea
              rows={3}
              value={defaultPrompt}
              onChange={(e) => setDefaultPrompt(e.target.value)}
              placeholder="Instructions for Gemini model rendering pipeline..."
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            />
          </div>

          <div className="pt-4 border-t border-[#DDE3EE] flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center gap-1.5"
            >
              <Save className="w-4 h-4" /> Save Preset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
