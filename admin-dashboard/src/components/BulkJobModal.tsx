"use client";

import React, { useState } from 'react';
import { X, Layers, Play } from 'lucide-react';
import { BulkJob } from '../types';

interface BulkJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onScheduleJob: (job: BulkJob) => void;
}

export const BulkJobModal: React.FC<BulkJobModalProps> = ({
  isOpen,
  onClose,
  onScheduleJob,
}) => {
  const [userName, setUserName] = useState('Rahul K.');
  const [template, setTemplate] = useState('Festival Wish');
  const [quantity, setQuantity] = useState(500);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newJob: BulkJob = {
      id: `#89${Math.floor(10 + Math.random() * 89)}`,
      user: userName,
      status: 'QUEUED',
      postersGenerated: quantity,
      template,
      startedAt: 'Just now',
    };
    onScheduleJob(newJob);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-md w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        <div className="bg-[#0D1B3E] text-white p-5 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-amber-300" />
            <h3 className="font-bold text-base">Schedule New Bulk Job</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-full transition-all text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Target User / Operator</label>
            <input
              type="text"
              required
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Target Template</label>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="w-full bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-[#0D1B3E] outline-none"
            >
              <option value="Festival Wish">Festival Wish (42.3k uses)</option>
              <option value="Investment Plan">Investment Plan (38.1k uses)</option>
              <option value="HR Updates">HR Updates (29.8k uses)</option>
              <option value="Loan Calculator">Loan Calculator (15.4k uses)</option>
              <option value="Stock Insights">Stock Insights (12.9k uses)</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-bold text-[#0D1B3E] block mb-1">Batch Poster Quantity</label>
            <input
              type="number"
              min={10}
              max={10000}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
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
              className="px-5 py-2.5 bg-[#C0392B] hover:bg-red-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-white" /> Start Batch Job
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
