"use client";

import { useState, useEffect, useRef, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useTabState } from "@/context/TabStateContext";
import { getConversationMessages, getConversationImage } from "@/lib/api";
import {
  Sparkles,
  Download,
  Upload,
  RefreshCw,
  AlertCircle,
  Image as ImageIcon,
  Layers,
  Check,
} from "lucide-react";
import ZoneEditor, { DrawnZone, RequiredField } from "@/components/ZoneEditor";
import TemplateSelectionList from "@/components/TemplateSelectionList";

interface OverlayLayer {
  id: string;
  type: "text" | "image";
  placeholder: string;
  box: { x: number; y: number; width: number; height: number };
  style?: Record<string, any>;
  llm_can_invent?: boolean;
}

function SingleGenerateContent() {
  const searchParams = useSearchParams();
  const convoId = searchParams.get("id");

  const router = useRouter();
  const { state, updateState, resetState } = useTabState("single");

  const prompt = state.prompt ?? "";
  const setPrompt = (val: string) => updateState({ prompt: val });

  const imageFile = state.imageFile ?? null;
  const setImageFile = (val: File | null) => updateState({ imageFile: val });

  const folder = state.folder ?? null;
  const setFolder = (val: string | null) => updateState({ folder: val });

  const templateId = state.templateId ?? null;
  const setTemplateId = (val: string | null) => updateState({ templateId: val });

  const posterUrl = state.posterUrl ?? null;
  const setPosterUrl = (val: string | null) => updateState({ posterUrl: val });

  const storedValues = state.storedValues ?? {};
  const setStoredValues = (val: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => {
    updateState({ storedValues: val });
  };

  const layers: OverlayLayer[] = state.layers ?? [];
  const setLayers = (val: OverlayLayer[] | ((prev: OverlayLayer[]) => OverlayLayer[])) => updateState({ layers: val });

  const layoutOverrides = state.layoutOverrides ?? {};
  const setLayoutOverrides = (val: Record<string, Record<string, any>> | ((prev: Record<string, Record<string, any>>) => Record<string, Record<string, any>>)) => updateState({ layoutOverrides: val });

  const styleOverrides = state.styleOverrides ?? {};
  const setStyleOverrides = (val: Record<string, Record<string, any>> | ((prev: Record<string, Record<string, any>>) => Record<string, Record<string, any>>)) => updateState({ styleOverrides: val });

  const customCaptionPrompt = state.customCaptionPrompt ?? "";
  const setCustomCaptionPrompt = (val: string) => updateState({ customCaptionPrompt: val });

  const fieldPrompts = state.fieldPrompts ?? {};
  const setFieldPrompts = (val: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => updateState({ fieldPrompts: val });

  const zoneEditorMode = state.zoneEditorMode ?? false;
  const setZoneEditorMode = (val: boolean) => updateState({ zoneEditorMode: val });

  const hintField = state.hintField ?? null;
  const setHintField = (val: string | null) => updateState({ hintField: val });

  const assignedZoneFields: Set<string> = state.assignedZoneFields ?? new Set<string>();
  const setAssignedZoneFields = (val: Set<string> | ((prev: Set<string>) => Set<string>)) => updateState({ assignedZoneFields: val });

  const zoneEditorKey = state.zoneEditorKey ?? 0;
  const setZoneEditorKey = (val: number | ((prev: number) => number)) => updateState({ zoneEditorKey: val });

  const presetZones: DrawnZone[] = state.presetZones ?? [];
  const setPresetZones = (val: DrawnZone[] | ((prev: DrawnZone[]) => DrawnZone[])) => updateState({ presetZones: val });

  // Local ephemeral states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ambiguousMatches, setAmbiguousMatches] = useState<any[] | null>(null);
  const [galleryTemplates, setGalleryTemplates] = useState<any[] | null>(null);
  const [missingFields, setMissingFields] = useState<string[] | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Load conversation history if convoId present
  useEffect(() => {
    if (!convoId) {
      // If we navigate to /generate without an ID, we should reset to a clean state.
      // But only if we want to clear. Actually, the requirement says "never reset on tab switch".
      // A tab switch to /generate (with no ID) might mean they clicked the sidebar "Single Poster" link.
      // Let's only reset if they explicitly clicked "New" - wait, there is no "New" button.
      // The bug says "Clicking a history item must completely replace".
      // So if convoId IS present, we MUST reset first to clear previous state.
      return;
    }
    
    const loadConvoHistory = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // CLEAR entire session state first so previous poster's state doesn't leak
        resetState();
        
        const data = await getConversationMessages(convoId);
        if (data.messages && data.messages.length > 0) {
          const userMsg = data.messages.find((m: any) => m.role === "user");
          if (userMsg) {
            // We must update the state via the context update
            updateState({ prompt: userMsg.content });
          }
          
          const assistantMsg = data.messages.find(
            (m: any) => m.role === "assistant" && m.output_file_path
          );
          if (assistantMsg) {
            try {
              const blob = await getConversationImage(convoId);
              updateState({ posterUrl: URL.createObjectURL(blob) });
            } catch (imgErr) {
              console.warn("Could not fetch conversation image output:", imgErr);
            }
          }
          
          // Note: if the backend returned layers/zones/templateId in data.conversation,
          // we would populate them here. Currently it seems they aren't fully returned 
          // or aren't used, but the crucial part is we cleared the OLD stale data.
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

  // Main generate handler
  const handleGenerate = async (
    overrideFolder?: string,
    overrideTemplateId?: string,
    additionalInputs?: Record<string, string>,
    regenCaptionPrompt?: string,
    passedLayoutOverrides?: Record<string, any>,
    passedStyleOverrides?: Record<string, any>
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
    setZoneEditorMode(false);

    // If this is a fresh search from the main prompt button (no overrides or field answers),
    // clear stale folder, templateId, and overrides so vector search finds the right template.
    const isFreshSearch = !overrideFolder && !overrideTemplateId && !additionalInputs && !regenCaptionPrompt;
    if (isFreshSearch) {
      setFolder(null);
      setTemplateId(null);
      setStoredValues({});
      setLayoutOverrides({});
      setStyleOverrides({});
      setFieldPrompts({});
      setCustomCaptionPrompt("");
    }

    try {
      const formData = new FormData();
      formData.append("prompt", prompt.trim());

      const targetFolder = isFreshSearch ? undefined : (overrideFolder || folder);
      const targetTemplateId = isFreshSearch ? undefined : (overrideTemplateId || templateId);

      if (targetFolder) formData.append("folder", targetFolder);
      if (targetTemplateId) formData.append("template_id", targetTemplateId);
      if (imageFile) formData.append("image", imageFile);

      // Layout overrides (from zone drawing or passed directly)
      const effectiveLayoutOverrides = passedLayoutOverrides ?? {};
      const effectiveStyleOverrides = passedStyleOverrides ?? styleOverrides;

      // Append Layout & Style overrides if non-empty and not a fresh search
      if (!isFreshSearch && Object.keys(effectiveLayoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(effectiveLayoutOverrides));
      }
      if (!isFreshSearch && Object.keys(effectiveStyleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(effectiveStyleOverrides));
      }
      if (!isFreshSearch && Object.keys(fieldPrompts).length > 0) {
        formData.append("field_prompts", JSON.stringify(fieldPrompts));
      }

      if (regenCaptionPrompt) {
        formData.append("caption_prompt", regenCaptionPrompt);
      } else if (customCaptionPrompt) {
        formData.append("caption_prompt", customCaptionPrompt);
      }

      const mergedInputs = isFreshSearch ? (additionalInputs || {}) : { ...storedValues, ...(additionalInputs || {}) };
      Object.entries(mergedInputs).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          if (v instanceof Blob) {
            formData.append(k, v);
          } else if (typeof v === "object") {
            formData.append(k, JSON.stringify(v));
          } else {
            formData.append(k, String(v));
          }
        }
      });

      const res = await fetch("/api/proxy/generate?json=true", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData,
      });

      const contentType = res.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const json = await res.json();

        if (json.status === "success") {
          setPosterUrl(`data:image/png;base64,${json.image}`);
          if (json.folder) setFolder(json.folder);
          if (json.template_id) setTemplateId(json.template_id);
          if (json.overlay_values) {
            setStoredValues((prev) => ({ ...prev, ...json.overlay_values }));
          }

          if (json.overlay_layers) {
            const syncedZones: DrawnZone[] = json.overlay_layers
              .filter((l: any) => l.box && l.box.width > 0)
              .map((l: any) => {
                const currentLayout = effectiveLayoutOverrides[l.id] || {};
                const currentStyle = effectiveStyleOverrides[l.id] || {};
                return {
                  field_id: l.id,
                  x: currentLayout.x ?? l.box.x,
                  y: currentLayout.y ?? l.box.y,
                  width: currentLayout.width ?? l.box.width,
                  height: currentLayout.height ?? l.box.height,
                  font_family: currentStyle.font_family || l.style?.font_family || "Poppins",
                  font_size: currentStyle.font_size || l.style?.font_size || 32,
                  font_weight: currentStyle.font_weight || l.style?.font_weight || "bold",
                  color: currentStyle.color || l.style?.color || "#FFFFFF",
                  align: (currentStyle.align || l.style?.align || "center") as any,
                  llm_can_invent: !!l.llm_can_invent,
                  type: l.type || "text",
                };
              });

            const syncedLayoutOverrides: Record<string, any> = { ...effectiveLayoutOverrides };
            const syncedStyleOverrides: Record<string, any> = { ...effectiveStyleOverrides };

            syncedZones.forEach((z) => {
              if (!syncedLayoutOverrides[z.field_id]) {
                syncedLayoutOverrides[z.field_id] = { x: z.x, y: z.y, width: z.width, height: z.height };
              }
              if (!syncedStyleOverrides[z.field_id]) {
                syncedStyleOverrides[z.field_id] = {
                  font_family: z.font_family,
                  font_size: z.font_size,
                  font_weight: z.font_weight,
                  color: z.color,
                  align: z.align,
                };
              }
            });

            updateState({
              layers: json.overlay_layers,
              presetZones: syncedZones,
              layoutOverrides: syncedLayoutOverrides,
              styleOverrides: syncedStyleOverrides,
              assignedZoneFields: new Set(syncedZones.map((z) => z.field_id)),
            });
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
          if (json.overlay_layers) {
            setLayers(json.overlay_layers);
            const loadedZones: DrawnZone[] = json.overlay_layers
              .filter((l: any) => l.box && l.box.width > 0)
              .map((l: any) => ({
                field_id: l.id,
                x: l.box.x,
                y: l.box.y,
                width: l.box.width,
                height: l.box.height,
                font_family: l.style?.font_family || "Poppins",
                font_size: l.style?.font_size || 32,
                font_weight: l.style?.font_weight || "bold",
                color: l.style?.color || "#FFFFFF",
                align: (l.style?.align as any) || "center",
                llm_can_invent: !!l.llm_can_invent,
                type: l.type || "text"
              }));
            setPresetZones(loadedZones);
            setAssignedZoneFields(new Set(loadedZones.map(z => z.field_id)));
            setZoneEditorKey(prev => prev + 1);
          } else {
            setAssignedZoneFields(new Set());
            setPresetZones([]);
            setZoneEditorKey(prev => prev + 1);
          }
          setZoneEditorMode(true);
        } else if (json.status === "no_match") {
          setError(json.message || "No template found for your request.");
        } else if (json.detail) {
          setError(
            typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail)
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

  // Compute required fields for ZoneEditor (derive llm_can_invent from layers if available)
  const requiredFieldsMeta: RequiredField[] = layers.map((layer) => ({
    id: layer.id,
    llm_can_invent: !!(layer as any).llm_can_invent,
  }));

  // Called continuously whenever zones are added, dragged, resized, or styled in ZoneEditor
  const handleZoneChange = useCallback(
    (zones: DrawnZone[]) => {
      const newLayoutOverrides: Record<string, any> = {};
      const newStyleOverrides: Record<string, any> = {};

      zones.forEach((z) => {
        newLayoutOverrides[z.field_id] = {
          x: z.x, y: z.y, width: z.width, height: z.height,
        };
        newStyleOverrides[z.field_id] = {
          font_family: z.font_family,
          font_size: z.font_size,
          font_weight: z.font_weight,
          color: z.color,
          align: z.align,
        };
      });

      updateState({
        layoutOverrides: newLayoutOverrides,
        styleOverrides: newStyleOverrides,
        presetZones: zones,
        assignedZoneFields: new Set(zones.map((z) => z.field_id)),
      });
    },
    [updateState]
  );

  // Called when user completes zone drawing and clicks Done
  const handleZoneDone = useCallback(
    (zones: DrawnZone[]) => {
      // Validate that all required non-AI fields have values typed in
      const emptyFields = requiredFieldsMeta.filter((f) => !f.llm_can_invent && !storedValues[f.id]?.trim());
      if (emptyFields.length > 0) {
        setError(`Please type the text value for: ${emptyFields.map(f => f.id.replace(/_/g, ' ')).join(', ')} in the left panel before generating.`);
        return;
      }

      const newLayoutOverrides: Record<string, any> = {};
      const newStyleOverrides: Record<string, any> = {};

      zones.forEach((z) => {
        newLayoutOverrides[z.field_id] = {
          x: z.x, y: z.y, width: z.width, height: z.height,
        };
        newStyleOverrides[z.field_id] = {
          font_family: z.font_family,
          font_size: z.font_size,
          font_weight: z.font_weight,
          color: z.color,
          align: z.align,
        };
      });

      setLayoutOverrides(newLayoutOverrides);
      setStyleOverrides(newStyleOverrides);
      setPresetZones(zones);
      setZoneEditorKey(prev => prev + 1);
      setZoneEditorMode(false);
      // Pass overrides directly to avoid async state timing issues
      handleGenerate(
        folder || undefined,
        templateId || undefined,
        undefined,
        undefined,
        newLayoutOverrides,
        newStyleOverrides
      );
    },
    [folder, templateId, storedValues, fieldPrompts, customCaptionPrompt, imageFile, requiredFieldsMeta, layers]
  );



  const thumbnailUrl =
    folder && templateId
      ? `/api/proxy/template-thumbnail/${folder}/${templateId}`
      : null;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 overflow-x-hidden">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-indigo-400" />
          Single Poster Generator & Live Editor
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          Describe your poster, let AI select templates and write copy, then draw zones to place your text with live preview.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* ── Left Column ── */}
        <div className="lg:col-span-5 space-y-6">
          {/* Prompt + Photo + Generate */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                Poster Prompt / Event Description *
              </label>
              <textarea
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g., Generate a festive Happy Dussehra greeting poster with customer photo and wish line..."
                className="w-full p-3.5 bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm resize-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                User Photo (Optional)
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 bg-slate-50 dark:bg-slate-950/40 rounded-xl p-4 cursor-pointer transition-all flex flex-col items-center justify-center text-center gap-2"
              >
                <Upload className="h-5 w-5 text-slate-500" />
                {imageFile ? (
                  <span className="text-xs text-indigo-400 font-medium">{imageFile.name}</span>
                ) : (
                  <span className="text-xs text-slate-500">Click to attach photo for image placeholder zones</span>
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

            <button
              onClick={() => handleGenerate()}
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-slate-900 dark:text-white font-medium rounded-xl shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition-all active:scale-[0.99] disabled:opacity-50 text-sm"
            >
              {loading ? (
                <><RefreshCw className="h-4 w-4 animate-spin" /><span>Processing & Rendering...</span></>
              ) : (
                <><Sparkles className="h-4 w-4" /><span>Generate Poster</span></>
              )}
            </button>
          </div>

          {/* Ambiguous disambiguation */}
          {ambiguousMatches && ambiguousMatches.length > 0 && (
            <div className="bg-amber-950/30 border border-amber-800/50 rounded-2xl p-6 space-y-4">
              <h3 className="text-sm font-semibold text-amber-200 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-amber-400" />
                Multiple Matching Poster Categories Found
              </h3>
              <p className="text-xs text-amber-300/80">Please select the specific category for your poster:</p>
              <div className="space-y-2">
                {ambiguousMatches.map((m: any) => (
                  <button
                    key={m.folder}
                    onClick={() => { setFolder(m.folder); handleGenerate(m.folder); }}
                    className="w-full text-left p-3 rounded-xl bg-white dark:bg-slate-900 border border-amber-900/40 hover:border-amber-500 text-slate-800 dark:text-slate-200 flex items-center justify-between text-xs font-medium transition-all"
                  >
                    <span>{m.display_name || m.folder}</span>
                    <span className="text-[10px] text-amber-400">Select →</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Zone editor — field tracker */}
          {zoneEditorMode && requiredFieldsMeta.length > 0 && (
            <div className="bg-white dark:bg-slate-900 border border-indigo-500/40 rounded-2xl p-6 space-y-5 shadow-xl">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-indigo-400" />
                Fields needed for this poster
              </h3>

              <div className="space-y-4">
                {requiredFieldsMeta.map((field) => {
                  const isAI = field.llm_can_invent;
                  const hasZone = assignedZoneFields.has(field.id);
                  return (
                    <div key={field.id} className="flex items-start gap-3">
                      {/* Status icon */}
                      <div className={`mt-0.5 h-4 w-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                        isAI || hasZone ? "border-emerald-500 bg-emerald-500/20" : "border-slate-500"
                      }`}>
                        {(isAI || hasZone) && <Check className="h-2.5 w-2.5 text-emerald-400" />}
                      </div>

                      <div className="flex-1 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-800 dark:text-slate-200 capitalize flex items-center gap-2">
                            {field.id.replace(/_/g, " ")}
                            {isAI && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                                AI
                              </span>
                            )}
                          </span>
                          <button
                            onClick={() => setHintField(field.id)}
                            className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors font-medium"
                          >
                            Draw zone →
                          </button>
                        </div>

                        {/* Text value input */}
                        {!isAI && (
                          <input
                            type="text"
                            value={storedValues[field.id] || ""}
                            onChange={(e) => setStoredValues({ ...storedValues, [field.id]: e.target.value })}
                            placeholder={`Type ${field.id.replace(/_/g, " ")} value...`}
                            className="w-full p-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-xs text-slate-900 dark:text-slate-100 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* All zones placed success */}
              {requiredFieldsMeta.every((f) => f.llm_can_invent || assignedZoneFields.has(f.id)) && (
                <div className="flex items-center gap-2 text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 rounded-xl px-4 py-2.5 text-xs font-medium">
                  <Check className="h-3.5 w-3.5" />
                  All zones placed. Click "Done — Generate Poster" to continue.
                </div>
              )}

              <p className="text-[10px] text-slate-500">
                Draw zones on the poster preview → to place each field, then click Done.
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs leading-relaxed">
              {error}
            </div>
          )}
        </div>

        {/* ── Right Column ── */}
        <div className="lg:col-span-7 flex flex-col space-y-6">


          {/* Zone Editor — replaces right panel when needs_input */}
          {zoneEditorMode && thumbnailUrl ? (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xl">
              <ZoneEditor
                key={zoneEditorKey}
                initialZones={presetZones}
                posterImageUrl={thumbnailUrl || posterUrl || ""}
                requiredFields={requiredFieldsMeta}
                textValues={storedValues}
                onChange={handleZoneChange}
                onDone={handleZoneDone}
                onCancel={() => { setZoneEditorMode(false); setMissingFields(null); }}
                hintField={hintField}
                onHintFieldClear={() => setHintField(null)}
                onFieldAssigned={(fid) =>
                  setAssignedZoneFields((prev) => new Set([...prev, fid]))
                }
              />
            </div>
          ) : (
            /* Normal poster preview */
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 flex flex-col justify-center items-center relative min-h-[450px] shadow-xl">
              {loading ? (
                <div className="flex flex-col items-center gap-3 text-slate-600 dark:text-slate-400">
                  <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
                  <p className="text-xs font-medium">Rendering poster live preview...</p>
                </div>
              ) : posterUrl ? (
                <div className="flex flex-col items-center gap-4 w-full">
                  <div className="relative rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-2xl max-h-[600px] flex justify-center">
                    <img
                      src={posterUrl}
                      alt="Generated Poster"
                      className="max-h-[600px] w-auto object-contain rounded-xl"
                    />
                  </div>
                  <div className="flex gap-3">
                    <a
                      href={posterUrl}
                      download="poster.png"
                      className="py-2.5 px-5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-900 dark:text-white font-medium rounded-xl border border-slate-700 shadow-md text-xs flex items-center gap-2 transition-all"
                    >
                      <Download className="h-4 w-4" />
                      <span>Download High-Res PNG</span>
                    </a>
                    <button
                      onClick={() => {
                        let activeZones = presetZones;
                        if ((!activeZones || activeZones.length === 0) && layers.length > 0) {
                          activeZones = layers
                            .filter((l: any) => l.box && l.box.width > 0)
                            .map((l: any) => {
                              const currentLayout = layoutOverrides[l.id] || {};
                              const currentStyle = styleOverrides[l.id] || {};
                              return {
                                field_id: l.id,
                                x: currentLayout.x ?? l.box.x,
                                y: currentLayout.y ?? l.box.y,
                                width: currentLayout.width ?? l.box.width,
                                height: currentLayout.height ?? l.box.height,
                                font_family: currentStyle.font_family || l.style?.font_family || "Poppins",
                                font_size: currentStyle.font_size || l.style?.font_size || 32,
                                font_weight: currentStyle.font_weight || l.style?.font_weight || "bold",
                                color: currentStyle.color || l.style?.color || "#FFFFFF",
                                align: (currentStyle.align || l.style?.align || "center") as any,
                                llm_can_invent: !!l.llm_can_invent,
                                type: l.type || "text",
                              };
                            });
                          setPresetZones(activeZones);
                        }
                        setAssignedZoneFields(new Set((activeZones || []).map((z) => z.field_id)));
                        setZoneEditorKey((prev) => prev + 1);
                        setZoneEditorMode(true);
                      }}
                      className="py-2.5 px-5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 font-medium rounded-xl border border-indigo-700/50 text-xs flex items-center gap-2 transition-all"
                    >
                      Reposition Zones
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3 text-slate-600 text-center p-6">
                  <ImageIcon className="h-12 w-12 stroke-[1.5]" />
                  <p className="text-xs font-medium text-slate-600 dark:text-slate-400">No poster generated yet</p>
                  <p className="text-[11px] text-slate-600 max-w-xs">
                    Fill in the prompt on the left and click "Generate Poster" to view your result here.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Gallery thumbnail picker - FULL WIDTH */}
      {galleryTemplates && galleryTemplates.length > 0 && (
        <div className="bg-indigo-950/30 border border-indigo-800/50 rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-semibold text-indigo-200 flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-400" />
            Select a Template Layout
          </h3>
          <p className="text-xs text-indigo-300/70">
            Click a template or "Use this Design" to generate your poster.
          </p>
          <TemplateSelectionList
            templates={galleryTemplates}
            folder={folder}
            selectedId={templateId}
            onSelect={(id) => {
              setTemplateId(id);
              handleGenerate(folder || undefined, id);
            }}
            themeColor="indigo"
            actionText="Use this Design"
            twoColumn={true}
          />
        </div>
      )}
    </div>
  );
}

export default function SingleGeneratePage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-slate-600 dark:text-slate-400 text-xs">
          Loading poster generator...
        </div>
      }
    >
      <SingleGenerateContent />
    </Suspense>
  );
}
