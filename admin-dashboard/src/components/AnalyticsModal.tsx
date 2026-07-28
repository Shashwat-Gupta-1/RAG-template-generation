"use client";

import React from 'react';
import { X, BarChart2, TrendingUp, Users, CheckCircle } from 'lucide-react';
import { TemplatePreset } from '../types';

interface AnalyticsModalProps {
  template: TemplatePreset | null;
  onClose: () => void;
}

export const AnalyticsModal: React.FC<AnalyticsModalProps> = ({ template, onClose }) => {
  if (!template) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-lg w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        <div className="bg-[#0D1B3E] text-white p-5 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-amber-300" />
            <h3 className="font-bold text-base">Template Analytics - {template.title}</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-full transition-all text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-xs text-[#1b1b1e]">
          <div className="grid grid-cols-3 gap-3 bg-[#f5f3f6] p-4 rounded-xl text-center">
            <div>
              <p className="uppercase text-[10px] text-gray-500 font-bold">Total Uses</p>
              <p className="text-xl font-bold text-[#0D1B3E] mt-0.5">{template.uses}</p>
            </div>
            <div>
              <p className="uppercase text-[10px] text-gray-500 font-bold">Conversion Rate</p>
              <p className="text-xl font-bold text-green-700 mt-0.5">94.2%</p>
            </div>
            <div>
              <p className="uppercase text-[10px] text-gray-500 font-bold">Version</p>
              <p className="text-xl font-bold text-[#0D1B3E] mt-0.5">{template.version}</p>
            </div>
          </div>

          <div className="border border-[#DDE3EE] rounded-xl p-4 space-y-3">
            <h4 className="font-bold text-[#0D1B3E] flex items-center gap-1.5 text-sm">
              <TrendingUp className="w-4 h-4 text-[#C0392B]" /> Generation Velocity (Last 7 Days)
            </h4>

            <div className="space-y-2">
              {[
                { day: 'Mon', count: 6400 },
                { day: 'Tue', count: 7100 },
                { day: 'Wed', count: 8300 },
                { day: 'Thu', count: 9200 },
                { day: 'Fri', count: 11400 },
              ].map((item) => (
                <div key={item.day} className="flex items-center gap-3">
                  <span className="w-8 font-bold text-gray-500">{item.day}</span>
                  <div className="flex-1 bg-gray-100 h-3 rounded-full overflow-hidden">
                    <div
                      className="bg-[#0D1B3E] h-full rounded-full"
                      style={{ width: `${(item.count / 12000) * 100}%` }}
                    ></div>
                  </div>
                  <span className="w-12 text-right font-bold text-[#0D1B3E]">
                    {item.count.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-xl text-emerald-900 text-[11px] flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Optimal performance rating. High click-through on retail banking media.</span>
          </div>
        </div>

        <div className="p-4 bg-gray-50 border-t border-[#DDE3EE] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl transition-all"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
