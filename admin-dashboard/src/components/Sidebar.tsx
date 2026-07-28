"use client";

import React from 'react';
import { NavigationSection } from '../types';
import {
  LayoutDashboard,
  UserSearch,
  MessageSquare,
  Library,
  FileText,
  UserCircle,
  Settings,
} from 'lucide-react';

interface SidebarProps {
  activeSection: NavigationSection;
  onSectionChange: (section: NavigationSection) => void;
  onOpenProfile: () => void;
  onOpenSettings: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSectionChange,
  onOpenProfile,
  onOpenSettings,
}) => {
  const navItems = [
    { id: 'dashboard' as NavigationSection, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'search-user' as NavigationSection, label: 'Search by User', icon: UserSearch },
    { id: 'logs' as NavigationSection, label: 'Conversation Logs', icon: MessageSquare },
    { id: 'library' as NavigationSection, label: 'Library', icon: Library },
    { id: 'templates' as NavigationSection, label: 'Templates', icon: FileText },
  ];

  return (
    <aside className="fixed left-0 top-0 h-screen w-[260px] bg-[#0D1B3E] flex flex-col py-6 px-4 z-50 text-white select-none">
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-2 mb-8 cursor-pointer group" onClick={() => onSectionChange('dashboard')}>
        <img
          src="/logo.png"
          alt="MS Fincap Logo"
          className="h-10 w-auto object-contain rounded-lg bg-white/10 p-1 border border-white/10 group-hover:scale-105 transition-transform"
          onError={(e) => {
            (e.target as HTMLImageElement).src = "http://localhost:8000/brand/logo.png";
          }}
        />
        <div className="flex flex-col">
          <span className="text-white font-bold tracking-wider leading-none text-base group-hover:text-amber-300 transition-colors">FINCAP</span>
          <span className="text-[#7784ad] text-[10px] uppercase font-bold tracking-widest opacity-80 mt-0.5">
            AI Intelligence
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSectionChange(item.id)}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-lg text-sm transition-all text-left ${
                isActive
                  ? 'bg-[#1E3A6E] border-l-4 border-[#C0392B] font-semibold text-white shadow-sm'
                  : 'text-[#f5f3f6] hover:bg-white/10 opacity-85 hover:opacity-100'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-[#C0392B]' : 'text-[#c6c6cf]'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom Profile & Settings */}
      <div className="pt-6 border-t border-white/10 space-y-2">
        <button
          onClick={onOpenProfile}
          className={`w-full flex items-center gap-4 px-4 py-3 rounded-lg text-sm text-[#f5f3f6] hover:bg-white/10 transition-all text-left ${
            activeSection === 'profile' ? 'bg-[#1E3A6E] font-semibold text-white' : ''
          }`}
        >
          <UserCircle className="w-5 h-5 text-[#c6c6cf]" />
          <span>Admin Profile</span>
        </button>
        <button
          onClick={onOpenSettings}
          className={`w-full flex items-center gap-4 px-4 py-3 rounded-lg text-sm text-[#f5f3f6] hover:bg-white/10 transition-all text-left ${
            activeSection === 'settings' ? 'bg-[#1E3A6E] font-semibold text-white' : ''
          }`}
        >
          <Settings className="w-5 h-5 text-[#c6c6cf]" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
};
