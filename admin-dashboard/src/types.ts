export type NavigationSection = 
  | 'dashboard' 
  | 'search-user' 
  | 'logs' 
  | 'library' 
  | 'templates' 
  | 'profile' 
  | 'settings';

export interface ActivityItem {
  id: string;
  type: 'poster' | 'system' | 'job' | 'warning' | 'edit';
  title: string;
  details: string;
  timestamp: string;
  user?: string;
  icon: string;
  borderColor: string;
}

export interface TopTemplate {
  rank: string;
  name: string;
  count: number;
}

export interface BulkJob {
  id: string;
  user: string;
  status: 'DONE' | 'ACTIVE' | 'QUEUED' | 'FAILED';
  postersGenerated: number;
  template: string;
  startedAt: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar: string;
  memberSince: string;
  postersCount: number;
  avgScore: number;
  lastActive: string;
  role: string;
  status: 'Active' | 'Inactive' | 'Pending';
  department: string;
  bio?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'system' | 'user' | 'assistant' | string;
  text: string;
  time: string;
  output_file_path?: string;
  is_bulk?: boolean;
  template_used?: string;
}

export interface ConversationLog {
  id: string;
  user: string;
  userEmail?: string;
  userAvatar?: string;
  userInitials: string;
  sessionTitle: string;
  date: string;
  timestamp?: string;
  messageCount: number;
  isFlagged?: boolean;
  category: 'Creation Flow' | 'Bulk Request' | 'Support' | 'System Inquiry';
  messages: ChatMessage[];
  complianceScore?: string;
  aiAnalysis?: {
    summary: string;
    sentiment: string;
    complianceScore: string;
    keyTopics: string[];
    recommendation: string;
  };
}

export interface AssetPoster {
  id: string;
  title: string;
  filename: string;
  author: string;
  authorEmail?: string;
  timeAgo: string;
  category: 'Festival' | 'Investment' | 'Corporate' | 'Loan' | 'Stock';
  imageUrl: string;
  dataAlt: string;
  downloads: number;
  views: number;
  isBulk?: boolean;
  zipUrl?: string;
  zipFilename?: string;
  totalPostersInBulk?: number;
  templateFolder?: string;
}

export interface TemplatePreset {
  id: string;
  title: string;
  category: 'Festival' | 'Planning' | 'HR' | 'Investment' | 'Emergency' | string;
  status: 'ACTIVE' | 'DRAFT' | 'ARCHIVED';
  description: string;
  uses: string;
  version: string;
  tags: string[];
  previewImage: string;
  dataAlt: string;
  defaultPrompt?: string;
}
