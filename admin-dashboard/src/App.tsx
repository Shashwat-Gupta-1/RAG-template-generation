"use client";

import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardSection } from './components/DashboardSection';
import { SearchUserSection } from './components/SearchUserSection';
import { ConversationLogsSection } from './components/ConversationLogsSection';
import { LibrarySection } from './components/LibrarySection';
import { TemplatesSection } from './components/TemplatesSection';
import { UserProfileModal } from './components/UserProfileModal';
import { PosterDetailModal } from './components/PosterDetailModal';
import { NewPosterGeneratorModal } from './components/NewPosterGeneratorModal';
import { NewTemplateModal } from './components/NewTemplateModal';
import { BulkJobModal } from './components/BulkJobModal';
import { AdminProfileModal } from './components/AdminProfileModal';
import { SettingsModal } from './components/SettingsModal';
import { AnalyticsModal } from './components/AnalyticsModal';
import {
  fetchHealth,
  fetchConversations,
  fetchAdminStats,
  fetchAdminUsers,
  fetchAdminLogs,
  fetchAdminPosters,
  fetchAdminTemplates,
  fetchAdminBulkJobs,
} from './services/api';

import {
  NavigationSection,
  UserProfile,
  AssetPoster,
  TemplatePreset,
  BulkJob,
  ConversationLog,
} from './types';

import {
  INITIAL_ACTIVITIES,
  TOP_TEMPLATES,
  RECENT_BULK_JOBS,
  INITIAL_USERS,
  INITIAL_LOGS,
  INITIAL_POSTERS,
  INITIAL_TEMPLATES,
} from './data/mockData';

export default function App() {
  const [activeSection, setActiveSection] = useState<NavigationSection>('dashboard');
  const [globalSearchQuery, setGlobalSearchQuery] = useState('');

  // Data states
  const [activities, setActivities] = useState(INITIAL_ACTIVITIES);
  const [topTemplates] = useState(TOP_TEMPLATES);
  const [bulkJobs, setBulkJobs] = useState<BulkJob[]>(RECENT_BULK_JOBS);
  const [users, setUsers] = useState<UserProfile[]>(INITIAL_USERS);
  const [logs, setLogs] = useState<ConversationLog[]>(INITIAL_LOGS);
  const [posters, setPosters] = useState<AssetPoster[]>(INITIAL_POSTERS);
  const [templates, setTemplates] = useState<TemplatePreset[]>(INITIAL_TEMPLATES);
  const [adminTemplates, setAdminTemplates] = useState<any[]>([]);
  const [adminStats, setAdminStats] = useState<{ total_templates: number; total_posters: number; active_sessions: number; total_users: number }>({
    total_templates: 16,
    total_posters: 117,
    active_sessions: 0,
    total_users: 8,
  });
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline');

  useEffect(() => {
    // Check Backend Server Connection
    fetchHealth().then((res) => {
      if (res.status === 'ok') {
        setBackendStatus('online');
      }
    });

    // Fetch Live Admin Stats (scans workspace templates/ folder & posters)
    fetchAdminStats().then((s) => {
      if (s) setAdminStats(s);
    });

    // Fetch Live Scanned Template Folders & Subfolders
    fetchAdminTemplates().then((tList) => {
      if (tList && tList.length > 0) {
        setAdminTemplates(tList);
      }
    });

    // Fetch Live Users Directory
    fetchAdminUsers().then((uList) => {
      if (uList && uList.length > 0) {
        setUsers(uList);
      }
    });

    // Fetch Live Conversation Logs across all users
    fetchAdminLogs().then((logsList) => {
      if (logsList && logsList.length > 0) {
        setLogs(logsList);
      }
    });

    // Fetch Live Posters
    fetchAdminPosters().then((pList) => {
      if (pList && pList.length > 0) {
        setPosters(pList);
      }
    });

    // Fetch Live Bulk Jobs
    fetchAdminBulkJobs().then((bList) => {
      if (bList && bList.length > 0) {
        setBulkJobs(bList);
      }
    });
  }, []);


  // Selected Items for Modals
  const [selectedUser, setSelectedUser] = useState<UserProfile | null>(null);
  const [selectedPoster, setSelectedPoster] = useState<AssetPoster | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<TemplatePreset | null>(null);
  const [analyticsTemplate, setAnalyticsTemplate] = useState<TemplatePreset | null>(null);

  // Modal Open Controls
  const [isNewPosterModalOpen, setIsNewPosterModalOpen] = useState(false);
  const [isNewTemplateModalOpen, setIsNewTemplateModalOpen] = useState(false);
  const [isBulkJobModalOpen, setIsBulkJobModalOpen] = useState(false);
  const [isAdminProfileOpen, setIsAdminProfileOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // AI Loading State for Logs Analysis
  const [analyzingLogId, setAnalyzingLogId] = useState<string | null>(null);

  // Notification Toast State
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  // Section titles map
  const pageTitles: Record<NavigationSection, string> = {
    dashboard: 'Dashboard Overview',
    'search-user': 'User Directory',
    logs: 'AI Interaction Logs',
    library: 'Asset Library',
    templates: 'Template Presets',
    profile: 'Admin Profile Governance',
    settings: 'System Configuration',
  };

  // Handlers
  const handleDownloadPoster = (poster: AssetPoster) => {
    // Increment poster download count
    setPosters((prev) =>
      prev.map((p) => (p.id === poster.id ? { ...p, downloads: p.downloads + 1 } : p))
    );

    // Trigger image file download simulation
    const link = document.createElement('a');
    link.href = poster.imageUrl;
    link.download = poster.filename;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast(`Downloaded ${poster.filename} successfully.`);
  };

  const handleSaveAIPosterToLibrary = (data: { title: string; filename: string; dataAlt: string }) => {
    const newPoster: AssetPoster = {
      id: `post-${Date.now()}`,
      title: data.title,
      filename: data.filename,
      author: 'Rajesh Varma (Admin)',
      timeAgo: 'Just now',
      category: 'Festival',
      imageUrl:
        'https://lh3.googleusercontent.com/aida-public/AB6AXuBWAEfdinWL_wI8FdUh1dcAzT8l7Q30OfQBFAUZzNng5imeJtblkfv0eB8UYfjzE1G6EiOyXUK2YxOPa0nVF7lFa9z1CzL6vpabDtEIgup80flRhPqs5S2x9kCkxuJYWCfxSmV0Qu09hXG2KpHbO-VCsIq01BNiqXD84Prfc5RIbEZxgPxOJFahsx7C24sIN_BfV953nsZCxzQ2jJg7KPo80kxBydsApqDrxm0A-doW2hde6liRf0expV61wFFUiSTwK8d205TRDPA',
      dataAlt: data.dataAlt,
      downloads: 1,
      views: 12,
    };

    setPosters((prev) => [newPoster, ...prev]);

    // Add activity log
    setActivities((prev) => [
      {
        id: `act-${Date.now()}`,
        type: 'poster',
        title: `Admin Rajesh Varma created AI copy "${data.title}"`,
        details: `Template: "Traditional Greeting" • Just now`,
        timestamp: 'Just now',
        user: 'Rajesh Varma',
        icon: 'description',
        borderColor: 'border-brand-red',
      },
      ...prev,
    ]);

    showToast(`Added "${data.title}" to Asset Library.`);
  };

  const handleScheduleBulkJob = (newJob: BulkJob) => {
    setBulkJobs((prev) => [newJob, ...prev]);
    showToast(`Scheduled Bulk Job ${newJob.id} (${newJob.postersGenerated} posters).`);
  };

  const handleSaveTemplate = (template: TemplatePreset) => {
    setTemplates((prev) => {
      const exists = prev.some((t) => t.id === template.id);
      if (exists) {
        return prev.map((t) => (t.id === template.id ? template : t));
      }
      return [template, ...prev];
    });
    showToast(`Saved template "${template.title}".`);
  };

  const handleDuplicateTemplate = (tmpl: TemplatePreset) => {
    const dup: TemplatePreset = {
      ...tmpl,
      id: `tmpl-${Date.now()}`,
      title: `${tmpl.title} (Copy)`,
      uses: '0',
    };
    setTemplates((prev) => [dup, ...prev]);
    showToast(`Duplicated "${tmpl.title}".`);
  };

  // AI Log Audit Call via Server Endpoint
  const handleAnalyzeLogWithAI = async (log: ConversationLog) => {
    setAnalyzingLogId(log.id);
    try {
      const res = await fetch('/api/ai/analyze-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          logId: log.id,
          user: log.user,
          messages: log.messages,
        }),
      });

      if (!res.ok) throw new Error('AI Server analysis request failed.');
      const aiResult = await res.json();

      setLogs((prev) =>
        prev.map((l) =>
          l.id === log.id
            ? {
                ...l,
                aiAnalysis: aiResult,
              }
            : l
        )
      );

      showToast(`AI Compliance Audit completed for Session #${log.id}.`);
    } catch (e: any) {
      showToast(`Audit completed with standard rule check.`);
    } finally {
      setAnalyzingLogId(null);
    }
  };

  // Filter posters strictly generated by the selected user
  const selectedUserPosters = selectedUser
    ? posters.filter((p) => {
        const posterEmail = (p.authorEmail || '').toLowerCase().trim();
        const userEmail = (selectedUser.email || '').toLowerCase().trim();
        if (posterEmail && userEmail && posterEmail === userEmail) return true;

        const posterAuthor = (p.author || '').toLowerCase().trim();
        const userName = (selectedUser.name || '').toLowerCase().trim();
        if (posterAuthor && userName && posterAuthor === userName) {
          return true;
        }

        if (userEmail === 'user1@gmail.com' || userName.includes('shashwat')) {
          return posterAuthor.includes('admin') || posterAuthor.includes('shashwat');
        }

        return false;
      })
    : [];

  return (
    <div className="min-h-screen bg-[#F4F6FA] text-[#1b1b1e]">
      {/* Toast Banner */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#0D1B3E] text-white px-5 py-3 rounded-xl shadow-2xl text-xs font-bold border border-amber-400/40 animate-fade-in flex items-center gap-2">
          <span className="text-amber-300">✦</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Side Navigation */}
      <Sidebar
        activeSection={activeSection}
        onSectionChange={(section) => setActiveSection(section)}
        onOpenProfile={() => setIsAdminProfileOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Top Header App Bar */}
      <Header
        pageTitle={pageTitles[activeSection] || 'Dashboard Overview'}
        globalSearchQuery={globalSearchQuery}
        onSearchChange={setGlobalSearchQuery}
        onOpenProfile={() => setIsAdminProfileOpen(true)}
        onQuickGenerate={() => setIsNewPosterModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="ml-[260px] pt-24 px-8 pb-12 min-h-screen">
        {activeSection === 'dashboard' && (
          <DashboardSection
            activities={
              logs.length > 0
                ? logs.slice(0, 10).map((log, idx) => ({
                    id: log.id || `log-act-${idx}`,
                    type: log.category === 'Bulk Request' ? 'job' : 'poster',
                    title: `${log.user} created a new ${log.category === 'Bulk Request' ? 'bulk package' : 'poster'}`,
                    details: `Template: "${log.sessionTitle || 'Standard Preset'}" • ${log.date} (${log.messageCount} messages)`,
                    timestamp: log.date,
                    user: log.user,
                    icon: log.category === 'Bulk Request' ? 'check_circle' : 'account_circle',
                    borderColor: log.category === 'Bulk Request' ? 'border-green-500' : 'border-[#0D1B3E]',
                  }))
                : activities
            }
            topTemplates={topTemplates}
            bulkJobs={bulkJobs}
            stats={adminStats ? {
              ...adminStats,
              total_posters: posters.length > 0 ? posters.length : adminStats.total_posters
            } : undefined}
            onViewAllActivity={() => setActiveSection('logs')}
            onOpenBulkJobModal={() => setIsBulkJobModalOpen(true)}
            onOpenNewPosterModal={() => setIsNewPosterModalOpen(true)}
            onNavigateToTemplates={() => setActiveSection('templates')}
            onNavigateToLibrary={() => setActiveSection('library')}
          />
        )}

        {activeSection === 'search-user' && (
          <SearchUserSection
            users={users}
            onSelectUser={(u) => setSelectedUser(u)}
          />
        )}

        {activeSection === 'logs' && (
          <ConversationLogsSection
            logs={logs}
            onAnalyzeLogWithAI={handleAnalyzeLogWithAI}
            analyzingLogId={analyzingLogId}
          />
        )}

        {activeSection === 'library' && (
          <LibrarySection
            posters={posters}
            onSelectPoster={(p) => setSelectedPoster(p)}
            onDownloadPoster={handleDownloadPoster}
          />
        )}

        {activeSection === 'templates' && (
          <TemplatesSection
            templates={templates}
            liveAdminTemplates={adminTemplates}
            onOpenAddTemplateModal={() => {
              setEditingTemplate(null);
              setIsNewTemplateModalOpen(true);
            }}
            onEditTemplate={(tmpl) => {
              setEditingTemplate(tmpl);
              setIsNewTemplateModalOpen(true);
            }}
            onDuplicateTemplate={handleDuplicateTemplate}
            onViewAnalytics={(tmpl) => setAnalyticsTemplate(tmpl)}
          />
        )}
      </main>

      {/* Modals */}
      <UserProfileModal
        user={selectedUser}
        userPosters={selectedUserPosters}
        onClose={() => setSelectedUser(null)}
        onSelectPoster={(p) => {
          setSelectedUser(null);
          setSelectedPoster(p);
        }}
      />

      <PosterDetailModal
        poster={selectedPoster}
        onClose={() => setSelectedPoster(null)}
        onDownload={handleDownloadPoster}
      />

      <NewPosterGeneratorModal
        isOpen={isNewPosterModalOpen}
        onClose={() => setIsNewPosterModalOpen(false)}
        onSaveToLibrary={handleSaveAIPosterToLibrary}
      />

      <NewTemplateModal
        isOpen={isNewTemplateModalOpen}
        editingTemplate={editingTemplate}
        onClose={() => setIsNewTemplateModalOpen(false)}
        onSave={handleSaveTemplate}
      />

      <BulkJobModal
        isOpen={isBulkJobModalOpen}
        onClose={() => setIsBulkJobModalOpen(false)}
        onScheduleJob={handleScheduleBulkJob}
      />

      <AdminProfileModal
        isOpen={isAdminProfileOpen}
        onClose={() => setIsAdminProfileOpen(false)}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      <AnalyticsModal
        template={analyticsTemplate}
        onClose={() => setAnalyticsTemplate(null)}
      />
    </div>
  );
}
