"use client";

import React, { useState } from 'react';
import { Search, Bell, HelpCircle, X, Check } from 'lucide-react';
import { ADMIN_USER } from '../data/mockData';

interface HeaderProps {
  pageTitle: string;
  globalSearchQuery: string;
  onSearchChange: (query: string) => void;
  onOpenProfile: () => void;
  onQuickGenerate: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  pageTitle,
  globalSearchQuery,
  onSearchChange,
  onOpenProfile,
  onQuickGenerate,
}) => {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState([
    { id: 'n1', title: 'Bulk Job #8921 Complete', time: '10m ago', read: false },
    { id: 'n2', title: 'New Template "Independence Day" Active', time: '1h ago', read: false },
    { id: 'n3', title: 'System Security Check Passed', time: '3h ago', read: true },
  ]);

  const markAllRead = () => {
    setUnreadNotifications(unreadNotifications.map(n => ({ ...n, read: true })));
  };

  const hasUnread = unreadNotifications.some(n => !n.read);

  return (
    <header className="fixed top-0 right-0 w-[calc(100%-260px)] h-16 bg-white border-b border-[#DDE3EE] flex justify-between items-center px-8 z-40 select-none">
      {/* Title */}
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold text-[#0D1B3E] font-poppins">{pageTitle}</h1>
        <button
          onClick={onQuickGenerate}
          className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-[#0D1B3E] hover:bg-[#1E3A6E] text-white text-xs font-semibold rounded-full shadow-sm transition-all"
        >
          <span className="text-amber-300">✦</span> AI Quick Copy
        </button>
      </div>

      {/* Header Utilities */}
      <div className="flex items-center gap-6">

        {/* Action Icons */}
        <div className="flex items-center gap-2 relative">
          {/* Bell Notifications */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-[#eae7eb] transition-all text-[#45464e] relative"
              title="Notifications"
            >
              <Bell className="w-5 h-5" />
              {hasUnread && (
                <span className="absolute top-2 right-2 w-2 h-2 bg-[#C0392B] rounded-full ring-2 ring-white"></span>
              )}
            </button>

            {/* Notifications Dropdown */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-[#DDE3EE] rounded-xl shadow-xl z-50 p-4 animate-fade-in">
                <div className="flex justify-between items-center mb-3 pb-2 border-b border-[#DDE3EE]">
                  <h3 className="font-bold text-sm text-[#0D1B3E]">Notifications</h3>
                  <button
                    onClick={markAllRead}
                    className="text-xs text-[#1E3A6E] hover:underline flex items-center gap-1 font-medium"
                  >
                    <Check className="w-3 h-3" /> Mark read
                  </button>
                </div>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {unreadNotifications.map((n) => (
                    <div
                      key={n.id}
                      className={`p-2.5 rounded-lg text-xs flex justify-between items-start ${
                        n.read ? 'bg-gray-50 text-gray-600' : 'bg-blue-50 text-[#0D1B3E] font-medium'
                      }`}
                    >
                      <div>
                        <p>{n.title}</p>
                        <span className="text-[10px] text-gray-400 mt-0.5 block">{n.time}</span>
                      </div>
                      {!n.read && <span className="w-1.5 h-1.5 bg-blue-600 rounded-full mt-1"></span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Help Button */}
          <div className="relative">
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-[#eae7eb] transition-all text-[#45464e]"
              title="System Documentation & Help"
            >
              <HelpCircle className="w-5 h-5" />
            </button>

            {showHelp && (
              <div className="absolute right-0 mt-2 w-80 bg-white border border-[#DDE3EE] rounded-xl shadow-xl z-50 p-4 animate-fade-in">
                <h3 className="font-bold text-sm text-[#0D1B3E] mb-2">MS Fincap Admin Guide</h3>
                <p className="text-xs text-gray-600 leading-relaxed mb-3">
                  This dashboard manages AI poster rendering pipelines, user directory logs, and template presets for retail financial marketing.
                </p>
                <div className="text-[11px] bg-slate-100 p-2.5 rounded text-slate-700 space-y-1">
                  <p>• <b>Dashboard:</b> Operational stats & bulk queues</p>
                  <p>• <b>User Directory:</b> Individual output & scores</p>
                  <p>• <b>Logs:</b> Compliance audit & chat records</p>
                  <p>• <b>Library:</b> Download & export generated media</p>
                </div>
              </div>
            )}
          </div>

          <div className="h-8 w-[1px] bg-[#DDE3EE] mx-1"></div>

          {/* User Profile */}
          <div
            onClick={onOpenProfile}
            className="flex items-center gap-3 cursor-pointer group hover:bg-[#f5f3f6] p-1.5 rounded-full transition-all"
          >
            <div className="text-right hidden sm:block">
              <p className="text-xs font-bold text-[#0D1B3E] leading-none">{ADMIN_USER.name}</p>
              <p className="text-[10px] text-[#45464e] font-medium mt-0.5">{ADMIN_USER.role}</p>
            </div>
            <img
              src={ADMIN_USER.avatar}
              alt={ADMIN_USER.name}
              className="w-10 h-10 rounded-full border border-[#DDE3EE] group-hover:border-[#C0392B] transition-all object-cover"
            />
          </div>
        </div>
      </div>
    </header>
  );
};
