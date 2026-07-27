import { Conversation, Message, AgentState, BulkJobStatus } from "./types";

export async function login(credentials: { email: string; password: string }) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "Login failed");
  }
  return res.json();
}

export async function register(userData: { email: string; password: string; name: string }) {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userData),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "Registration failed");
  }
  return res.json();
}

export async function logout() {
  const res = await fetch("/api/auth/logout", { method: "POST" });
  return res.json();
}

export async function getConversations(): Promise<Conversation[]> {
  try {
    const res = await fetch("/api/proxy/history/conversations");
    if (res.status === 401) {
      if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
      return [];
    }
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.warn("getConversations failed:", err);
    return [];
  }
}


export async function getConversationMessages(id: string): Promise<{ conversation: Conversation; messages: Message[] }> {
  const res = await fetch(`/api/proxy/history/conversations/${id}/messages`);
  if (!res.ok) throw new Error("Failed to load conversation messages");
  return res.json();
}

export async function getConversationImage(id: string): Promise<Blob> {
  const res = await fetch(`/api/proxy/history/conversations/${id}/image`);
  if (!res.ok) throw new Error("Image not found");
  return res.blob();
}

export async function deleteConversation(id: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/proxy/history/conversations/${id}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch (err) {
    console.error("deleteConversation failed:", err);
    return false;
  }
}

export async function renameConversation(id: string, newTitle: string): Promise<Conversation | null> {
  try {
    const res = await fetch(`/api/proxy/history/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("renameConversation failed:", err);
    return null;
  }
}

export async function generatePoster(formData: FormData): Promise<Response> {
  const res = await fetch("/api/proxy/generate", {
    method: "POST",
    body: formData,
  });
  return res;
}

export async function previewBulkJob(formData: FormData): Promise<any> {
  const res = await fetch("/api/proxy/bulk/preview", {
    method: "POST",
    body: formData,
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text || "Bulk preview failed");
  }
}

export async function startBulkJob(formData: FormData): Promise<any> {
  const res = await fetch("/api/proxy/bulk", {
    method: "POST",
    body: formData,
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text || "Bulk job start failed");
  }
}

export async function resumeBulkJob(jobId: string): Promise<any> {
  const res = await fetch(`/api/proxy/bulk/resume/${jobId}`, {
    method: "POST",
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text || "Failed to resume bulk job");
  }
}


export async function getBulkStatus(jobId: string): Promise<BulkJobStatus> {
  const res = await fetch(`/api/proxy/job-status/${jobId}`);
  if (!res.ok) throw new Error("Failed to get bulk job status");
  return res.json();
}

export async function createAgentConversation(): Promise<{ conversation_id: string }> {
  const res = await fetch("/api/proxy/agent/conversations", {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to create agent session");
  return res.json();
}

export async function getAgentState(conversationId: string): Promise<AgentState> {
  const res = await fetch(`/api/proxy/agent/conversations/${conversationId}/state`);
  if (!res.ok) throw new Error("Failed to get agent state");
  return res.json();
}

export async function agentChat(conversationId: string, message: string) {
  const res = await fetch("/api/proxy/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  });
  if (!res.ok) throw new Error("Agent chat failed");
  return res.json();
}

export async function rebuildPrompt(conversationId: string, assumptions: Record<string, any>, userEdits: string = "") {
  const res = await fetch("/api/proxy/agent/rebuild-prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, assumptions, user_edits: userEdits }),
  });
  if (!res.ok) throw new Error("Failed to rebuild prompt");
  return res.json();
}

export async function refinePrompt(conversationId: string, refinementRequest: string, previousPrompt?: string) {
  const res = await fetch("/api/proxy/agent/refine-prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      refinement_request: refinementRequest,
      previous_prompt: previousPrompt,
    }),
  });
  if (!res.ok) throw new Error("Failed to refine prompt");
  return res.json();
}

export async function generateAgentImage(conversationId: string) {
  const res = await fetch("/api/proxy/agent/generate-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error("Failed to generate agent image");
  return res.json();
}
