"use client";

import React, { useState } from 'react';
import { X, Settings, Sliders, Database, Check } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [modelQuality, setModelQuality] = useState('High');
  const [autoFlagging, setAutoFlagging] = useState(true);
  const [contrastEnforcement, setContrastEnforcement] = useState(true);
  const [saved, setSaved] = useState(false);

  if (!isOpen) return null;

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-lg w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        <div className="bg-[#0D1B3E] text-white p-5 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-amber-300" />
            <h3 className="font-bold text-base">System Settings & AI Controls</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-full transition-all text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-xs text-[#1b1b1e]">
          <div>
            <label className="font-bold text-[#0D1B3E] block mb-1">Rendering Quality Model</label>
            <select
              value={modelQuality}
              onChange={(e) => setModelQuality(e.target.value)}
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-semibold"
            >
              <option value="High">High Precision (Gemini 3.6 Flash)</option>
              <option value="Balanced">Balanced (Standard Speed)</option>
              <option value="Fast">Fast Draft Mode</option>
            </select>
          </div>

          <div className="space-y-3 pt-2 border-t border-[#DDE3EE]">
            <h4 className="font-bold text-[#0D1B3E] flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-[#1E3A6E]" /> Compliance & Brand Rules
            </h4>

            <label className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-[#DDE3EE] cursor-pointer">
              <div>
                <p className="font-bold text-[#0D1B3E]">Automatic Log Flagging</p>
                <p className="text-[11px] text-gray-500">Flag interaction sessions with logo padding or contrast queries.</p>
              </div>
              <input
                type="checkbox"
                checked={autoFlagging}
                onChange={(e) => setAutoFlagging(e.target.checked)}
                className="w-4 h-4 text-[#0D1B3E] rounded focus:ring-0"
              />
            </label>

            <label className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-[#DDE3EE] cursor-pointer">
              <div>
                <p className="font-bold text-[#0D1B3E]">WCAG AAA Contrast Enforcement</p>
                <p className="text-[11px] text-gray-500">Enforce minimum 7:1 contrast on all navy/white poster typography.</p>
              </div>
              <input
                type="checkbox"
                checked={contrastEnforcement}
                onChange={(e) => setContrastEnforcement(e.target.checked)}
                className="w-4 h-4 text-[#0D1B3E] rounded focus:ring-0"
              />
            </label>
          </div>

          <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 text-[11px]">
            <p className="font-bold">Server Proxy Ingestion</p>
            <p className="mt-0.5">All requests bind to port 3000 via Express & Vite server routing.</p>
          </div>
        </div>

        <div className="p-4 bg-gray-50 border-t border-[#DDE3EE] flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-gray-800">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2.5 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
          >
            {saved ? <Check className="w-4 h-4 text-green-400" /> : null}
            {saved ? 'Saved!' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
