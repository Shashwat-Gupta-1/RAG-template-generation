"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  previewBulkJob,
  startBulkJob,
  resumeBulkJob,
  getBulkStatus,
  getConversations,
  getConversationMessages,
} from "@/lib/api";


import { BulkJobStatus } from "@/lib/types";
import {
  FileSpreadsheet,
  Upload,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  Eye,
  Sliders,
  ChevronDown,
  ChevronUp,
  MapPin,
  ArrowRight,
  RotateCcw,
  Wand2,
  Edit3,
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

function BulkGenerateContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const convoId = searchParams.get("id");

  // Inputs
  const [prompt, setPrompt] = useState("");
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);

  // Workflow State
  const [bulkStarted, setBulkStarted] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  // Preview & Layer State
  const [previewB64, setPreviewB64] = useState<string | null>(null);
  const [canvasDimensions, setCanvasDimensions] = useState<{ width: number; height: number }>({
    width: 1024,
    height: 1536,
  });
  const [overlayLayers, setOverlayLayers] = useState<any[]>([]);
  const [excelColumns, setExcelColumns] = useState<string[]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [layoutOverrides, setLayoutOverrides] = useState<Record<string, { x: number; y: number }>>({});
  const [styleOverrides, setStyleOverrides] = useState<Record<string, any>>({});

  // Direct Custom Values & AI Field Prompts for llm_can_invent: true fields
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [fieldPrompts, setFieldPrompts] = useState<Record<string, string>>({});

  // Caption Controls
  const [customCaptionPrompt, setCustomCaptionPrompt] = useState("");
  const [staticCaption, setStaticCaption] = useState("");

  // Ambiguous & Gallery States
  const [ambiguousMatches, setAmbiguousMatches] = useState<any[]>([]);
  const [galleryTemplates, setGalleryTemplates] = useState<any[]>([]);
  const [galleryDisplayName, setGalleryDisplayName] = useState("");

  // Job & Polling State
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<BulkJobStatus | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [startLoading, setStartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Expanders
  const [showMappingExpander, setShowMappingExpander] = useState(true);
  const [showEditorExpander, setShowEditorExpander] = useState(true);

  const excelInputRef = useRef<HTMLInputElement | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);


  // Restore conversation if query param present
  useEffect(() => {
    if (!convoId) return;

    const loadBulkConvo = async () => {
      try {
        setJobId(convoId);
        const data = await getConversationMessages(convoId);
        if (data.conversation) {
          setPrompt(data.conversation.title || "");
        }
      } catch (err: any) {
        console.warn("Failed to load bulk conversation:", err.message);
        router.replace("/bulk");
      }
    };

    loadBulkConvo();
  }, [convoId]);


  // Polling loop for active job
  useEffect(() => {
    if (!jobId) return;

    let isSubscribed = true;

    const checkStatus = async () => {
      try {
        const res = await getBulkStatus(jobId);
        if (!isSubscribed) return;

        setJobStatus(res);

        const currentStatus = res.status || res.job_status;
        if (currentStatus === "processing" || currentStatus === "queued") {
          setTimeout(checkStatus, 1500); // Poll every 1.5s
        }
      } catch (err: any) {
        if (isSubscribed) {
          console.error("Error polling job status:", err);
        }
      }
    };

    checkStatus();

    return () => {
      isSubscribed = false;
    };
  }, [jobId]);

  // Helper to build FormData payload for preview or job start
  const buildFormData = useCallback(
    (overrideFolder?: string, overrideTemplateId?: string) => {
      const formData = new FormData();
      formData.append("prompt", prompt.trim());

      if (excelFile) formData.append("excel_file", excelFile);
      if (photoFile) formData.append("photo", photoFile);

      const targetFolder = overrideFolder || selectedFolder;
      const targetTemplateId = overrideTemplateId || selectedTemplateId;

      if (targetFolder) formData.append("folder", targetFolder);
      if (targetTemplateId) formData.append("template_id", targetTemplateId);

      if (Object.keys(columnMapping).length > 0) {
        formData.append("column_mapping", JSON.stringify(columnMapping));
      }
      if (Object.keys(layoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(layoutOverrides));
      }
      if (Object.keys(styleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(styleOverrides));
      }

      // Pass direct custom field values and custom AI field prompts
      if (Object.keys(fieldValues).length > 0) {
        formData.append("field_values", JSON.stringify(fieldValues));
      }
      if (Object.keys(fieldPrompts).length > 0) {
        formData.append("field_prompts", JSON.stringify(fieldPrompts));
      }

      if (customCaptionPrompt.trim()) {
        formData.append("caption_prompt", customCaptionPrompt.trim());
      }
      if (staticCaption.trim()) {
        formData.append("caption", staticCaption.trim());
      }

      return formData;
    },
    [
      prompt,
      excelFile,
      photoFile,
      selectedFolder,
      selectedTemplateId,
      columnMapping,
      layoutOverrides,
      styleOverrides,
      fieldValues,
      fieldPrompts,
      customCaptionPrompt,
      staticCaption,
    ]
  );

  // Fetch / Refresh Live Preview (Row 1)
  const fetchLivePreview = useCallback(
    async (overrideFolder?: string, overrideTemplateId?: string) => {
      if (!prompt.trim() || !excelFile) return;

      setPreviewLoading(true);
      setError(null);

      try {
        const formData = buildFormData(overrideFolder, overrideTemplateId);
        const res = await previewBulkJob(formData);

        // Always extract structural layer metadata if returned
        if (res.canvas) setCanvasDimensions(res.canvas);
        if (res.overlay_layers) setOverlayLayers(res.overlay_layers);
        if (res.column_map) {
          setColumnMapping((prev) => (Object.keys(prev).length === 0 ? res.column_map : prev));
        }
        if (res.excel_columns) setExcelColumns(res.excel_columns);
        if (res.folder) {
          setSelectedFolder((prev) => (prev !== res.folder ? res.folder : prev));
        }
        if (res.template_id) {
          setSelectedTemplateId((prev) => (prev !== res.template_id ? res.template_id : prev));
        }

        if (res.status === "ambiguous" && res.matches) {
          setAmbiguousMatches(res.matches);
          setPreviewB64(null);
        } else if (res.status === "gallery" && res.templates) {
          setGalleryTemplates(res.templates);
          setGalleryDisplayName(res.display_name || "Matching Templates");
          setPreviewB64(null);
        } else if (res.preview_image) {
          setPreviewB64(`data:image/png;base64,${res.preview_image}`);
          setAmbiguousMatches([]);
          setGalleryTemplates([]);
          if (res.errors && Array.isArray(res.errors) && res.errors.length > 0) {
            setError("Some template fields require column mapping. Please review and map the columns in the panel below.");
          } else {
            setError(null);
          }
        } else if (res.errors && Array.isArray(res.errors)) {
          setError(
            "Some template fields require column mapping. Please review and map the columns in the panel below."
          );
        } else if (res.error) {
          setError(res.error);
        }
      } catch (err: any) {
        setError(err.message || "Failed to generate live preview.");
      } finally {
        setPreviewLoading(false);
      }
    },
    [prompt, excelFile, buildFormData]
  );

  // Auto-refresh live preview ONLY when user modifies layout, style, column mapping, or field value controls
  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (!bulkStarted || !excelFile || !prompt.trim()) return;

    const timer = setTimeout(() => {
      fetchLivePreview();
    }, 500);

    return () => clearTimeout(timer);
  }, [
    columnMapping,
    layoutOverrides,
    styleOverrides,
    fieldValues,
    fieldPrompts,
    staticCaption,
    customCaptionPrompt,
  ]);

  const handleStartSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      setError("Please describe the poster type.");
      return;
    }
    if (!excelFile) {
      setError("Please select an Excel (.xlsx) file.");
      return;
    }

    setBulkStarted(true);
    setSelectedFolder(null);
    setSelectedTemplateId(null);
    setColumnMapping({});
    setLayoutOverrides({});
    setStyleOverrides({});
    setFieldValues({});
    setFieldPrompts({});
    setStaticCaption("");
    setCustomCaptionPrompt("");
    fetchLivePreview();
  };

  const handleStartBatchJob = async () => {
    if (!prompt.trim() || !excelFile) {
      setError("Prompt and Excel file are required.");
      return;
    }

    setStartLoading(true);
    setError(null);

    try {
      const formData = buildFormData();
      const res = await startBulkJob(formData);

      if (res.job_id) {
        setJobId(res.job_id);
        setJobStatus({
          job_id: res.job_id,
          status: res.status || "processing",
          total: res.total_rows || 0,
          completed: 0,
        });
      } else if (res.error) {
        setError(res.error);
      } else if (res.errors) {
        setError(`Excel validation errors: ${JSON.stringify(res.errors)}`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to start bulk job.");
    } finally {
      setStartLoading(false);
    }
  };

  const handleResumeBatchJob = async () => {
    if (!jobId || startLoading) return;
    setStartLoading(true);
    setError(null);

    try {
      const res = await resumeBulkJob(jobId);
      if (res.job_id) {
        setJobStatus((prev) =>
          prev
            ? { ...prev, status: "processing" }
            : { job_id: res.job_id, status: "processing", total: 0, completed: 0 }
        );
        try {
          const statusRes = await getBulkStatus(res.job_id);
          setJobStatus(statusRes);
        } catch {}
      } else if (res.error) {
        setError(res.error);
      }
    } catch (err: any) {
      setError(err.message || "Failed to resume bulk job.");
    } finally {
      setStartLoading(false);
    }
  };





  const handleResetBulk = () => {
    setBulkStarted(false);
    setPrompt("");
    setExcelFile(null);
    setPhotoFile(null);
    setSelectedFolder(null);
    setSelectedTemplateId(null);
    setPreviewB64(null);
    setOverlayLayers([]);
    setColumnMapping({});
    setLayoutOverrides({});
    setStyleOverrides({});
    setFieldValues({});
    setFieldPrompts({});
    setStaticCaption("");
    setCustomCaptionPrompt("");
    setJobId(null);
    setJobStatus(null);
    setError(null);
  };

  const updateColumnMapping = (fieldId: string, colName: string) => {
    const nextMap = { ...columnMapping };
    if (colName && colName !== "(Choose column...)") {
      nextMap[fieldId] = colName;
    } else {
      delete nextMap[fieldId];
    }
    setColumnMapping(nextMap);
  };

  const updateLayoutOverride = (layerId: string, axis: "x" | "y", val: number) => {
    const origBox = overlayLayers.find((l) => l.id === layerId)?.box || { x: 0, y: 0 };
    const current = layoutOverrides[layerId] || { x: origBox.x, y: origBox.y };
    const next = { ...current, [axis]: val };
    setLayoutOverrides({ ...layoutOverrides, [layerId]: next });
  };

  const updateStyleOverride = (layerId: string, key: string, val: any) => {
    const current = styleOverrides[layerId] || {};
    const next = { ...current, [key]: val };
    setStyleOverrides({ ...styleOverrides, [layerId]: next });
  };

  const statusStr = jobStatus?.status || jobStatus?.job_status || "idle";
  const totalRows = jobStatus?.total ?? jobStatus?.job_total ?? 0;
  const completedRows = jobStatus?.completed ?? jobStatus?.job_completed ?? 0;
  const skippedRows = jobStatus?.skipped ?? jobStatus?.job_skipped ?? 0;
  const failedRows = jobStatus?.failed ?? jobStatus?.job_failed ?? 0;
  const downloadUrl = jobStatus?.download_url || jobStatus?.job_download_url;
  const jobErr = jobStatus?.error || jobStatus?.job_error;

  const progressPercent =
    totalRows > 0 ? Math.min(100, Math.round((completedRows / totalRows) * 100)) : 0;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <FileSpreadsheet className="h-6 w-6 text-emerald-400" />
            Bulk Poster Generation from Excel
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Search template by query, map Excel columns, customize live preview styling, then apply to all rows in batch.
          </p>
        </div>

        {bulkStarted && (
          <button
            type="button"
            onClick={handleResetBulk}
            className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs flex items-center gap-1.5 border border-slate-700 transition-all"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Start Over</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs leading-relaxed">
          {error}
        </div>
      )}

      {/* STEP 1: Search Form Inputs */}
      {!bulkStarted ? (
        <form
          onSubmit={handleStartSearch}
          className="bg-slate-900 border border-slate-800 rounded-2xl p-8 max-w-2xl mx-auto shadow-xl space-y-6"
        >
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Describe Poster Type / Event Query *
            </label>
            <textarea
              rows={3}
              required
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Holi poster for employees, Eid greetings, Hiring announcement for sales team..."
              className="w-full p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-sm resize-none"
            />
          </div>

          {/* Excel File Upload */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Excel Data File (.xlsx) *
            </label>
            <div
              onClick={() => excelInputRef.current?.click()}
              className="border-2 border-dashed border-slate-800 hover:border-emerald-500/50 bg-slate-950/40 rounded-xl p-5 cursor-pointer transition-all flex flex-col items-center justify-center text-center gap-2"
            >
              <FileSpreadsheet className="h-8 w-8 text-emerald-500" />
              {excelFile ? (
                <span className="text-xs text-emerald-400 font-medium">{excelFile.name}</span>
              ) : (
                <span className="text-xs text-slate-400">
                  Click to select Excel (.xlsx) file
                </span>
              )}
              <input
                ref={excelInputRef}
                type="file"
                accept=".xlsx, .xls"
                onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
                className="hidden"
              />
            </div>
          </div>

          {/* Optional Shared Photo */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Shared Profile Photo / Logo (Optional)
            </label>
            <div
              onClick={() => photoInputRef.current?.click()}
              className="border border-slate-800 hover:border-slate-700 bg-slate-950/40 rounded-xl p-3.5 cursor-pointer transition-all flex items-center justify-between text-xs text-slate-400"
            >
              <span>{photoFile ? photoFile.name : "Attach photo for image placeholder zones"}</span>
              <Upload className="h-4 w-4 text-slate-500" />
              <input
                ref={photoInputRef}
                type="file"
                accept="image/*"
                onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
                className="hidden"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3.5 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition-all text-xs"
          >
            <span>Match Template & Generate Live Preview</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>
      ) : (
        /* STEP 2: Interactive Live Preview, Column Mapping, Styling & Batch Launch */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Configuration & Mapping Controls */}
          <div className="lg:col-span-6 space-y-6">
            {/* Ambiguous Matches Card */}
            {ambiguousMatches.length > 0 && (
              <div className="bg-slate-900 border border-amber-800/60 rounded-2xl p-5 space-y-3 shadow-xl">
                <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" /> Which category did you mean?
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  {ambiguousMatches.map((m) => (
                    <button
                      key={m.folder}
                      onClick={() => {
                        setSelectedFolder(m.folder);
                        fetchLivePreview(m.folder);
                      }}
                      className="p-3 bg-slate-950 hover:bg-slate-800 border border-slate-800 text-white text-xs font-medium rounded-xl text-left transition-all"
                    >
                      {m.display_name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Template Gallery Picker Card */}
            {galleryTemplates.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Select a Template Design for {galleryDisplayName}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {galleryTemplates.map((t) => (
                    <div
                      key={t.template_id}
                      onClick={() => {
                        setSelectedTemplateId(t.template_id);
                        fetchLivePreview(selectedFolder || undefined, t.template_id);
                      }}
                      className={`p-4 bg-slate-950 rounded-xl border cursor-pointer transition-all space-y-2 ${
                        selectedTemplateId === t.template_id
                          ? "border-emerald-500 ring-2 ring-emerald-500/20"
                          : "border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <p className="font-semibold text-xs text-white">{t.template_id}</p>
                      <p className="text-[11px] text-slate-400 line-clamp-2">{t.description}</p>
                      <span className="text-[10px] text-emerald-400 font-medium block">
                        Click to use this template →
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Column Mapping Expander */}
            {(excelColumns.length > 0 || overlayLayers.length > 0) && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                <div
                  onClick={() => setShowMappingExpander(!showMappingExpander)}
                  className="p-4 bg-slate-950/70 hover:bg-slate-800/80 cursor-pointer flex items-center justify-between border-b border-slate-800 transition-all text-xs font-semibold text-emerald-300"
                >
                  <span className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-emerald-400" />
                    Review & Adjust Column Mapping
                  </span>
                  {showMappingExpander ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </div>

                {showMappingExpander && (
                  <div className="p-6 space-y-4 bg-slate-900">
                    <p className="text-xs text-slate-400">
                      Checking Excel columns against template fields. Matched columns display a green checkmark ✅. Select mapping for unmapped fields below.
                    </p>

                    <div className="space-y-3">
                      {/* Compute all fields needing check */}
                      {[
                        { id: "emp_id", label: "Row Identifier (emp_id)" },
                        ...overlayLayers
                          .filter((l) => l.id && l.type !== "image")
                          .map((l) => ({ id: l.id, label: `Field: ${l.id}` })),
                      ].map((item) => {
                        const mappedCol = columnMapping[item.id] || "";
                        const isMatched = mappedCol !== "" && excelColumns.includes(mappedCol);

                        return (
                          <div
                            key={item.id}
                            className={`flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl border transition-all gap-2 ${
                              isMatched
                                ? "bg-slate-950/80 border-emerald-500/30"
                                : "bg-amber-950/20 border-amber-500/40"
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              {isMatched ? (
                                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                              ) : (
                                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0" />
                              )}
                              <span className="text-xs font-semibold text-white">
                                {item.label}{" "}
                                {isMatched ? (
                                  <span className="text-emerald-400 font-mono font-normal">
                                    ✅ Matched to <span className="underline">{mappedCol}</span>
                                  </span>
                                ) : (
                                  <span className="text-amber-400 font-normal">
                                    ⚠️ No match in Excel — Please select column
                                  </span>
                                )}
                              </span>
                            </div>

                            <select
                              value={mappedCol}
                              onChange={(e) => updateColumnMapping(item.id, e.target.value)}
                              className={`p-2 rounded-lg text-xs focus:ring-1 focus:outline-none transition-all ${
                                isMatched
                                  ? "bg-slate-900 border border-slate-800 text-slate-300 focus:ring-emerald-500"
                                  : "bg-slate-900 border border-amber-500/60 text-amber-200 focus:ring-amber-500 ring-1 ring-amber-500/30"
                              }`}
                            >
                              <option value="">(Select Excel column...)</option>
                              {excelColumns.map((col) => (
                                <option key={col} value={col}>
                                  {col}
                                </option>
                              ))}
                            </select>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Position Sliders & Typography Styling Controls & Invent Fields Form */}
            {overlayLayers.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                <div
                  onClick={() => setShowEditorExpander(!showEditorExpander)}
                  className="p-4 bg-slate-950/70 hover:bg-slate-800/80 cursor-pointer flex items-center justify-between border-b border-slate-800 transition-all text-xs font-semibold text-emerald-300"
                >
                  <span className="flex items-center gap-2">
                    <Sliders className="h-4 w-4 text-emerald-400" />
                    Adjust Placeholder Positions, Values & AI Prompts
                  </span>
                  {showEditorExpander ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </div>

                {showEditorExpander && (
                  <div className="p-6 space-y-6 bg-slate-900 max-h-[550px] overflow-y-auto pr-2">
                    {overlayLayers
                      .filter((layer) => layer.id && layer.type !== "image")
                      .map((layer) => {
                        const lid = layer.id;
                        const box = layer.box || { x: 0, y: 0, width: 100, height: 50 };
                        const currentPos = layoutOverrides[lid] || { x: box.x, y: box.y };
                        const currentStyle = styleOverrides[lid] || {};
                        const isText = layer.type === "text";
                        const canInvent = !!layer.llm_can_invent;

                        return (
                          <div
                            key={lid}
                            className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-4"
                          >
                            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                              <span className="font-semibold text-xs text-white flex items-center gap-1.5">
                                Placeholder: <span className="text-purple-300 font-mono">{lid}</span> ({layer.type})
                                {canInvent ? (
                                  <span className="px-2 py-0.5 bg-purple-950 text-purple-400 border border-purple-800 text-[10px] rounded-md font-medium">
                                    AI Inventable
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 bg-slate-900 text-slate-400 border border-slate-800 text-[10px] rounded-md font-medium">
                                    Excel Mapped / Direct Input
                                  </span>
                                )}
                              </span>
                            </div>

                            {/* Direct Value vs AI Prompt Input Box */}
                            {isText && (
                              <div className="space-y-3">
                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1">
                                    <Edit3 className="h-3.5 w-3.5 text-emerald-400" />
                                    Direct Custom Value (Exact Text)
                                  </label>
                                  <input
                                    type="text"
                                    value={fieldValues[lid] || ""}
                                    onChange={(e) =>
                                      setFieldValues({ ...fieldValues, [lid]: e.target.value })
                                    }
                                    placeholder={`e.g. Type custom text for ${lid}...`}
                                    className="w-full p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                                  />
                                  <p className="text-[10px] text-slate-500 mt-1">
                                    Overrides text value for all posters in this batch.
                                  </p>
                                </div>

                                {canInvent && (
                                  <div className="border-t border-slate-800/80 pt-2">
                                    <label className="block text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1">
                                      <Wand2 className="h-3.5 w-3.5 text-purple-400" />
                                      AI Generation Instruction Prompt ({lid})
                                    </label>
                                    <input
                                      type="text"
                                      value={fieldPrompts[lid] || ""}
                                      onChange={(e) =>
                                        setFieldPrompts({ ...fieldPrompts, [lid]: e.target.value })
                                      }
                                      placeholder={`e.g. Write a creative ${lid} in Hindi...`}
                                      className="w-full p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:ring-1 focus:ring-purple-500 focus:outline-none"
                                    />
                                    <p className="text-[10px] text-slate-500 mt-1">
                                      Instruction prompt given to AI for generating content for this placeholder.
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Position Sliders (X, Y) */}
                            <div className="grid grid-cols-2 gap-4 border-t border-slate-800/80 pt-3">
                              <div>
                                <div className="flex justify-between items-center mb-1">
                                  <label className="text-[11px] font-semibold text-slate-400">X Position (px)</label>
                                  <input
                                    type="number"
                                    min={0}
                                    max={canvasDimensions.width}
                                    value={currentPos.x}
                                    onChange={(e) =>
                                      updateLayoutOverride(lid, "x", parseInt(e.target.value) || 0)
                                    }
                                    className="w-16 p-1 bg-slate-900 border border-slate-800 rounded text-xs text-slate-200 text-center font-mono"
                                  />
                                </div>
                                <input
                                  type="range"
                                  min={0}
                                  max={canvasDimensions.width}
                                  value={currentPos.x}
                                  onChange={(e) =>
                                    updateLayoutOverride(lid, "x", parseInt(e.target.value) || 0)
                                  }
                                  className="w-full accent-emerald-500 cursor-pointer"
                                />
                              </div>

                              <div>
                                <div className="flex justify-between items-center mb-1">
                                  <label className="text-[11px] font-semibold text-slate-400">Y Position (px)</label>
                                  <input
                                    type="number"
                                    min={0}
                                    max={canvasDimensions.height}
                                    value={currentPos.y}
                                    onChange={(e) =>
                                      updateLayoutOverride(lid, "y", parseInt(e.target.value) || 0)
                                    }
                                    className="w-16 p-1 bg-slate-900 border border-slate-800 rounded text-xs text-slate-200 text-center font-mono"
                                  />
                                </div>
                                <input
                                  type="range"
                                  min={0}
                                  max={canvasDimensions.height}
                                  value={currentPos.y}
                                  onChange={(e) =>
                                    updateLayoutOverride(lid, "y", parseInt(e.target.value) || 0)
                                  }
                                  className="w-full accent-emerald-500 cursor-pointer"
                                />
                              </div>
                            </div>

                            {/* Typography Styling (Font Family, Color) */}
                            {isText && (
                              <div className="grid grid-cols-2 gap-4 border-t border-slate-800/80 pt-3">
                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                                    Font Family
                                  </label>
                                  <select
                                    value={currentStyle.font_family || "(Template default)"}
                                    onChange={(e) =>
                                      updateStyleOverride(
                                        lid,
                                        "font_family",
                                        e.target.value === "(Template default)" ? undefined : e.target.value
                                      )
                                    }
                                    className="w-full p-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200"
                                  >
                                    {FONT_OPTIONS.map((f) => (
                                      <option key={f} value={f}>
                                        {f}
                                      </option>
                                    ))}
                                  </select>
                                </div>

                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                                    Text Colour
                                  </label>
                                  <div className="flex gap-2 items-center">
                                    <input
                                      type="color"
                                      value={currentStyle.color || "#FFFFFF"}
                                      onChange={(e) => updateStyleOverride(lid, "color", e.target.value)}
                                      className="h-8 w-10 bg-transparent cursor-pointer"
                                    />
                                    <input
                                      type="text"
                                      value={currentStyle.color || "#FFFFFF"}
                                      onChange={(e) => updateStyleOverride(lid, "color", e.target.value)}
                                      className="flex-1 p-1.5 bg-slate-900 border border-slate-800 rounded text-xs font-mono text-slate-200"
                                    />
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Live Preview & Batch Launch Section */}
          <div className="lg:col-span-6 space-y-6">
            {/* Live Preview Artwork Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col items-center justify-center relative min-h-[400px]">
              <div className="flex items-center justify-between w-full mb-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Eye className="h-4 w-4 text-emerald-400" />
                  Live Preview
                </h3>

                <button
                  type="button"
                  onClick={() => fetchLivePreview()}
                  disabled={previewLoading}
                  className="py-1.5 px-3 bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 rounded-lg text-xs flex items-center gap-1.5 font-medium transition-all disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${previewLoading ? "animate-spin" : ""}`} />
                  <span>Update Live Preview ↺</span>
                </button>
              </div>

              {previewB64 ? (
                <div className="flex flex-col items-center gap-2 w-full">
                  {/* eslint-disable-next-html-element-suppression */}
                  <img
                    src={previewB64}
                    alt="Live Preview"
                    className="max-h-[480px] w-auto object-contain rounded-xl border border-slate-800 shadow-2xl transition-all"
                  />
                  <p className="text-[11px] text-slate-400 italic mt-1">
                    Live preview — adjustments apply to every poster in the batch
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3 text-slate-600 text-center py-12">
                  <Eye className="h-12 w-12 stroke-[1.5]" />
                  <p className="text-xs font-medium text-slate-400">Loading live preview...</p>
                </div>
              )}
            </div>

            {/* Launch Batch Job Button */}
            {previewB64 && (
              <button
                type="button"
                onClick={handleStartBatchJob}
                disabled={startLoading || (jobId !== null && (statusStr === "processing" || statusStr === "queued"))}
                className="w-full py-4 px-6 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-2xl shadow-xl shadow-emerald-600/25 flex items-center justify-center gap-2 transition-all text-sm disabled:opacity-50"
              >
                {startLoading ? (
                  <>
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    <span>Launching Batch Job...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5" />
                    <span>Start Bulk Job (Generate All Posters into ZIP) 🚀</span>
                  </>
                )}
              </button>
            )}

            {/* Active Batch Progress Tracker Card */}
            {jobId && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    {statusStr === "done" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                    ) : statusStr === "failed" ? (
                      <AlertCircle className="h-5 w-5 text-red-400" />
                    ) : (
                      <Clock className="h-5 w-5 text-amber-400 animate-pulse" />
                    )}
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white text-sm capitalize">
                        Status: <span className={statusStr === "done" ? "text-emerald-400" : statusStr === "failed" ? "text-red-400" : "text-amber-400"}>{statusStr}</span>
                      </span>

                      {/* Resume button for interrupted/failed/paused job */}
                      {(statusStr === "failed" || statusStr === "interrupted" || statusStr === "paused") && (
                        <button
                          type="button"
                          onClick={handleResumeBatchJob}
                          disabled={startLoading}
                          className="py-1 px-3 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-medium flex items-center gap-1 transition-all disabled:opacity-50 ml-1"
                        >
                          <RotateCcw className="h-3 w-3" />
                          <span>Resume 🔄</span>
                        </button>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    ID: {jobId.slice(0, 8)}...
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>Batch Progress</span>
                    <span>
                      {completedRows} / {totalRows} completed ({progressPercent}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden p-0.5 border border-slate-800">
                    <div
                      className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full rounded-full transition-all duration-300"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                {/* Counts Breakdown */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                    <p className="text-[10px] uppercase font-semibold text-slate-500">Completed</p>
                    <p className="text-lg font-bold text-emerald-400">{completedRows}</p>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                    <p className="text-[10px] uppercase font-semibold text-slate-500">Skipped</p>
                    <p className="text-lg font-bold text-amber-400">{skippedRows}</p>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                    <p className="text-[10px] uppercase font-semibold text-slate-500">Failed</p>
                    <p className="text-lg font-bold text-red-400">{failedRows}</p>
                  </div>
                </div>

                {/* ZIP Download Button */}
                {statusStr === "done" && downloadUrl && (
                  <div className="pt-2">
                    <a
                      href={`/api/proxy${downloadUrl}`}
                      download
                      className="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition-all text-xs"
                    >
                      <Download className="h-4 w-4" />
                      <span>Download Bulk Posters Package (ZIP)</span>
                    </a>
                  </div>
                )}

                {/* Resume Interrupted Job Button */}
                {statusStr !== "done" && statusStr !== "processing" && statusStr !== "queued" && (
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={handleResumeBatchJob}
                      disabled={startLoading}
                      className="w-full py-3.5 px-4 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-semibold rounded-xl shadow-lg shadow-amber-600/20 flex items-center justify-center gap-2 transition-all text-xs disabled:opacity-50"
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span>Resume Interrupted Batch (From Checkpoint) 🔄</span>
                    </button>
                  </div>
                )}

                {statusStr === "failed" && jobErr && (
                  <div className="p-3 bg-red-950/60 border border-red-900 rounded-xl text-red-200 text-xs">
                    Job Error: {jobErr}
                  </div>
                )}

              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BulkGeneratePage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-slate-400 text-xs">Loading bulk generator...</div>
      }
    >
      <BulkGenerateContent />
    </Suspense>
  );
}
