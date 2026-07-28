"use client";

import React from 'react';
import { X, Calendar, Mail, Building2, FileText, Award, Shield } from 'lucide-react';
import { UserProfile, AssetPoster } from '../types';

interface UserProfileModalProps {
  user: UserProfile | null;
  userPosters: AssetPoster[];
  onClose: () => void;
  onSelectPoster: (poster: AssetPoster) => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  user,
  userPosters,
  onClose,
  onSelectPoster,
}) => {
  if (!user) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-3xl w-full border border-[#DDE3EE] shadow-2xl overflow-hidden animate-fade-in my-8">
        {/* Modal Header Banner */}
        <div className="bg-gradient-to-r from-[#0D1B3E] to-[#1E3A6E] p-6 text-white relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-full transition-all"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex flex-col sm:flex-row items-center gap-6">
            <img
              src={user.avatar}
              alt={user.name}
              className="w-20 h-20 rounded-full border-4 border-white object-cover shadow-lg"
            />
            <div className="text-center sm:text-left">
              <div className="flex items-center gap-3 justify-center sm:justify-start">
                <h3 className="text-2xl font-bold">{user.name}</h3>
                <span className="bg-green-500/20 text-green-300 text-xs px-2.5 py-0.5 rounded-full border border-green-400/30 font-semibold">
                  {user.status}
                </span>
              </div>
              <p className="text-sm text-slate-300 mt-1 font-medium">{user.role}</p>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 mt-3">
                <span className="flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-amber-300" /> {user.email}
                </span>
                <span className="flex items-center gap-1">
                  <Building2 className="w-3.5 h-3.5 text-amber-300" /> {user.department}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          {/* Stats Bar */}
          <div className="grid grid-cols-2 gap-4 bg-[#f5f3f6] p-4 rounded-xl text-center">
            <div>
              <p className="text-xs uppercase text-[#45464e] font-semibold">Total Generated</p>
              <p className="text-2xl font-bold text-[#0D1B3E] mt-1">{Math.max(user.postersCount, userPosters.length).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-[#45464e] font-semibold">Member Since</p>
              <p className="text-2xl font-bold text-[#0D1B3E] mt-1">{user.memberSince}</p>
            </div>
          </div>

          {/* User Bio & Details */}
          {user.bio && (
            <div>
              <h4 className="text-xs uppercase font-bold text-[#45464e] mb-2 tracking-wider">
                Member Profile Overview
              </h4>
              <p className="text-sm text-[#1b1b1e] leading-relaxed bg-slate-50 p-4 rounded-xl border border-[#DDE3EE]">
                {user.bio}
              </p>
            </div>
          )}

          {/* Generated Posters Gallery */}
          <div>
            <h4 className="text-xs uppercase font-bold text-[#45464e] mb-3 tracking-wider flex items-center justify-between">
              <span>Recent Output Media ({userPosters.length})</span>
              <span className="text-[11px] text-[#1E3A6E] font-semibold">Click to preview</span>
            </h4>

            {userPosters.length > 0 ? (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                {userPosters.map((poster) => (
                  <div
                    key={poster.id}
                    onClick={() => onSelectPoster(poster)}
                    className="relative aspect-[9/16] rounded-lg overflow-hidden border border-[#DDE3EE] cursor-pointer hover:border-[#0D1B3E] transition-all group shadow-2xs"
                  >
                    <img
                      src={poster.imageUrl}
                      alt={poster.filename}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-xs font-bold transition-opacity">
                      Preview
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500 italic p-4 bg-gray-50 rounded-xl">
                No recent posters cataloged in current cache for this member.
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-gray-50 border-t border-[#DDE3EE] flex justify-between items-center">
          <span className="text-xs text-gray-500">User ID: {user.id}</span>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-bold rounded-xl transition-all cursor-pointer"
          >
            Close Profile
          </button>
        </div>
      </div>
    </div>
  );
};
