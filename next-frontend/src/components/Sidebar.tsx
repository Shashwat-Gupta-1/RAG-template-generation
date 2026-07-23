"use client";

import React, { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Image as ImageIcon, PlusSquare, ChevronRight, LogOut, ChevronLeft, Sparkles, MoreVertical, Edit2, Trash2 } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  
  const [collapsed, setCollapsed] = useState(false);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<{name: string, role: string} | null>(null);

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Auto-collapse on small screens
  useEffect(() => {
    const checkSize = () => {
      if (window.innerWidth < 768) {
        setCollapsed(true);
      } else {
        setCollapsed(false);
      }
    };
    checkSize();
    window.addEventListener('resize', checkSize);
    return () => window.removeEventListener('resize', checkSize);
  }, []);

  const isActive = (path: string) => {
    if (path === '/' && (pathname === '/' || pathname === '/generate')) return true;
    if (path === pathname) return true;
    return false;
  };

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) return;
        
        // Fetch User Info
        const userRes = await fetch("http://localhost:8000/auth/me", {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (userRes.ok) {
          const userData = await userRes.json();
          setUser({ name: userData.name, role: userData.role });
        }

        // Fetch History
        const res = await fetch("http://localhost:8000/history/conversations?limit=10", {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setSessions(data);
        }
      } catch (err) {
        console.error("Failed to fetch history or user", err);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [pathname]); // Refetch when route changes so it stays somewhat fresh

  const handleRename = async (e: React.MouseEvent, id: string, oldTitle: string) => {
    e.stopPropagation();
    setEditingSessionId(id);
    setEditTitle(oldTitle || "Untitled Session");
  };

  const submitRename = async (id: string) => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/history/conversations/${id}`, {
        method: 'PATCH',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: editTitle })
      });
      setSessions(prev => prev.map(s => s.id === id ? { ...s, title: editTitle } : s));
    } catch (err) {
      console.error(err);
    } finally {
      setEditingSessionId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this session?")) return;
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/history/conversations/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      setSessions(prev => prev.filter(s => s.id !== id));
      if (pathname.includes(id)) {
        router.push('/');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const getSessionColor = (type: string) => {
    switch (type) {
      case 'creation_agent': return 'bg-[#6366f1]'; // purple
      case 'bulk': return 'bg-orange-500';
      case 'single': return 'bg-teal-500';
      default: return 'bg-gray-500';
    }
  };

  const getSessionLabel = (type: string) => {
    switch (type) {
      case 'creation_agent': return 'AI CREATE';
      case 'bulk': return 'BULK';
      case 'single': return 'SINGLE';
      default: return 'JOB';
    }
  };

  return (
    <div 
      className={`fixed left-0 top-0 h-full bg-[#0d0d1a] border-r border-[#1f2937] z-50 flex flex-col transition-all duration-300 ${collapsed ? 'w-[60px]' : 'w-[220px]'}`}
    >
      {/* Mobile Toggle Button */}
      <button 
        onClick={() => setCollapsed(!collapsed)}
        className="md:hidden absolute -right-3 top-6 bg-[#1f2937] text-white rounded-full p-1 border border-gray-700 z-50 shadow-md"
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      {/* Top Section */}
      <div className={`p-5 flex flex-col ${collapsed ? 'items-center px-0' : ''}`}>
        {!collapsed ? (
          <div>
            <h1 className="text-[#6366f1] font-bold text-[16px]">MS Fincap AI</h1>
            <p className="text-gray-500 text-[10px] uppercase tracking-wide mt-1">Poster Generation System</p>
          </div>
        ) : (
          <h1 className="text-[#6366f1] font-bold text-lg">MS</h1>
        )}
      </div>

      <div className="h-px w-full bg-[#1f2937] mb-4"></div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 w-full">
        <button
          onClick={() => router.push('/')}
          className={`flex items-center gap-3 w-full transition-colors ${collapsed ? 'justify-center py-3' : 'px-5 py-3'} ${
            isActive('/') 
              ? 'bg-[#1a1a2e] text-[#6366f1] border-l-[3px] border-[#6366f1]' 
              : 'text-[#6b7280] hover:bg-[#1a1a2e] hover:text-white border-l-[3px] border-transparent'
          }`}
          title="Generate"
        >
          <ImageIcon size={18} />
          {!collapsed && <span className="font-medium text-sm text-left">Generate</span>}
        </button>

        <button
          onClick={() => router.push('/add-template')}
          className={`flex items-center gap-3 w-full transition-colors ${collapsed ? 'justify-center py-3' : 'px-5 py-3'} ${
            isActive('/add-template') 
              ? 'bg-[#1a1a2e] text-[#6366f1] border-l-[3px] border-[#6366f1]' 
              : 'text-[#6b7280] hover:bg-[#1a1a2e] hover:text-white border-l-[3px] border-transparent'
          }`}
          title="Add Template"
        >
          <PlusSquare size={18} />
          {!collapsed && <span className="font-medium text-sm text-left">Add Template</span>}
        </button>

        <button
          onClick={() => router.push('/create-template')}
          className={`flex items-center gap-3 w-full transition-colors ${collapsed ? 'justify-center py-3' : 'px-5 py-3'} ${
            isActive('/create-template') 
              ? 'bg-[#1a1a2e] text-[#6366f1] border-l-[3px] border-[#6366f1]' 
              : 'text-[#6b7280] hover:bg-[#1a1a2e] hover:text-white border-l-[3px] border-transparent'
          }`}
          title="Create Template (AI)"
        >
          <Sparkles size={18} />
          {!collapsed && <span className="font-medium text-sm text-left flex-1">Create Template</span>}
        </button>
      </nav>

      {/* Bottom Section */}
      <div className="mt-auto w-full flex flex-col">
        
        {/* Recent Sessions */}
        {!collapsed && (
          <div className="px-5 mb-6">
            <h3 className="text-gray-500 text-[11px] uppercase tracking-wider font-semibold mb-3">Recent Sessions</h3>
            <div className="flex flex-col gap-1 max-h-[160px] overflow-y-auto pr-1 custom-scrollbar">
              {loading ? (
                <div className="text-xs text-gray-600 px-2">Loading...</div>
              ) : sessions.length === 0 ? (
                <div className="text-[10px] text-gray-600 px-2">No recent sessions</div>
              ) : (
                sessions.map(session => (
                  <div 
                    key={session.id} 
                    onClick={() => {
                      if (editingSessionId !== session.id) {
                        router.push(`/history/${session.id}`);
                      }
                    }}
                    className="flex items-center gap-2 py-1.5 px-2 hover:bg-[#1a1a2e] rounded cursor-pointer group transition-colors relative"
                  >
                    <span className={`text-[8px] font-bold text-white px-1.5 py-0.5 rounded ${getSessionColor(session.conversation_type)}`}>
                      {getSessionLabel(session.conversation_type)}
                    </span>
                    
                    {editingSessionId === session.id ? (
                      <input 
                        autoFocus
                        value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        onBlur={() => submitRename(session.id)}
                        onKeyDown={e => e.key === 'Enter' && submitRename(session.id)}
                        className="text-xs bg-[#1f2937] text-white outline-none w-full border border-[#6366f1] rounded px-1"
                        onClick={e => e.stopPropagation()}
                      />
                    ) : (
                      <span className="text-xs text-gray-400 group-hover:text-gray-200 truncate font-medium flex-1">
                        {session.title || "Untitled Session"}
                      </span>
                    )}

                    {!editingSessionId && (
                      <div className="hidden group-hover:flex items-center gap-1 absolute right-2 bg-[#1a1a2e] pl-2">
                        <button onClick={(e) => handleRename(e, session.id, session.title)} className="text-gray-500 hover:text-white transition-colors" title="Rename">
                          <Edit2 size={12} />
                        </button>
                        <button onClick={(e) => handleDelete(e, session.id)} className="text-gray-500 hover:text-red-400 transition-colors" title="Delete">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="h-px w-full bg-[#1f2937]"></div>

        {/* User Info */}
        <div className={`p-4 flex items-center justify-between ${collapsed ? 'flex-col gap-4 px-2 py-6' : ''}`}>
          <div className="flex items-center gap-3 w-full justify-center">
            <div className="w-8 h-8 rounded-full bg-[#1f2937] border border-gray-700 flex flex-shrink-0 items-center justify-center text-sm font-bold text-white uppercase">
              {user ? user.name[0] : "U"}
            </div>
            {!collapsed && (
              <div className="flex flex-col flex-1 overflow-hidden">
                <span className="text-white text-sm font-bold leading-tight truncate">{user ? user.name : "Loading..."}</span>
                <span className="text-gray-500 text-xs truncate capitalize">{user ? user.role : "User"}</span>
              </div>
            )}
          </div>
        </div>

        {/* Logout */}
        <div className={`px-4 pb-6 w-full ${collapsed ? 'px-2' : ''}`}>
          <button 
            onClick={() => {
              localStorage.removeItem("token");
              router.push("/login");
            }}
            className={`w-full flex items-center gap-2 text-[#6b7280] hover:text-[#ef4444] transition-colors rounded py-2 ${collapsed ? 'justify-center' : 'px-2'}`}
            title="Log Out"
          >
            <LogOut size={16} className="flex-shrink-0" />
            {!collapsed && <span className="text-sm font-medium">Log Out</span>}
          </button>
        </div>

      </div>
    </div>
  );
}
