"use client";

import React, { useState, useEffect, useRef } from 'react';
import ZoneMapper, { Zone } from '@/components/ZoneMapper';
import { useRouter } from 'next/navigation';
import { CloudUpload, Trash2, Loader2, CheckCircle2, ChevronDown, PlusCircle, Send, Sparkles, RefreshCw, Undo, Image as ImageIcon } from 'lucide-react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

export default function CreateTemplatePage() {
  const router = useRouter();
  
  const [step, setStep] = useState(0); // 0: Chat, 1: Upload, 2: Draw, 3: Save, 4: Success
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // -----------------------------------------------------
  // STEP 0: AGENT CHAT STATE
  // -----------------------------------------------------
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [assumptions, setAssumptions] = useState<Record<string, string>>({});
  const [generatedPrompt, setGeneratedPrompt] = useState('');
  const [agentReady, setAgentReady] = useState(false);
  const [userEdits, setUserEdits] = useState('');
  const [refinementInput, setRefinementInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Init Agent Chat
  useEffect(() => {
    const initChat = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch("http://localhost:8000/agent/conversations", {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Failed to start session");
        const data = await res.json();
        setConversationId(data.conversation_id);

        // Fetch greeting
        const greetRes = await fetch("http://localhost:8000/agent/chat", {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ conversation_id: data.conversation_id })
        });
        const greetData = await greetRes.json();
        setMessages([{ role: 'assistant', content: greetData.reply }]);
        setAssumptions(greetData.assumptions || {});
        setAgentReady(greetData.ready || false);
        if (greetData.generated_prompt) setGeneratedPrompt(greetData.generated_prompt);

      } catch (err) {
        console.error(err);
        setError("Failed to connect to Creative Director Agent.");
      }
    };
    initChat();
  }, []);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() || !conversationId) return;

    const userMsg = inputMessage.trim();
    setInputMessage('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/agent/chat", {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          conversation_id: conversationId,
          message: userMsg 
        })
      });
      const data = await res.json();
      
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      setAssumptions(data.assumptions || {});
      setAgentReady(data.ready || false);
      if (data.generated_prompt) setGeneratedPrompt(data.generated_prompt);

    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRebuildPrompt = async () => {
    if (!conversationId) return;
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/agent/rebuild-prompt", {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          conversation_id: conversationId,
          assumptions,
          user_edits: userEdits
        })
      });
      const data = await res.json();
      if (data.generated_prompt) setGeneratedPrompt(data.generated_prompt);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefinePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conversationId || !refinementInput.trim()) return;
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/agent/refine-prompt", {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          conversation_id: conversationId,
          refinement_request: refinementInput
        })
      });
      const data = await res.json();
      if (data.generated_prompt) setGeneratedPrompt(data.generated_prompt);
      setRefinementInput('');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateImage = async () => {
    if (!conversationId) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/agent/generate-image", {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ conversation_id: conversationId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Image generation failed");
      
      const tokenQuery = `token=${token}`;
      // Need to fetch it as a blob so we can attach it to a File object for the rest of the flow
      const imgRes = await fetch(`http://localhost:8000/agent/image?path=${encodeURIComponent(data.image_path)}&${tokenQuery}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const blob = await imgRes.blob();
      const f = new File([blob], "ai_generated_template.png", { type: blob.type });
      handleFileChange(f);
      setStep(1);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // -----------------------------------------------------
  // STEP 1-4: STANDARD ADD TEMPLATE LOGIC
  // -----------------------------------------------------
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState({ w: 0, h: 0 });
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [configs, setConfigs] = useState<Record<string, any>>({});
  const [categories, setCategories] = useState<string[]>(['festival', 'hr', 'promotional', 'grand_opening']);
  const [category, setCategory] = useState('festival');
  const [newCategory, setNewCategory] = useState('');
  const [baseId, setBaseId] = useState('');
  const [hint, setHint] = useState('');
  const [keywords, setKeywords] = useState('');
  const [successData, setSuccessData] = useState<any>(null);

  // Fetch available categories
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await fetch("http://localhost:8000/templates/categories");
        if (res.ok) {
          const data = await res.json();
          if (data.categories && data.categories.length > 0) {
            setCategories(data.categories);
            setCategory(data.categories[0]);
          }
        }
      } catch (err) {
        console.error("Failed to load categories", err);
      }
    };
    fetchCategories();
  }, []);

  const handleFileChange = (f: File | null) => {
    setUploadError(null);
    if (!f) return;
    setFile(f);
    const url = URL.createObjectURL(f);
    setImageUrl(url);
    const img = new window.Image();
    img.onload = () => setImageSize({ w: img.width, h: img.height });
    img.src = url;
  };

  const handleDragOver = (e: React.DragEvent) => e.preventDefault();
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) handleFileChange(e.dataTransfer.files[0]);
  };

  const handleZoneChange = (newZones: Zone[]) => {
    setZones(prev => newZones.map(z => ({ ...z, selected: z.id === selectedZoneId })));
  };

  const handleSelectZone = (id: string | null) => {
    setSelectedZoneId(id);
    setZones(prev => prev.map(z => ({ ...z, selected: z.id === id })));
    if (id && !configs[id]) {
      setConfigs(prev => ({
        ...prev,
        [id]: {
          id: id,
          type: 'text',
          instruction: `Value for ${id}`,
          llm_can_invent: true,
          font_family: 'Poppins',
          font_size: 48,
          font_size_min: 20,
          font_weight: 'bold',
          color: '#ffffff',
          align: 'center'
        }
      }));
    }
  };

  const updateConfig = (id: string, key: string, value: any) => {
    if (key === 'id') value = value.toLowerCase().replace(/\s+/g, '_');
    setConfigs(prev => ({
      ...prev,
      [id]: { ...prev[id], [key]: value }
    }));
  };

  const deleteZone = (id: string) => {
    setZones(zones.filter(z => z.id !== id));
    if (selectedZoneId === id) setSelectedZoneId(null);
  };

  const isValidStep2 = zones.length > 0 && zones.every(z => configs[z.id]?.id?.trim());

  const handleSubmit = async () => {
    const finalCategory = category === 'create_new' ? newCategory.trim() : category;

    if (!file || !finalCategory || !baseId) {
      setError("Please fill out all required fields correctly.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const overlay_layers = zones.map(z => {
        const conf = configs[z.id] || {};
        return { ...conf, id: conf.id || z.id, x: z.x, y: z.y, width: z.width, height: z.height };
      });
      const overlayData = { canvas: { width: imageSize.w, height: imageSize.h }, overlay_layers };

      const formData = new FormData();
      formData.append('image', file);
      formData.append('overlay_data', JSON.stringify(overlayData));
      formData.append('category', finalCategory);
      formData.append('base_id', baseId);
      formData.append('hint', `${hint}\nKeywords: ${keywords}`);

      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/templates/add", {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to add template");

      setSuccessData({
        template_id: data.template_id,
        folder_path: data.folder_path,
        tags: keywords.split(',').map(k => k.trim()).filter(k => k),
        description: hint
      });
      setStep(4);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // -----------------------------------------------------
  // RENDER HELPERS
  // -----------------------------------------------------
  const ProgressSteps = () => (
    <div className="sticky top-0 z-10 bg-[#0a0a0a]/80 backdrop-blur-md py-6 mb-8 border-b border-white/5">
      <div className="flex items-center justify-center max-w-[800px] mx-auto relative">
        <div className="absolute top-[15px] left-[12%] right-[12%] h-[2px] bg-gray-800 -z-10"></div>
        <div 
          className="absolute top-[15px] left-[12%] h-[2px] bg-[#6366f1] -z-10 transition-all duration-500"
          style={{ width: step === 0 ? '0%' : step === 1 ? '33%' : step === 2 ? '66%' : '85%' }}
        ></div>

        {[
          { num: 0, label: 'Chat' },
          { num: 1, label: 'Upload Poster' },
          { num: 2, label: 'Draw Zones' },
          { num: 3, label: 'Save Template' }
        ].map((s) => (
          <div key={s.num} className="flex flex-col items-center flex-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
              step > s.num ? 'bg-[#6366f1] text-white' : 
              step === s.num ? 'bg-[#6366f1] text-white ring-4 ring-[#6366f1]/20' : 
              'bg-gray-800 text-gray-500'
            }`}>
              {step > s.num ? <CheckCircle2 size={16} /> : s.num + 1}
            </div>
            <span className={`text-xs mt-2 font-medium ${step >= s.num ? 'text-white' : 'text-gray-500'}`}>
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-gray-200 font-sans pb-24">
      {step < 4 && <ProgressSteps />}

      <div className="max-w-[1000px] mx-auto px-4">
        
        {/* STEP 0: AI CHAT */}
        {step === 0 && (
          <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-180px)]">
            
            {/* LEFT: Chat Interface */}
            <div className="flex-1 bg-[#1a1a2e] rounded-xl border border-gray-800 shadow-xl flex flex-col overflow-hidden">
              <div className="bg-[#111827] px-6 py-4 border-b border-gray-800 flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <Sparkles className="text-[#6366f1] w-5 h-5" />
                  <h3 className="font-semibold text-white">Creative Director</h3>
                </div>
                <button 
                  onClick={() => setStep(1)} 
                  className="text-xs text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
                >
                  Skip Chat <ChevronDown className="-rotate-90 w-3 h-3" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-2xl px-5 py-3 ${
                      msg.role === 'user' 
                        ? 'bg-[#6366f1] text-white rounded-br-none' 
                        : 'bg-[#1f2937] text-gray-200 rounded-bl-none border border-gray-700'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-[#1f2937] rounded-2xl px-5 py-3 rounded-bl-none border border-gray-700">
                      <Loader2 className="w-4 h-4 animate-spin text-[#6366f1]" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="p-4 bg-[#111827] border-t border-gray-800">
                <form onSubmit={handleSendMessage} className="relative flex items-center">
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={e => setInputMessage(e.target.value)}
                    placeholder="Message the Creative Director..."
                    className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-full pl-5 pr-12 py-3 text-sm text-white outline-none transition-all"
                    disabled={loading}
                  />
                  <button 
                    type="submit"
                    disabled={loading || !inputMessage.trim()}
                    className="absolute right-2 p-2 bg-[#6366f1] hover:bg-[#4f46e5] disabled:opacity-50 text-white rounded-full transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </div>

            {/* RIGHT: Design Details Form */}
            <div className="w-full lg:w-[400px] flex flex-col gap-4">
              
              {/* Assumptions Card */}
              {Object.keys(assumptions).length > 0 && (
                <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-5 shadow-xl flex-shrink-0 max-h-[60%] overflow-y-auto custom-scrollbar">
                  <h4 className="text-sm font-semibold text-white mb-4 flex items-center justify-between">
                    Design Assumptions
                  </h4>
                  <div className="space-y-3">
                    {Object.entries(assumptions).map(([key, val]) => (
                      <div key={key}>
                        <label className="block text-[10px] font-bold text-gray-400 mb-1 uppercase tracking-wider">
                          {key.replace('_', ' ')}
                        </label>
                        <input
                          type="text"
                          value={val}
                          onChange={e => setAssumptions(prev => ({ ...prev, [key]: e.target.value }))}
                          className="w-full bg-[#111827] border border-gray-700 focus:border-[#6366f1] rounded p-2 text-xs text-gray-300 outline-none"
                        />
                      </div>
                    ))}
                    <div>
                      <label className="block text-[10px] font-bold text-gray-400 mb-1 uppercase tracking-wider mt-4">
                        Additional Visual Constraints
                      </label>
                      <textarea
                        value={userEdits}
                        onChange={e => setUserEdits(e.target.value)}
                        className="w-full bg-[#111827] border border-gray-700 focus:border-[#6366f1] rounded p-2 text-xs text-gray-300 outline-none resize-none"
                        rows={2}
                      />
                    </div>
                    <button 
                      onClick={handleRebuildPrompt}
                      disabled={loading}
                      className="w-full mt-2 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white text-xs font-semibold rounded transition-colors flex items-center justify-center gap-2"
                    >
                      <RefreshCw className="w-3 h-3" /> Rebuild Prompt
                    </button>
                  </div>
                </div>
              )}

              {/* Prompt Editor Card */}
              {(agentReady || generatedPrompt) && (
                <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-5 shadow-xl flex-1 flex flex-col">
                  <h4 className="text-sm font-semibold text-white mb-3">Image Generation Prompt</h4>
                  
                  <textarea
                    value={generatedPrompt}
                    onChange={e => setGeneratedPrompt(e.target.value)}
                    className="w-full flex-1 min-h-[100px] bg-[#111827] border border-gray-700 focus:border-[#6366f1] rounded-lg p-3 text-xs text-gray-300 outline-none resize-none mb-3"
                  />

                  <form onSubmit={handleRefinePrompt} className="flex gap-2 mb-4">
                    <input
                      type="text"
                      value={refinementInput}
                      onChange={e => setRefinementInput(e.target.value)}
                      placeholder="e.g. make it darker..."
                      className="flex-1 bg-[#111827] border border-gray-700 focus:border-[#6366f1] rounded p-2 text-xs text-gray-300 outline-none"
                    />
                    <button 
                      type="submit"
                      disabled={loading || !refinementInput.trim()}
                      className="px-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white text-xs font-semibold rounded transition-colors disabled:opacity-50"
                    >
                      Refine
                    </button>
                  </form>

                  {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

                  <button 
                    onClick={handleGenerateImage}
                    disabled={loading}
                    className="w-full py-3 bg-[#6366f1] hover:bg-[#4f46e5] disabled:opacity-50 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-2 shadow-lg shadow-[#6366f1]/20 mt-auto"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImageIcon className="w-4 h-4" />}
                    Generate Image 🚀
                  </button>
                </div>
              )}
            </div>

          </div>
        )}

        {/* STEP 1: UPLOAD (or Review AI Image) */}
        {step === 1 && (
          <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-8 shadow-xl">
            {!file ? (
              <label 
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                className="flex flex-col items-center justify-center w-full h-[400px] border-2 border-dashed border-[#6366f1] rounded-xl bg-[#111827] hover:bg-[#111827]/80 transition-colors cursor-pointer"
              >
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <CloudUpload className="w-12 h-12 text-[#6366f1] mb-4" />
                  <p className="mb-2 text-lg font-semibold text-white">Drag and drop your poster PNG here</p>
                  <p className="text-sm text-gray-500 mb-6">or</p>
                  <div className="px-6 py-2 border border-[#6366f1] text-[#6366f1] rounded-lg font-medium hover:bg-[#6366f1] hover:text-white transition-colors">
                    Browse Files
                  </div>
                  <p className="text-xs text-gray-500 mt-6">Supported: PNG, JPG up to 10MB</p>
                </div>
                <input type="file" className="hidden" accept="image/png, image/jpeg" onChange={(e) => e.target.files && handleFileChange(e.target.files[0])} />
              </label>
            ) : (
              <div className="flex flex-col items-center w-full">
                <div className="w-full h-[400px] bg-[#111827] rounded-xl border border-gray-800 flex items-center justify-center overflow-hidden p-4 relative group">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={imageUrl!} alt="preview" className="max-h-full max-w-full object-contain" />
                </div>
                
                <div className="mt-4 flex flex-col items-center">
                  <p className="text-white font-medium">{file.name}</p>
                  <p className="text-sm text-gray-500">{(file.size / (1024*1024)).toFixed(2)} MB</p>
                  <button onClick={() => setFile(null)} className="text-sm text-gray-500 hover:text-red-400 mt-1 transition-colors underline flex items-center gap-1">
                    <Undo className="w-3 h-3" /> Change file
                  </button>
                </div>

                <div className="flex gap-4 w-full mt-8">
                  <button onClick={() => setStep(0)} className="px-6 py-4 bg-[#111827] hover:bg-gray-800 border border-gray-700 text-gray-400 hover:text-white rounded-lg font-medium transition-colors">
                    ← Back to Chat
                  </button>
                  <button 
                    onClick={() => setStep(2)}
                    className="flex-1 py-4 bg-[#6366f1] hover:bg-[#4f46e5] text-white rounded-lg font-bold text-lg transition-colors shadow-lg shadow-[#6366f1]/20 flex justify-center items-center gap-2"
                  >
                    Continue to Draw Zones <ChevronDown className="-rotate-90" />
                  </button>
                </div>
              </div>
            )}
            
            {uploadError && <p className="text-red-400 text-sm mt-4 text-center">{uploadError}</p>}
          </div>
        )}

        {/* STEP 2: DRAW ZONES */}
        {step === 2 && imageUrl && (
          <div className="flex flex-col md:flex-row gap-6">
            {/* LEFT CANVAS */}
            <div className="w-full md:w-[60%] flex flex-col gap-2">
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-4 shadow-xl">
                <ZoneMapper 
                  imageUrl={imageUrl} 
                  imageNaturalWidth={imageSize.w} 
                  imageNaturalHeight={imageSize.h} 
                  zones={zones} 
                  onChange={handleZoneChange} 
                  onSelectZone={handleSelectZone} 
                />
              </div>
              <p className="text-gray-500 text-sm px-2 text-center md:text-left">
                Click and drag to draw a zone. Each zone becomes a text field on your poster.
              </p>
            </div>
            
            {/* RIGHT PANEL */}
            <div className="w-full md:w-[40%] flex flex-col h-full min-h-[500px]">
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-6 flex flex-col h-full shadow-xl">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="font-bold text-xl text-white">Zones</h3>
                  <span className="bg-[#1f2937] text-white px-3 py-1 rounded-full text-sm font-medium border border-gray-700">
                    {zones.length} drawn
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto pr-2 space-y-4 custom-scrollbar">
                  {zones.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-500 text-center px-4 opacity-70">
                      <PlusCircle className="w-12 h-12 mb-4 text-gray-600" />
                      <p>Draw your first zone on the poster →</p>
                    </div>
                  ) : (
                    zones.map((z, idx) => {
                      const conf = configs[z.id];
                      return (
                        <div 
                          key={z.id} 
                          className={`bg-[#1f2937] rounded-lg p-4 border transition-colors ${selectedZoneId === z.id ? 'border-[#6366f1]' : 'border-gray-800'}`}
                          onClick={() => handleSelectZone(z.id)}
                        >
                          <div className="flex justify-between items-start mb-3">
                            <span className="bg-[#111827] text-gray-400 w-6 h-6 rounded flex items-center justify-center text-xs font-bold">
                              {idx + 1}
                            </span>
                            <button onClick={(e) => { e.stopPropagation(); deleteZone(z.id); }} className="text-gray-500 hover:text-red-400 p-1">
                              <Trash2 size={16} />
                            </button>
                          </div>
                          
                          <div className="space-y-4">
                            <div>
                              <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Field ID</label>
                              <input 
                                type="text"
                                placeholder="e.g. name, heading, caption"
                                value={conf?.id || ''}
                                onChange={e => updateConfig(z.id, 'id', e.target.value)}
                                className="w-full bg-[#111827] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-3 py-2 text-sm text-white outline-none transition-all"
                              />
                            </div>
                            
                            <div className="flex items-center justify-between bg-[#111827] p-2 rounded-lg border border-gray-800">
                              <span className="text-sm text-gray-300" title="If enabled, AI will fill this automatically">
                                LLM can generate
                              </span>
                              <button 
                                onClick={() => updateConfig(z.id, 'llm_can_invent', !conf?.llm_can_invent)}
                                className={`w-10 h-5 rounded-full transition-colors relative ${conf?.llm_can_invent ? 'bg-[#6366f1]' : 'bg-gray-600'}`}
                              >
                                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${conf?.llm_can_invent ? 'left-5' : 'left-0.5'}`}></div>
                              </button>
                            </div>

                            <div className="font-mono text-[10px] text-gray-500 pt-2 border-t border-gray-800 flex justify-between">
                              <span>x: {z.x}</span>
                              <span>y: {z.y}</span>
                              <span>w: {z.width}</span>
                              <span>h: {z.height}</span>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>

                <div className="pt-6 mt-4 border-t border-gray-800 flex gap-3">
                  <button onClick={() => setStep(1)} className="px-4 py-2 text-gray-400 hover:text-white bg-[#111827] hover:bg-gray-800 border border-gray-700 rounded-lg transition-colors font-medium">
                    ← Back
                  </button>
                  <button 
                    onClick={() => setStep(3)}
                    disabled={!isValidStep2}
                    className="flex-1 px-4 py-2 bg-[#6366f1] hover:bg-[#4f46e5] disabled:opacity-50 disabled:bg-gray-700 text-white rounded-lg font-bold transition-colors flex justify-center items-center gap-2"
                  >
                    Continue to Save <ChevronDown className="-rotate-90 w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: SAVE */}
        {step === 3 && (
          <div className="flex flex-col md:flex-row gap-8">
            {/* LEFT DETAILS */}
            <div className="w-full md:w-[55%]">
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 p-8 shadow-xl">
                <h3 className="text-xl font-medium text-white mb-6">Template Details</h3>
                
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Category Folder</label>
                    <div className="relative">
                      <select 
                        value={category}
                        onChange={e => setCategory(e.target.value)}
                        className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg pl-4 pr-10 py-3 text-white outline-none appearance-none cursor-pointer transition-all"
                      >
                        {categories.map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                        ))}
                        <option value="create_new">+ Create New...</option>
                      </select>
                      <ChevronDown className="absolute right-3 top-3.5 text-gray-400 pointer-events-none w-5 h-5" />
                    </div>
                    {category === 'create_new' && (
                      <input 
                        type="text"
                        placeholder="New category name..."
                        value={newCategory}
                        onChange={e => setNewCategory(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                        className="w-full mt-3 bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all"
                      />
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Sub-category folder</label>
                    <input 
                      type="text" 
                      placeholder="e.g. holi, diwali, hiring_2026"
                      value={baseId} 
                      onChange={e => setBaseId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                      className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Brief description (Optional)</label>
                    <textarea 
                      placeholder="Describe what this template is for, or leave blank to let AI generate tags..."
                      value={hint} 
                      onChange={e => setHint(e.target.value)}
                      rows={3}
                      className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Occasion keywords</label>
                    <input 
                      type="text" 
                      placeholder="comma separated..."
                      value={keywords} 
                      onChange={e => setKeywords(e.target.value)}
                      className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all"
                    />
                  </div>
                </div>

                <hr className="border-gray-800 my-8" />
                
                {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

                <div className="flex gap-4">
                  <button 
                    onClick={() => setStep(2)} 
                    disabled={loading}
                    className="px-6 py-3 text-gray-400 hover:text-white bg-transparent hover:bg-[#1f2937] border border-gray-700 rounded-lg transition-colors font-medium whitespace-nowrap"
                  >
                    ← Back
                  </button>
                  <button 
                    onClick={handleSubmit} 
                    disabled={loading || !baseId || (category === 'create_new' && !newCategory)}
                    className="flex-1 px-4 py-3 bg-[#6366f1] hover:bg-[#4f46e5] disabled:opacity-50 text-white rounded-lg font-bold transition-colors shadow-lg shadow-[#6366f1]/20 flex justify-center items-center gap-2"
                  >
                    {loading ? (
                      <><Loader2 className="animate-spin w-5 h-5" /> Generating tags...</>
                    ) : (
                      '🏷 Generate Tags and Save'
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* RIGHT PREVIEW */}
            <div className="w-full md:w-[45%] flex flex-col gap-6">
              <div className="bg-[#1a1a2e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">
                <div className="bg-[#111827] px-6 py-4 border-b border-gray-800">
                  <h3 className="font-semibold text-white">Template Preview</h3>
                </div>
                
                <div className="bg-[#0a0a0a] p-4 flex justify-center border-b border-gray-800">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={imageUrl!} alt="preview" className="max-h-[300px] object-contain rounded border border-gray-800" />
                </div>
                
                <div className="p-6">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Zones Summary</h4>
                  <div className="space-y-3">
                    {zones.map(z => {
                      const conf = configs[z.id];
                      return (
                        <div key={z.id} className="flex items-center justify-between bg-[#1f2937] rounded-lg p-3 border border-gray-800">
                          <span className="bg-[#6366f1] text-white text-xs font-bold px-2 py-1 rounded">
                            {conf?.id || z.id}
                          </span>
                          <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded ${conf?.llm_can_invent ? 'bg-teal-500/10 text-teal-400' : 'bg-orange-500/10 text-orange-400'}`}>
                            {conf?.llm_can_invent ? 'AI generates' : 'From Excel'}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: SUCCESS */}
        {step === 4 && successData && (
          <div className="max-w-2xl mx-auto bg-[#1a1a2e] rounded-2xl border border-gray-800 p-10 shadow-2xl flex flex-col items-center text-center animate-in fade-in zoom-in duration-300">
            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-6">
              <CheckCircle2 className="w-10 h-10 text-green-500" />
            </div>
            <h2 className="text-3xl font-bold text-white mb-2">Template saved successfully!</h2>
            <p className="text-gray-400 mb-8">Your template is now indexed and ready to use</p>
            <div className="flex flex-col sm:flex-row gap-4 w-full">
              <button 
                onClick={() => router.push('/')}
                className="flex-1 py-3 bg-[#6366f1] hover:bg-[#4f46e5] text-white rounded-lg font-bold transition-colors"
              >
                Generate a poster →
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
