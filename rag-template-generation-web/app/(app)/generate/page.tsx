"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getConversationMessages, getConversationImage } from "@/lib/api";
import {
  Sparkles,
  Download,
  Upload,
  RefreshCw,
  AlertCircle,
  Image as ImageIcon,
  Layers,
  Sliders,
  Type,
  Move,
  Palette,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const FONT_OPTIONS = [
  "(Template default)",
  "Poppins",
  "NotoSans",
  "Arial",
  "Times New Roman",
  "Georgia",
  "Calibri",
  "Verdana",
  "Trebuchet MS",
];

interface OverlayLayer {
  id: string;
  type: "text" | "image";
  placeholder: string;
  box: { x: number; y: number; width: number; height: number };
  style?: Record<string, any>;
}

function SingleGenerateContent() {
  const searchParams = useSearchParams();
  const convoId = searchParams.get("id");

  const [prompt, setPrompt] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [folder, setFolder] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);

  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Response States
  const [posterUrl, setPosterUrl] = useState<string | null>(null);
  const [ambiguousMatches, setAmbiguousMatches] = useState<any[] | null>(null);
  const [galleryTemplates, setGalleryTemplates] = useState<any[] | null>(null);
  const [missingFields, setMissingFields] = useState<string[] | null>(null);

  // Dynamic values, layers, and canvas geometry
  const [storedValues, setStoredValues] = useState<Record<string, string>>({});
  const [layers, setLayers] = useState<OverlayLayer[]>([]);
  const [canvas, setCanvas] = useState<{ width: number; height: number }>({
    width: 1024,
    height: 1536,
  });

  // Overrides & Caption AI state
  const [layoutOverrides, setLayoutOverrides] = useState<
    Record<string, { x: number; y: number }>
  >({});
  const [styleOverrides, setStyleOverrides] = useState<
    Record<string, Record<string, any>>
  >({});
  const [customCaptionPrompt, setCustomCaptionPrompt] = useState("");
  const [fieldPrompts, setFieldPrompts] = useState<Record<string, string>>({});
  const [isEditorExpanded, setIsEditorExpanded] = useState(true);


  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Load conversation history if convoId present
  useEffect(() => {
    if (!convoId) return;

    const loadConvoHistory = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getConversationMessages(convoId);
        if (data.messages && data.messages.length > 0) {
          const userMsg = data.messages.find((m) => m.role === "user");
          if (userMsg) setPrompt(userMsg.content);

          const assistantMsg = data.messages.find(
            (m) => m.role === "assistant" && m.output_file_path
          );
          if (assistantMsg) {
            try {
              const blob = await getConversationImage(convoId);
              setPosterUrl(URL.createObjectURL(blob));
            } catch (imgErr) {
              console.warn("Could not fetch conversation image output:", imgErr);
            }
          }
        }
      } catch (err: any) {
        console.warn("Conversation history no longer exists:", err.message);
        router.replace("/generate");
      } finally {
        setLoading(false);
      }
    };

    loadConvoHistory();
  }, [convoId]);

  const handleGenerate = async (
    overrideFolder?: string,
    overrideTemplateId?: string,
    additionalInputs?: Record<string, string>,
    regenCaptionPrompt?: string
  ) => {
    if (!prompt.trim()) {
      setError("Please enter a prompt describing the poster you want to generate.");
      return;
    }

    setLoading(true);
    setError(null);
    setAmbiguousMatches(null);
    setGalleryTemplates(null);
    setMissingFields(null);

    try {
      const formData = new FormData();
      formData.append("prompt", prompt.trim());

      const targetFolder = overrideFolder || folder;
      const targetTemplateId = overrideTemplateId || templateId;

      if (targetFolder) formData.append("folder", targetFolder);
      if (targetTemplateId) formData.append("template_id", targetTemplateId);
      if (imageFile) formData.append("image", imageFile);

      // Append Layout & Style overrides if non-empty
      if (Object.keys(layoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(layoutOverrides));
      }

      if (Object.keys(styleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(styleOverrides));
      }

      if (Object.keys(fieldPrompts).length > 0) {
        formData.append("field_prompts", JSON.stringify(fieldPrompts));
      }

      // Caption AI prompt override if user clicked Regenerate Caption
      if (regenCaptionPrompt) {
        formData.append("caption_prompt", regenCaptionPrompt);
      } else if (customCaptionPrompt) {
        formData.append("caption_prompt", customCaptionPrompt);
      }

      // Merge stored layer text values and additional inputs
      const mergedInputs = { ...storedValues, ...(additionalInputs || {}) };
      Object.entries(mergedInputs).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          formData.append(k, v);
        }
      });


      // Request with ?json=true to get metadata + base64 image
      const res = await fetch("/api/proxy/generate?json=true", {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
        body: formData,
      });

      const contentType = res.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const json = await res.json();
        if (json.status === "success") {
          setPosterUrl(`data:image/png;base64,${json.image}`);
          if (json.canvas) setCanvas(json.canvas);
          if (json.overlay_layers) setLayers(json.overlay_layers);
          if (json.folder) setFolder(json.folder);
          if (json.template_id) setTemplateId(json.template_id);

          if (json.overlay_values) {
            setStoredValues((prev) => ({
              ...prev,
              ...json.overlay_values,
            }));
          }
        } else if (json.status === "ambiguous") {
          setAmbiguousMatches(json.matches || []);
        } else if (json.status === "gallery") {
          setFolder(json.folder);
          setGalleryTemplates(json.templates || []);
        } else if (json.status === "needs_input") {
          setMissingFields(json.missing_fields || []);
          if (json.folder) setFolder(json.folder);
          if (json.template_id) setTemplateId(json.template_id);
          if (json.overlay_values) {
            setStoredValues((prev) => ({ ...prev, ...json.overlay_values }));
          }
        } else if (json.status === "no_match") {
          setError(json.message || "No template found for your request.");
        } else if (json.detail) {
          setError(
            typeof json.detail === "string"
              ? json.detail
              : JSON.stringify(json.detail)
          );
        }
      } else if (contentType.includes("image/")) {
        const blob = await res.blob();
        setPosterUrl(URL.createObjectURL(blob));
      } else {
        const text = await res.text();
        setError(text || "Failed to generate poster.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate poster.");
    } finally {
      setLoading(false);
    }
  };

  const handleLayoutChange = (lid: string, field: "x" | "y", val: number) => {
    const origBox = layers.find((l) => l.id === lid)?.box || { x: 0, y: 0 };
    setLayoutOverrides((prev) => ({
      ...prev,
      [lid]: {
        x: field === "x" ? val : (prev[lid]?.x ?? origBox.x),
        y: field === "y" ? val : (prev[lid]?.y ?? origBox.y),
      },
    }));
  };

  const handleStyleChange = (lid: string, key: string, val: any) => {
    setStyleOverrides((prev) => {
      const currentLayerStyle = { ...(prev[lid] || {}) };
      if (val === "" || val === "(Template default)" || val === null) {
        delete currentLayerStyle[key];
      } else {
        currentLayerStyle[key] = val;
      }
      return {
        ...prev,
        [lid]: currentLayerStyle,
      };
    });
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-indigo-400" />
          Single Poster Generator & Live Editor
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Describe your poster, let AI select templates and write copy, then tweak positions and fonts with live preview.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Controls & Form */}
        <div className="lg:col-span-6 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
            {/* Prompt Input */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Poster Prompt / Event Description *
              </label>
              <textarea
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g., Generate a festive Happy Dussehra greeting poster with customer photo and wish line..."
                className="w-full p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm resize-none"
              />
            </div>

            {/* Optional Photo Upload */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                User Photo (Optional)
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 bg-slate-950/40 rounded-xl p-4 cursor-pointer transition-all flex flex-col items-center justify-center text-center gap-2"
              >
                <Upload className="h-5 w-5 text-slate-500" />
                {imageFile ? (
                  <span className="text-xs text-indigo-400 font-medium">
                    {imageFile.name}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">
                    Click to attach photo for image placeholder zones
                  </span>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              onClick={() => handleGenerate()}
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition-all active:scale-[0.99] disabled:opacity-50 text-sm"
            >
              {loading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Processing & Rendering Live Preview...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Generate Poster</span>
                </>
              )}
            </button>
          </div>

          {/* Ambiguous Disambiguation Selection */}
          {ambiguousMatches && ambiguousMatches.length > 0 && (
            <div className="bg-amber-950/30 border border-amber-800/50 rounded-2xl p-6 space-y-4">
              <h3 className="text-sm font-semibold text-amber-200 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-amber-400" />
                Multiple Matching Poster Categories Found
              </h3>
              <p className="text-xs text-amber-300/80">
                Please select the specific category for your poster:
              </p>
              <div className="space-y-2">
                {ambiguousMatches.map((m: any) => (
                  <button
                    key={m.folder}
                    onClick={() => {
                      setFolder(m.folder);
                      handleGenerate(m.folder);
                    }}
                    className="w-full text-left p-3 rounded-xl bg-slate-900 border border-amber-900/40 hover:border-amber-500 text-slate-200 hover:text-white flex items-center justify-between text-xs font-medium transition-all"
                  >
                    <span>{m.display_name || m.folder}</span>
                    <span className="text-[10px] text-amber-400">Select →</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Template Gallery Selection */}
          {galleryTemplates && galleryTemplates.length > 0 && (
            <div className="bg-indigo-950/30 border border-indigo-800/50 rounded-2xl p-6 space-y-4">
              <h3 className="text-sm font-semibold text-indigo-200 flex items-center gap-2">
                <Layers className="h-4 w-4 text-indigo-400" />
                Select a Template Layout
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {galleryTemplates.map((t: any) => (
                  <button
                    key={t.template_id}
                    onClick={() => {
                      setTemplateId(t.template_id);
                      handleGenerate(folder || undefined, t.template_id);
                    }}
                    className="p-3 rounded-xl bg-slate-900 border border-slate-800 hover:border-indigo-500 text-left text-xs space-y-1 transition-all"
                  >
                    <p className="font-semibold text-slate-200">{t.template_id}</p>
                    <p className="text-[10px] text-slate-400 line-clamp-2">
                      {t.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Missing Fields Input Form */}
          {missingFields && missingFields.length > 0 && (
            <div className="bg-slate-900 border border-indigo-500/50 rounded-2xl p-6 space-y-4 shadow-xl">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-indigo-400" />
                Required Template Information
              </h3>
              <p className="text-xs text-slate-400">
                This template requires specific details before rendering:
              </p>
              <div className="space-y-3">
                {missingFields.map((field) => (
                  <div key={field}>
                    <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                      {field.replace(/_/g, " ")}
                    </label>
                    <input
                      type="text"
                      value={storedValues[field] || ""}
                      onChange={(e) =>
                        setStoredValues({ ...storedValues, [field]: e.target.value })
                      }
                      placeholder={`Enter ${field.replace(/_/g, " ")}`}
                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={() =>
                  handleGenerate(folder || undefined, templateId || undefined)
                }
                className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl text-xs transition-all mt-2"
              >
                Submit & Render Poster
              </button>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs leading-relaxed">
              {error}
            </div>
          )}
        </div>

        {/* Right Output & Interactive Live Editor */}
        <div className="lg:col-span-6 flex flex-col space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-center items-center relative min-h-[450px] shadow-xl">
            {loading ? (
              <div className="flex flex-col items-center gap-3 text-slate-400">
                <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
                <p className="text-xs font-medium">Rendering poster live preview...</p>
              </div>
            ) : posterUrl ? (
              <div className="flex flex-col items-center gap-4 w-full">
                <div className="relative rounded-xl overflow-hidden border border-slate-800 shadow-2xl max-h-[500px] flex justify-center">
                  {/* eslint-disable-next-html-element-suppression */}
                  <img
                    src={posterUrl}
                    alt="Generated Poster"
                    className="max-h-[500px] w-auto object-contain rounded-xl"
                  />
                </div>
                <a
                  href={posterUrl}
                  download="poster.png"
                  className="py-2.5 px-5 bg-slate-800 hover:bg-slate-700 text-white font-medium rounded-xl border border-slate-700 shadow-md text-xs flex items-center gap-2 transition-all"
                >
                  <Download className="h-4 w-4" />
                  <span>Download High-Res PNG</span>
                </a>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-slate-600 text-center p-6">
                <ImageIcon className="h-12 w-12 stroke-[1.5]" />
                <p className="text-xs font-medium text-slate-400">No poster generated yet</p>
                <p className="text-[11px] text-slate-600 max-w-xs">
                  Fill in the prompt on the left and click "Generate Poster" to view your result here.
                </p>
              </div>
            )}
          </div>

          {/* Interactive Live Editor Panel */}
          {layers.length > 0 && posterUrl && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <button
                onClick={() => setIsEditorExpanded(!isEditorExpanded)}
                className="w-full flex items-center justify-between text-left focus:outline-none"
              >
                <div className="flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-sm font-semibold text-white">
                    Adjust Placeholder Positions & Styling
                  </h3>
                </div>
                {isEditorExpanded ? (
                  <ChevronUp className="h-4 w-4 text-slate-400" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                )}
              </button>

              {isEditorExpanded && (
                <div className="space-y-6 pt-2 border-t border-slate-800/80">
                  <p className="text-xs text-slate-400">
                    Reposition placeholder zones using X/Y coordinate sliders, modify text contents directly, or ask AI to write custom captions.
                  </p>

                  <div className="space-y-5 max-h-[500px] overflow-y-auto pr-1">
                    {layers
                      .filter((layer) => !!layer.id)
                      .map((layer) => {

                        const lid = layer.id;
                        const isText = layer.type === "text";
                        const canInvent = !!(layer as any).llm_can_invent;
                        const currentVal = storedValues[lid] || "";
                        const currentLayout = layoutOverrides[lid] || layer.box;
                        const currentStyle = styleOverrides[lid] || {};

                        return (
                          <div
                            key={lid}
                            className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-4"
                          >
                            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                              <span className="text-xs font-bold text-indigo-400 flex items-center gap-1.5 capitalize">
                                {isText ? <Type className="h-3.5 w-3.5" /> : <ImageIcon className="h-3.5 w-3.5" />}
                                Placeholder: {lid}
                                {canInvent ? (
                                  <span className="px-2 py-0.5 bg-indigo-950 text-indigo-400 border border-indigo-800 text-[10px] rounded-md font-medium capitalize">
                                    AI Inventable
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 bg-slate-900 text-slate-400 border border-slate-800 text-[10px] rounded-md font-medium capitalize">
                                    Fixed / Extracted
                                  </span>
                                )}
                              </span>
                              <span className="text-[10px] font-mono text-slate-500">
                                ({currentLayout.x}px, {currentLayout.y}px)
                              </span>
                            </div>

                            {/* Text / Caption Editing */}
                            {isText && (
                              <div className="space-y-3">
                                {lid === "caption" ? (
                                  <>
                                    <div>
                                      <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                                        Section 1 — Type your own caption
                                      </label>
                                      <textarea
                                        rows={2}
                                        value={currentVal}
                                        onChange={(e) =>
                                          setStoredValues({
                                            ...storedValues,
                                            caption: e.target.value,
                                          })
                                        }
                                        placeholder="Type exact caption text to place on poster..."
                                        className="w-full p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                      />
                                    </div>

                                    <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg space-y-2">
                                      <label className="block text-[11px] font-semibold text-slate-300">
                                        Section 2 — Ask AI to write/regenerate caption
                                      </label>
                                      <div className="flex gap-2">
                                        <input
                                          type="text"
                                          value={customCaptionPrompt}
                                          onChange={(e) =>
                                            setCustomCaptionPrompt(e.target.value)
                                          }
                                          placeholder="e.g. Write a festive greeting in Hindi"
                                          className="flex-1 p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                        />
                                        <button
                                          onClick={() => {
                                            const nextStored = { ...storedValues };
                                            delete nextStored.caption;
                                            setStoredValues(nextStored);
                                            handleGenerate(
                                              folder || undefined,
                                              templateId || undefined,
                                              undefined,
                                              customCaptionPrompt
                                            );
                                          }}
                                          className="py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-all"
                                        >
                                          Regenerate
                                        </button>
                                      </div>
                                    </div>
                                  </>
                                ) : (
                                  <div className="space-y-3">
                                    <div>
                                      <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                                        Direct Custom Value ({lid})
                                      </label>
                                      <input
                                        type="text"
                                        value={currentVal}
                                        onChange={(e) =>
                                          setStoredValues({
                                            ...storedValues,
                                            [lid]: e.target.value,
                                          })
                                        }
                                        placeholder={`Type exact custom text for ${lid}...`}
                                        className="w-full p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-1 focus:ring-indigo-500"
                                      />
                                      <p className="text-[10px] text-slate-500 mt-1">
                                        Overrides AI generation if typed.
                                      </p>
                                    </div>

                                    {/* AI Generation Instruction Prompt — ONLY for llm_can_invent == true */}
                                    {(layer as any).llm_can_invent && (

                                      <div className="border-t border-slate-800/80 pt-2">
                                        <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                                          AI Generation Instruction Prompt ({lid})
                                        </label>
                                        <input
                                          type="text"
                                          value={fieldPrompts[lid] || ""}
                                          onChange={(e) =>
                                            setFieldPrompts({
                                              ...fieldPrompts,
                                              [lid]: e.target.value,
                                            })
                                          }
                                          placeholder={`e.g. Write a creative ${lid} in Hindi...`}
                                          className="w-full p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-1 focus:ring-indigo-500"
                                        />
                                        <p className="text-[10px] text-slate-500 mt-1">
                                          Prompt for AI to generate content for this field.
                                        </p>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}


                            {/* Position Sliders (X, Y) */}
                            <div className="space-y-3 pt-2">
                              <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                                <Move className="h-3 w-3" /> Position Coordinates (Pixels)
                              </span>
                              <div className="grid grid-cols-2 gap-4">
                                {/* X Position */}
                                <div className="space-y-1">
                                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                                    <span>X Axis</span>
                                    <input
                                      type="number"
                                      min={0}
                                      max={canvas.width}
                                      value={currentLayout.x}
                                      onChange={(e) =>
                                        handleLayoutChange(
                                          lid,
                                          "x",
                                          parseInt(e.target.value) || 0
                                        )
                                      }
                                      className="w-16 p-1 bg-slate-900 border border-slate-800 rounded text-center text-xs font-mono text-slate-200"
                                    />
                                  </div>
                                  <input
                                    type="range"
                                    min={0}
                                    max={canvas.width}
                                    value={currentLayout.x}
                                    onChange={(e) =>
                                      handleLayoutChange(
                                        lid,
                                        "x",
                                        parseInt(e.target.value) || 0
                                      )
                                    }
                                    className="w-full accent-indigo-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                                  />
                                </div>

                                {/* Y Position */}
                                <div className="space-y-1">
                                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                                    <span>Y Axis</span>
                                    <input
                                      type="number"
                                      min={0}
                                      max={canvas.height}
                                      value={currentLayout.y}
                                      onChange={(e) =>
                                        handleLayoutChange(
                                          lid,
                                          "y",
                                          parseInt(e.target.value) || 0
                                        )
                                      }
                                      className="w-16 p-1 bg-slate-900 border border-slate-800 rounded text-center text-xs font-mono text-slate-200"
                                    />
                                  </div>
                                  <input
                                    type="range"
                                    min={0}
                                    max={canvas.height}
                                    value={currentLayout.y}
                                    onChange={(e) =>
                                      handleLayoutChange(
                                        lid,
                                        "y",
                                        parseInt(e.target.value) || 0
                                      )
                                    }
                                    className="w-full accent-indigo-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
                                  />
                                </div>
                              </div>
                            </div>

                            {/* Typography Styling Overrides */}
                            {isText && (
                              <div className="space-y-3 pt-2">
                                <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                                  <Palette className="h-3 w-3" /> Typography & Style Overrides
                                </span>

                                <div className="grid grid-cols-2 gap-3">
                                  {/* Font Family */}
                                  <div>
                                    <label className="block text-[10px] text-slate-400 mb-1">
                                      Font Family
                                    </label>
                                    <select
                                      value={currentStyle.font_family || "(Template default)"}
                                      onChange={(e) =>
                                        handleStyleChange(lid, "font_family", e.target.value)
                                      }
                                      className="w-full p-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:ring-1 focus:ring-indigo-500"
                                    >
                                      {FONT_OPTIONS.map((f) => (
                                        <option key={f} value={f}>
                                          {f}
                                        </option>
                                      ))}
                                    </select>
                                  </div>

                                  {/* Font Weight */}
                                  <div>
                                    <label className="block text-[10px] text-slate-400 mb-1">
                                      Font Weight
                                    </label>
                                    <select
                                      value={currentStyle.font_weight || "(Template default)"}
                                      onChange={(e) =>
                                        handleStyleChange(lid, "font_weight", e.target.value)
                                      }
                                      className="w-full p-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:ring-1 focus:ring-indigo-500"
                                    >
                                      <option value="(Template default)">(Template default)</option>
                                      <option value="bold">Bold</option>
                                      <option value="regular">Normal</option>
                                    </select>
                                  </div>

                                  {/* Font Size */}
                                  <div>
                                    <label className="block text-[10px] text-slate-400 mb-1">
                                      Font Size (px)
                                    </label>
                                    <input
                                      type="number"
                                      placeholder="Default"
                                      value={currentStyle.font_size || ""}
                                      onChange={(e) =>
                                        handleStyleChange(
                                          lid,
                                          "font_size",
                                          e.target.value ? parseInt(e.target.value) : ""
                                        )
                                      }
                                      className="w-full p-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200"
                                    />
                                  </div>

                                  {/* Color Picker */}
                                  <div>
                                    <label className="block text-[10px] text-slate-400 mb-1">
                                      Text Color
                                    </label>
                                    <div className="flex gap-2 items-center">
                                      <input
                                        type="color"
                                        value={currentStyle.color || "#FFFFFF"}
                                        onChange={(e) =>
                                          handleStyleChange(lid, "color", e.target.value)
                                        }
                                        className="h-8 w-10 bg-transparent border-0 cursor-pointer"
                                      />
                                      <input
                                        type="text"
                                        value={currentStyle.color || ""}
                                        onChange={(e) =>
                                          handleStyleChange(lid, "color", e.target.value)
                                        }
                                        placeholder="#FFFFFF"
                                        className="flex-1 p-1.5 bg-slate-900 border border-slate-800 rounded text-xs font-mono text-slate-200"
                                      />
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>

                  {/* Apply Changes & Re-render Live Preview Button */}
                  <button
                    onClick={() =>
                      handleGenerate(folder || undefined, templateId || undefined)
                    }
                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 transition-all mt-4"
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span>Apply Adjustments & Re-render Live Preview</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SingleGeneratePage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-slate-400 text-xs">
          Loading poster generator...
        </div>
      }
    >
      <SingleGenerateContent />
    </Suspense>
  );
}
