"use client";

import React, { useState } from 'react';
import { Search, Filter, UserCheck } from 'lucide-react';
import { UserProfile } from '../types';

interface SearchUserSectionProps {
  users: UserProfile[];
  onSelectUser: (user: UserProfile) => void;
}

export const SearchUserSection: React.FC<SearchUserSectionProps> = ({
  users,
  onSelectUser,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('All');

  const departments = ['All', 'Retail Marketing', 'Digital Operations', 'Investment Services', 'Creative Strategy', 'Human Resources', 'Research & Analytics'];

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.role.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.id.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesDept = departmentFilter === 'All' || u.department === departmentFilter;

    return matchesSearch && matchesDept;
  });

  return (
    <section className="animate-fade-in space-y-6">
      {/* Search Header Bar */}
      <div className="bg-white rounded-xl border border-[#DDE3EE] p-6 shadow-sm">
        <h2 className="text-xl font-bold text-[#0D1B3E] mb-4">User Directory</h2>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[#76767f]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, email, or user ID..."
              className="w-full pl-12 pr-4 py-3 bg-[#f5f3f6] border border-[#DDE3EE] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0D1B3E] focus:bg-white transition-all text-[#1b1b1e]"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-[#45464e]" />
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="bg-[#f5f3f6] border border-[#DDE3EE] text-xs font-medium text-[#0D1B3E] rounded-lg px-3 py-3 focus:outline-none focus:ring-2 focus:ring-[#0D1B3E]"
            >
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d === 'All' ? 'All Departments' : d}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* User Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredUsers.map((user) => (
          <div
            key={user.id}
            className="bg-white rounded-xl border border-[#DDE3EE] p-6 hover:border-[#0D1B3E] transition-all group shadow-sm flex flex-col justify-between"
          >
            <div>
              {/* User Header */}
              <div className="flex items-center gap-4 mb-6">
                <img
                  src={user.avatar}
                  alt={user.name}
                  className="w-14 h-14 rounded-full border-2 border-[#eae7eb] group-hover:border-[#C0392B] transition-all object-cover flex-shrink-0"
                />
                <div className="min-w-0">
                  <h4 className="text-base font-bold text-[#0D1B3E] leading-tight truncate">
                    {user.name}
                  </h4>
                  <p className="text-xs text-[#45464e] font-medium mt-0.5 truncate">{user.role}</p>
                  <p className="text-[11px] text-gray-400 mt-0.5">Member since {user.memberSince}</p>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="mb-6">
                <div className="bg-[#f5f3f6] p-3 rounded-lg text-center">
                  <p className="text-[10px] uppercase font-semibold text-[#45464e] tracking-wider">
                    Posters Generated
                  </p>
                  <p className="text-lg font-bold text-[#0D1B3E] mt-0.5">
                    {user.postersCount.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Card Footer */}
            <div className="flex justify-between items-center text-xs text-[#45464e] pt-4 border-t border-[#DDE3EE]">
              <span>Last active: {user.lastActive}</span>
              <button
                onClick={() => onSelectUser(user)}
                className="text-[#C0392B] font-bold hover:underline cursor-pointer flex items-center gap-1"
              >
                <UserCheck className="w-3.5 h-3.5" /> View Profile
              </button>
            </div>
          </div>
        ))}

        {filteredUsers.length === 0 && (
          <div className="col-span-full bg-white rounded-xl border border-[#DDE3EE] p-12 text-center text-gray-500">
            No matching users found for "{searchTerm}".
          </div>
        )}
      </div>
    </section>
  );
};
