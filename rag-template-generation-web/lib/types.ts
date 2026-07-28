export interface User {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  conversation_type: 'single' | 'bulk' | 'creation_agent' | string;
  template_folder?: string;
  template_id?: string;
  job_status?: string;
  job_total?: number;
  job_completed?: number;
  job_skipped?: number;
  job_failed?: number;
  job_zip_path?: string;
  job_download_url?: string;
  generated_prompt?: string;
  has_image?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  output_file_path?: string;
  template_used?: string;
  created_at?: string;
}

export interface AgentState {
  assumptions: Record<string, any>;
  generated_prompt: string;
  prompt_versions?: Array<{ version: number; label: string; prompt: string }>;
}

export interface BulkJobStatus {
  job_id?: string;
  id?: string;
  status?: string;
  job_status?: string;
  total?: number;
  job_total?: number;
  completed?: number;
  job_completed?: number;
  skipped?: number;
  job_skipped?: number;
  failed?: number;
  job_failed?: number;
  download_url?: string;
  job_download_url?: string;
  error?: string;
  job_error?: string;
}
