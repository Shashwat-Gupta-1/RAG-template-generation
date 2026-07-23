"use client";

import React, { useState, useRef, useEffect } from 'react';
import ZoneMapper, { Zone } from '@/components/ZoneMapper';
import { useRouter } from 'next/navigation';
import { CloudUpload, Trash2, Loader2, CheckCircle2, ChevronDown, PlusCircle } from 'lucide-react';

export default function AddTemplatePage() {
  const router = useRouter();
  
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState({ w: 0, h: 0 });
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [configs, setConfigs] = useState<Record<string, any>>({});
  
  // Submit state
  const [categories, setCategories] = useState<string[]>(['festival', 'hr', 'promotional', 'grand_opening']);
  const [category, setCategory] = useState('festival');
  const [newCategory, setNewCategory] = useState('');
  const [baseId, setBaseId] = useState('');
  const [hint, setHint] = useState('');
  const [keywords, setKeywords] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  // File Upload Logic
  const handleFileChange = (f: File | null) => {
    setUploadError(null);
    if (!f) return;

    if (!['image/png', 'image/jpeg'].includes(f.type)) {
      setUploadError("Please upload a PNG or JPG file under 10MB");
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setUploadError("Please upload a PNG or JPG file under 10MB");
      return;
    }

    setFile(f);
    const url = URL.createObjectURL(f);
    setImageUrl(url);
    
    const img = new Image();
    img.onload = () => {
      setImageSize({ w: img.width, h: img.height });
    };
    img.src = url;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  // Zone Logic
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
    // Validate ID: lowercase, no spaces
    if (key === 'id') {
      value = value.toLowerCase().replace(/\s+/g, '_');
    }
    setConfigs(prev => ({
      ...prev,
      [id]: {
        ...prev[id],
        [key]: value
      }
    }));
  };

  const deleteZone = (id: string) => {
    const newZones = zones.filter(z => z.id !== id);
    setZones(newZones);
    if (selectedZoneId === id) setSelectedZoneId(null);
  };

  // Validation
  const isValidStep2 = zones.length > 0 && zones.every(z => {
    const conf = configs[z.id];
    return conf && conf.id && conf.id.trim() !== '';
  });

  const handleSubCategoryChange = (val: string) => {
    // lowercase, underscores, no spaces, no special chars
    const cleaned = val.toLowerCase().replace(/[^a-z0-9_]/g, '');
    setBaseId(cleaned);
  };

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
        return {
          ...conf,
          id: conf.id || z.id,
          x: z.x,
          y: z.y,
          width: z.width,
          height: z.height,
        };
      });

      const overlayData = {
        canvas: { width: imageSize.w, height: imageSize.h },
        overlay_layers
      };

      const formData = new FormData();
      formData.append('image', file);
      formData.append('overlay_data', JSON.stringify(overlayData));
      formData.append('category', finalCategory);
      formData.append('base_id', baseId);
      
      // Combine hint and keywords
      const fullHint = `${hint}\nKeywords: ${keywords}`;
      formData.append('hint', fullHint);

      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/templates/add", {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to add template");

      setSuccessData({
        template_id: data.template_id,
        folder_path: data.folder_path,
        // In a real app we'd get tags/desc back from the API to display
        tags: keywords.split(',').map(k => k.trim()).filter(k => k),
        description: hint
      });
      setStep(4); // Success step
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Steps Progress UI
  const ProgressSteps = () => (
    <div className="sticky top-0 z-10 bg-[#0a0a0a]/80 backdrop-blur-md py-6 mb-8 border-b border-white/5">
      <div className="flex items-center justify-center max-w-[600px] mx-auto relative">
        <div className="absolute top-[15px] left-[15%] right-[15%] h-[2px] bg-gray-800 -z-10"></div>
        <div 
          className="absolute top-[15px] left-[15%] h-[2px] bg-[#6366f1] -z-10 transition-all duration-500"
          style={{ width: step === 1 ? '0%' : step === 2 ? '50%' : '70%' }}
        ></div>

        {[
          { num: 1, label: 'Upload Poster' },
          { num: 2, label: 'Draw Zones' },
          { num: 3, label: 'Save Template' }
        ].map((s, i) => (
          <div key={s.num} className="flex flex-col items-center flex-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
              step > s.num ? 'bg-[#6366f1] text-white' : 
              step === s.num ? 'bg-[#6366f1] text-white ring-4 ring-[#6366f1]/20' : 
              'bg-gray-800 text-gray-500'
            }`}>
              {step > s.num ? <CheckCircle2 size={16} /> : s.num}
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

      <div className="max-w-[900px] mx-auto px-4">
        
        {/* STEP 1: UPLOAD */}
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
                  <button onClick={() => setFile(null)} className="text-sm text-gray-500 hover:text-red-400 mt-1 transition-colors underline">Change file</button>
                </div>

                <button 
                  onClick={() => setStep(2)}
                  className="w-full mt-8 py-4 bg-[#6366f1] hover:bg-[#4f46e5] text-white rounded-lg font-bold text-lg transition-colors shadow-lg shadow-[#6366f1]/20 flex justify-center items-center gap-2"
                >
                  Continue to Draw Zones <ChevronDown className="-rotate-90" />
                </button>
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

                <div className="flex-1 overflow-y-auto pr-2 space-y-4">
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
                      onChange={e => handleSubCategoryChange(e.target.value)}
                      className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all"
                    />
                    <p className="text-xs text-gray-500 mt-1.5">This becomes the folder name — use lowercase, no spaces, use underscores</p>
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
                      placeholder="holi, rang, gulal, festival of colors, होली"
                      value={keywords} 
                      onChange={e => setKeywords(e.target.value)}
                      className="w-full bg-[#1f2937] border border-gray-700 focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] rounded-lg px-4 py-3 text-white outline-none transition-all"
                    />
                    <p className="text-xs text-gray-500 mt-1.5">Comma separated. Include Hindi words and alternate spellings for better search.</p>
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
                    ← Back to Draw Zones
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
                          <span className="text-[10px] font-mono text-gray-500">
                            x:{z.x} y:{z.y} w:{z.width} h:{z.height}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              <div className="bg-[#111827] rounded-xl border border-gray-800 p-6 shadow-xl">
                <h4 className="text-sm font-semibold text-white mb-4">What happens when you save</h4>
                <ul className="space-y-3">
                  {[
                    `Template saved to templates/${category}/${baseId}/`,
                    'overlay.json created with your zones',
                    'AI generates description and tags for search',
                    'Template indexed into ChromaDB automatically',
                    'Available immediately in poster generation'
                  ].map((text, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                      <CheckCircle2 className="w-4 h-4 text-[#6366f1] flex-shrink-0 mt-0.5" />
                      {text}
                    </li>
                  ))}
                </ul>
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
            
            <div className="w-full bg-[#111827] rounded-xl p-6 border border-gray-800 mb-8 text-left">
              <p className="text-sm text-gray-300 italic border-l-2 border-[#6366f1] pl-4 mb-6">
                "{successData.description}"
              </p>
              
              <div className="flex flex-wrap gap-2">
                {successData.tags.map((tag: string, i: number) => (
                  <span key={i} className="bg-gray-800 text-gray-300 text-xs px-3 py-1.5 rounded-full border border-gray-700">
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 w-full">
              <button 
                onClick={() => router.push('/')}
                className="flex-1 py-3 bg-[#6366f1] hover:bg-[#4f46e5] text-white rounded-lg font-bold transition-colors"
              >
                Generate a poster with this template →
              </button>
              <button 
                onClick={() => window.location.reload()}
                className="flex-1 py-3 bg-transparent border border-[#6366f1] text-[#6366f1] hover:bg-[#6366f1]/10 rounded-lg font-bold transition-colors"
              >
                Add another template
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
