"use client";

import React, { useState } from 'react';
import {
  FileText,
  Image as ImageIcon,
  Zap,
  Layers,
  User,
  Settings as SettingsIcon,
  CheckCircle2,
  AlertTriangle,
  Plus,
} from 'lucide-react';
import { ActivityItem, BulkJob, TopTemplate } from '../types';

interface DashboardSectionProps {
  activities: ActivityItem[];
  topTemplates: TopTemplate[];
  bulkJobs: BulkJob[];
  stats?: { total_templates: number; total_posters: number; active_sessions: number; total_users: number };
  onViewAllActivity: () => void;
  onOpenBulkJobModal: () => void;
  onOpenNewPosterModal: () => void;
  onNavigateToTemplates?: () => void;
  onNavigateToLibrary?: () => void;
}

export const DashboardSection: React.FC<DashboardSectionProps> = ({
  activities,
  topTemplates,
  bulkJobs,
  stats,
  onViewAllActivity,
  onOpenBulkJobModal,
  onOpenNewPosterModal,
  onNavigateToTemplates,
  onNavigateToLibrary,
}) => {
  const [activityFilter, setActivityFilter] = useState<'ALL' | 'CRITICAL'>('ALL');

  const filteredActivities = activityFilter === 'ALL' 
    ? activities 
    : activities.filter(a => a.type === 'warning' || a.type === 'job');

  const renderIcon = (iconName: string) => {
    switch (iconName) {
      case 'account_circle':
        return <User className="w-[#C0392B]" />;
      case 'settings':
        return <SettingsIcon className="w-5 h-5 text-[#1E3A6E]" />;
      case 'check_circle':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-[#C0392B]" />;
      default:
        return <FileText className="w-5 h-5 text-[#0D1B3E]" />;
    }
  };

  return (
    <section className="animate-fade-in space-y-8">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Metric 1 - Total Templates Card (Clickable) */}
        <div 
          onClick={onNavigateToTemplates}
          className="bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm hover:shadow-md transition-all cursor-pointer group"
          title="Click to view all template presets & subfolders"
        >
          <div className="flex justify-between items-start mb-4">
            <div className="w-12 h-12 rounded-xl bg-[#dbe1ff]/30 flex items-center justify-center text-[#0D1B3E] group-hover:bg-[#0D1B3E] group-hover:text-white transition-all">
              <FileText className="w-6 h-6" />
            </div>
            <span className="text-xs font-semibold text-[#001a43] bg-[#d8e2ff]/50 px-2 py-1 rounded-md group-hover:bg-amber-300 group-hover:text-[#0D1B3E]">
              View All →
            </span>
          </div>
          <h3 className="text-xs font-medium text-[#45464e]">Total Templates</h3>
          <p className="text-2xl font-bold text-[#0D1B3E] mt-1">{stats?.total_templates ?? 16}</p>
        </div>

        {/* Metric 2 - Total Posters Card (Clickable to Library) */}
        <div 
          onClick={onNavigateToLibrary}
          className="bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm hover:shadow-md transition-all cursor-pointer group"
          title="Click to view all generated outputs in Asset Library"
        >
          <div className="flex justify-between items-start mb-4">
            <div className="w-12 h-12 rounded-xl bg-[#dce1ff]/30 flex items-center justify-center text-[#0D1B3E] group-hover:bg-[#0D1B3E] group-hover:text-white transition-all">
              <ImageIcon className="w-6 h-6" />
            </div>
            <span className="text-xs font-semibold text-[#001a43] bg-[#d8e2ff]/50 px-2 py-1 rounded-md group-hover:bg-amber-300 group-hover:text-[#0D1B3E]">
              View All →
            </span>
          </div>
          <h3 className="text-xs font-medium text-[#45464e]">Total Posters</h3>
          <p className="text-2xl font-bold text-[#0D1B3E] mt-1">{(stats?.total_posters ?? 117).toLocaleString()}</p>
        </div>

        {/* Metric 3 - Active Users in Last 24 Hours */}
        <div className="bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm hover:shadow-md transition-all">
          <div className="flex justify-between items-start mb-4">
            <div className="w-12 h-12 rounded-xl bg-[#ffdad6]/40 flex items-center justify-center text-[#C0392B]">
              <User className="w-6 h-6" />
            </div>
            <span className="text-xs font-semibold text-[#ba1a1a] bg-[#ffdad6] px-2.5 py-1 rounded-md">
              24h
            </span>
          </div>
          <h3 className="text-xs font-medium text-[#45464e]">Active Users (Last 24h)</h3>
          <p className="text-2xl font-bold text-[#0D1B3E] mt-1">{stats?.active_sessions ?? 0}</p>
        </div>

        {/* Metric 4 */}
        <div className="bg-white p-6 rounded-xl border border-[#DDE3EE] shadow-sm hover:shadow-md transition-all">
          <div className="flex justify-between items-start mb-4">
            <div className="w-12 h-12 rounded-xl bg-[#e4e2e5] flex items-center justify-center text-[#0D1B3E]">
              <Layers className="w-6 h-6" />
            </div>
            <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-1 rounded-md">
              Total
            </span>
          </div>
          <h3 className="text-xs font-medium text-[#45464e]">Total Completed Bulk Jobs</h3>
          <p className="text-2xl font-bold text-[#0D1B3E] mt-1">
            {bulkJobs.filter((j) => j.status === 'DONE').length}
          </p>
        </div>
      </div>

      {/* Main Grid: Activity Feed + Right Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity Feed */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#DDE3EE] flex flex-col overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-[#DDE3EE] flex justify-between items-center bg-white">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-[#0D1B3E]">Recent Activity Feed</h2>
              <div className="flex gap-1 bg-[#f5f3f6] p-0.5 rounded-lg text-xs">
                <button
                  onClick={() => setActivityFilter('ALL')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    activityFilter === 'ALL' ? 'bg-white text-[#0D1B3E] shadow-sm' : 'text-[#45464e]'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setActivityFilter('CRITICAL')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    activityFilter === 'CRITICAL' ? 'bg-white text-[#C0392B] shadow-sm' : 'text-[#45464e]'
                  }`}
                >
                  Critical
                </button>
              </div>
            </div>
            <button
              onClick={onViewAllActivity}
              className="text-xs font-bold text-[#1E3A6E] hover:underline"
            >
              View All
            </button>
          </div>

          <div className="p-6 space-y-4 max-h-[520px] overflow-y-auto">
            {filteredActivities.slice(0, 10).map((item) => (
              <div
                key={item.id}
                onClick={onViewAllActivity}
                className={`flex items-center gap-4 p-4 border-l-4 ${item.borderColor || 'border-[#0D1B3E]'} bg-[#ffffff] rounded-lg shadow-xs hover:shadow-md transition-all border border-[#DDE3EE]/60 cursor-pointer group`}
                title="Click to view full conversation log"
              >
                <div className="flex-shrink-0">{renderIcon(item.icon)}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#1b1b1e] group-hover:text-[#1E3A6E] transition-colors">{item.title}</p>
                  <p className="text-xs text-[#45464e] mt-0.5 truncate">{item.details}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Bulk Jobs */}
        <div className="space-y-6">

          {/* Recent Completed Bulk Jobs Table */}
          <div className="bg-white rounded-xl border border-[#DDE3EE] p-6 shadow-sm overflow-hidden">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-base font-bold text-[#0D1B3E]">Recent Completed Bulk Jobs</h2>
              <button
                onClick={onOpenBulkJobModal}
                className="text-xs font-semibold text-[#1E3A6E] hover:underline flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> Schedule Job
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-[#1E3A6E] text-white">
                  <tr>
                    <th className="px-3 py-2 text-[11px] uppercase tracking-wider font-semibold">Job ID</th>
                    <th className="px-3 py-2 text-[11px] uppercase tracking-wider font-semibold">User</th>
                    <th className="px-3 py-2 text-[11px] uppercase tracking-wider font-semibold text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="text-xs divide-y divide-[#DDE3EE]">
                  {bulkJobs
                    .filter((job) => job.status === 'DONE')
                    .slice(0, 5)
                    .map((job) => (
                      <tr key={job.id} className="hover:bg-slate-50 transition-all">
                        <td className="px-3 py-3 font-semibold text-[#0D1B3E]">{job.id}</td>
                        <td className="px-3 py-3 text-[#1b1b1e]">{job.user}</td>
                        <td className="px-3 py-3 text-right">
                          <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full text-[10px] font-bold inline-block">
                            DONE
                          </span>
                        </td>
                      </tr>
                    ))}
                  {bulkJobs.filter((job) => job.status === 'DONE').length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-3 py-4 text-center text-gray-400 text-xs italic">
                        No completed bulk jobs recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
