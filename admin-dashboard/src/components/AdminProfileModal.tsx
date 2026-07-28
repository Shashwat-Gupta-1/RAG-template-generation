"use client";

import React from 'react';
import { X, ShieldCheck, Key, UserCheck, Activity, Lock } from 'lucide-react';
import { ADMIN_USER } from '../data/mockData';

interface AdminProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminProfileModal: React.FC<AdminProfileModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-xl w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        <div className="bg-[#0D1B3E] text-white p-6 relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-full transition-all"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-5">
            <img
              src={ADMIN_USER.avatar}
              alt={ADMIN_USER.name}
              className="w-20 h-20 rounded-full border-4 border-white object-cover shadow-md"
            />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-bold">{ADMIN_USER.name}</h3>
                <span className="bg-emerald-500/20 text-emerald-300 text-[10px] px-2 py-0.5 rounded-md font-bold border border-emerald-400/30 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> System SuperAdmin
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-1 font-medium">{ADMIN_USER.role}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">{ADMIN_USER.email}</p>
            </div>
          </div>
        </div>

        <div className="p-6 text-xs text-[#1b1b1e]">
          <div className="bg-[#f5f3f6] p-4 rounded-xl border border-[#DDE3EE] flex justify-between items-center">
            <div>
              <p className="uppercase text-[10px] text-gray-500 font-bold">System Status</p>
              <p className="font-bold text-green-600 mt-0.5">Active Admin Session</p>
            </div>
            <div className="text-right">
              <p className="uppercase text-[10px] text-gray-500 font-bold">Last Login</p>
              <p className="font-bold text-[#0D1B3E] mt-0.5">{ADMIN_USER.lastLogin}</p>
            </div>
          </div>
        </div>

        <div className="p-4 bg-gray-50 border-t border-[#DDE3EE] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
