"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { Zone } from "@/components/ZoneCanvas";
import {
  canvasObjectsToOverlayLayers,
  validateLayers,
  OverlayLayer,
  ZoneConfig,
} from "@/lib/zoneMapper";
import {
  LayoutGrid,
  Plus,
  Trash2,
  Save,
  Upload,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Layers,
  Eye,
  FileCode,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const ZoneCanvas = dynamic(() => import("@/components/ZoneCanvas"), {
  ssr: false,
});

export default function AddTemplatePage() {
  const [templateName, setTemplateName] = useState("custom_001");
  const [existingCategories, setExistingCategories] = useState<string[]>([]);
  const [selectedCategoryOption, setSelectedCategoryOption] = useState("greetings");
  const [customCategory, setCustomCategory] = useState("");
  const [description, setDescription] = useState("");

  const [baseImageSrc, setBaseImageSrc] = useState<string | null>(null);
  const [uploadedFileB64, setUploadedFileB64] = useState<string | null>(null);
  const [imgDimensions, setImgDimensions] = useState<{ w: number; h: number }>({
    w: 1024,
    h: 1536,
  });

  const [zones, setZones] = useState<Zone[]>([
    {
      id: "headline",
      type: "text",
      x: 40,
      y: 40,
      width: 400,
      height: 60,
      label: "headline",
      instruction: "Main title text",
      font_family: "Poppins",
      font_size: 48,
      font_size_min: 20,
      font_weight: "bold",
      color: "#FFFFFF",
      align: "center",
      llm_can_invent: true,
    },
  ]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [expandedZoneIds, setExpandedZoneIds] = useState<Record<string, boolean>>({
    headline: true,
  });

  const [overlayLayers, setOverlayLayers] = useState<OverlayLayer[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [samplePreviewB64, setSamplePreviewB64] = useState<string | null>(null);
  const [showJsonExpander, setShowJsonExpander] = useState(false);

  const [loading, setLoading] = useState(false);
  const [renderingSample, setRenderingSample] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Load existing categories
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const res = await fetch("/api/proxy/agent/categories");
        if (res.ok) {
          const data = await res.json();
          if (data.categories && Array.isArray(data.categories)) {
            setExistingCategories(data.categories);
            if (data.categories.length > 0) {
              setSelectedCategoryOption(data.categories[0]);
            }
          }
        }
      } catch (err) {
        console.error("Failed to load categories:", err);
      }
    };
    loadCategories();
  }, []);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const b64 = evt.target?.result as string;
      setUploadedFileB64(b64);
      setBaseImageSrc(b64);

      const img = new Image();
      img.onload = () => {
        setImgDimensions({ w: img.width, h: img.height });
      };
      img.src = b64;
    };
    reader.readAsDataURL(file);
  };

  const updateZoneField = (id: string, key: string, val: any) => {
    setZones(zones.map((z) => (z.id === id ? { ...z, [key]: val } : z)));
  };

  const deleteZone = (id: string) => {
    setZones(zones.filter((z) => z.id !== id));
    if (selectedZoneId === id) setSelectedZoneId(null);
  };

  const toggleZoneExpand = (id: string) => {
    setExpandedZoneIds((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const buildAndValidateOverlay = (): { scaledLayers: OverlayLayer[]; errors: string[] } => {
    const DISPLAY_W = 680;
    const scale = DISPLAY_W / imgDimensions.w;
    const DISPLAY_H = Math.round(imgDimensions.h * scale);

    const canvasObjects = zones.map((z) => ({
      type: "rect",
      id: z.id,
      left: z.x,
      top: z.y,
      width: z.width,
      height: z.height,
    }));

    const fieldConfigs: Record<string, ZoneConfig> = {};
    zones.forEach((z, idx) => {
      fieldConfigs[String(idx)] = {
        id: z.id,
        type: z.type,
        instruction: z.instruction,
        llm_can_invent: z.llm_can_invent,
        font_family: z.font_family,
        font_size: z.font_size,
        font_size_min: z.font_size_min,
        font_weight: z.font_weight,
        color: z.color,
        align: z.align,
        shape: z.shape,
        border_color: z.border_color,
        border_width: z.border_width,
      };
    });

    const scaledLayers = canvasObjectsToOverlayLayers(
      canvasObjects,
      fieldConfigs,
      imgDimensions.w,
      imgDimensions.h,
      DISPLAY_W,
      DISPLAY_H
    );

    const errors = validateLayers(
      scaledLayers,
      imgDimensions.w,
      imgDimensions.h
    );

    setOverlayLayers(scaledLayers);
    setValidationErrors(errors);
    return { scaledLayers, errors };
  };

  const handleRenderSamplePreview = async () => {
    const { scaledLayers, errors } = buildAndValidateOverlay();
    if (errors.length > 0) return;

    if (!uploadedFileB64) {
      setMessage("Please upload a base template PNG image first.");
      return;
    }

    setRenderingSample(true);
    setMessage(null);

    try {
      const res = await fetch("/api/proxy/agent/render-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          overlay: {
            canvas: { width: imgDimensions.w, height: imgDimensions.h },
            overlay_layers: scaledLayers,
          },
          image_b64: uploadedFileB64,
        }),
      });

      const json = await res.json();
      if (!res.ok || json.detail) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Sample render failed"
        );
      }

      setSamplePreviewB64(json.image_b64);
    } catch (err: any) {
      setMessage(err.message || "Failed to render sample preview.");
    } finally {
      setRenderingSample(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    const finalCategory =
      selectedCategoryOption === "Create new folder..."
        ? customCategory.trim().toLowerCase()
        : selectedCategoryOption.trim();

    if (!templateName.trim() || !finalCategory) {
      setMessage("Please enter both Template ID and Category Folder Name.");
      return;
    }

    if (!uploadedFileB64) {
      setMessage("Please upload a base template PNG image.");
      return;
    }

    const { scaledLayers, errors } = buildAndValidateOverlay();
    if (errors.length > 0) {
      return;
    }

    setLoading(true);
    setMessage(null);

    const overlay = {
      canvas: { width: imgDimensions.w, height: imgDimensions.h },
      overlay_layers: scaledLayers,
    };

    try {
      const res = await fetch("/api/proxy/agent/save-template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: finalCategory,
          template_base_id: templateName.trim(),
          user_hint: description.trim(),
          overlay,
          image_b64: uploadedFileB64,
        }),
      });

      const json = await res.json();
      if (!res.ok || json.detail) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Save failed"
        );
      }

      setMessage(
        json.message ||
          `Saved as ${json.template_id} in ${json.folder}/ — searchable immediately!`
      );
    } catch (err: any) {
      setMessage(err.message || "Failed to save template.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <LayoutGrid className="h-6 w-6 text-purple-400" />
          Manual Template Registration & Zone Mapper
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Upload base PNG background, drag mouse directly on canvas to draw placeholder zones, render sample preview labels, and register template.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Metadata Form */}
          <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Template Metadata
            </h3>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                Category folder name
              </label>
              <select
                value={selectedCategoryOption}
                onChange={(e) => setSelectedCategoryOption(e.target.value)}
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 text-xs focus:ring-2 focus:ring-purple-500"
              >
                {existingCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
                <option value="Create new folder...">Create new folder...</option>
              </select>
            </div>

            {selectedCategoryOption === "Create new folder..." && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Enter new category folder name
                </label>
                <input
                  type="text"
                  value={customCategory}
                  onChange={(e) => setCustomCategory(e.target.value)}
                  placeholder="e.g. diwali"
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                Subfolder/Template base ID *
              </label>
              <input
                type="text"
                required
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="e.g. poster_001"
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                Brief description
              </label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Detailed description of template..."
                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 text-xs resize-none focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                Base Template PNG Artwork *
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-800 hover:border-purple-500/50 bg-slate-950/40 rounded-xl p-4 cursor-pointer text-center gap-2 flex flex-col items-center"
              >
                <Upload className="h-5 w-5 text-purple-400" />
                {baseImageSrc ? (
                  <span className="text-xs text-purple-300 font-medium">
                    Image Loaded ({imgDimensions.w} × {imgDimensions.h} px)
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">
                    Click to select background PNG image
                  </span>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png, image/jpeg"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </div>
            </div>

            {/* Validation Warnings */}
            {validationErrors.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-950/60 border border-amber-800 text-amber-200 text-xs space-y-1">
                <div className="flex items-center gap-1 font-semibold text-amber-300">
                  <AlertTriangle className="h-3.5 w-3.5" /> Validation Errors:
                </div>
                {validationErrors.map((err, idx) => (
                  <p key={idx}>• {err}</p>
                ))}
              </div>
            )}

            {/* Save Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold rounded-xl shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 transition-all text-xs disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              <span>Generate tags and save</span>
            </button>

            {message && (
              <div className="p-3.5 rounded-xl bg-purple-950/60 border border-purple-800 text-purple-200 text-xs flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-purple-400 shrink-0" />
                <span>{message}</span>
              </div>
            )}
          </div>

          {/* Right Mouse Canvas Drawing */}
          <div className="lg:col-span-8 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Layers className="h-4 w-4 text-purple-400" />
                  Interactive Zone Canvas (Drag mouse to draw)
                </h3>
                <span className="text-[11px] font-mono text-slate-500">
                  {imgDimensions.w} × {imgDimensions.h} px
                </span>
              </div>

              <div className="flex justify-center">
                <ZoneCanvas
                  imageSrc={baseImageSrc || undefined}
                  zones={zones}
                  onZonesChange={setZones}
                  selectedZoneId={selectedZoneId}
                  onSelectZone={setSelectedZoneId}
                  width={680}
                  height={Math.round((680 / imgDimensions.w) * imgDimensions.h)}
                />
              </div>
            </div>

            {/* Field Configuration Cards (Streamlit Architecture) */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-white">
                {zones.length} box(es) placed. Configure below:
              </h3>

              <div className="space-y-4">
                {zones.map((z, idx) => {
                  const zoneKey = z._key || `zone_${idx}`;
                  const isExpanded = expandedZoneIds[zoneKey] ?? (idx === 0);
                  const isText = z.type === "text";

                  return (
                    <div
                      key={zoneKey}
                      className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl"
                    >
                      <div
                        onClick={() => toggleZoneExpand(zoneKey)}
                        className="p-4 bg-slate-950/70 hover:bg-slate-800/80 cursor-pointer flex items-center justify-between border-b border-slate-800 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <span className="h-6 w-6 rounded-lg bg-purple-600/30 text-purple-300 font-bold text-xs flex items-center justify-center">
                            {idx + 1}
                          </span>
                          <span className="font-semibold text-xs text-white">
                            Field {idx + 1}: {z.id} ({z.type})
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteZone(z.id);
                            }}
                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4 text-slate-400" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-slate-400" />
                          )}
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-900">
                          {/* Column 1 */}
                          <div className="space-y-4">
                            <div>
                              <label className="block text-xs font-semibold text-slate-300 mb-1">
                                Field ID (must match Excel column name)
                              </label>
                              <input
                                type="text"
                                value={z.id}
                                onChange={(e) =>
                                  updateZoneField(z.id, "id", e.target.value)
                                }
                                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-semibold text-slate-300 mb-1">
                                Field type
                              </label>
                              <select
                                value={z.type}
                                onChange={(e) =>
                                  updateZoneField(
                                    z.id,
                                    "type",
                                    e.target.value as "text" | "image"
                                  )
                                }
                                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                              >
                                <option value="text">text</option>
                                <option value="image">image</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-xs font-semibold text-slate-300 mb-1">
                                Instruction for AI
                              </label>
                              <input
                                type="text"
                                value={z.instruction ?? ""}
                                placeholder={`Describe value or purpose for ${z.id}`}
                                onChange={(e) =>
                                  updateZoneField(
                                    z.id,
                                    "instruction",
                                    e.target.value
                                  )
                                }
                                className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                              />
                            </div>

                            <div className="flex items-center gap-2 pt-1">
                              <input
                                type="checkbox"
                                id={`add_llmi_${z.id}`}
                                checked={z.llm_can_invent ?? false}
                                onChange={(e) =>
                                  updateZoneField(
                                    z.id,
                                    "llm_can_invent",
                                    e.target.checked
                                  )
                                }
                                className="h-4 w-4 accent-purple-600 rounded border-slate-800 cursor-pointer"
                              />
                              <label
                                htmlFor={`add_llmi_${z.id}`}
                                className="text-xs text-slate-300 cursor-pointer"
                              >
                                AI can generate this if not provided
                              </label>
                            </div>
                          </div>

                          {/* Column 2 */}
                          <div className="space-y-4">
                            {isText ? (
                              <>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Font
                                  </label>
                                  <select
                                    value={z.font_family || "Poppins"}
                                    onChange={(e) =>
                                      updateZoneField(
                                        z.id,
                                        "font_family",
                                        e.target.value
                                      )
                                    }
                                    className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                  >
                                    <option value="Poppins">Poppins</option>
                                    <option value="NotoSans">NotoSans</option>
                                    <option value="NotoSansDevanagari">
                                      NotoSansDevanagari
                                    </option>
                                  </select>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                  <div>
                                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                                      Font size
                                    </label>
                                    <input
                                      type="number"
                                      min={8}
                                      max={200}
                                      value={z.font_size ?? 48}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "font_size",
                                          parseInt(e.target.value) || 24
                                        )
                                      }
                                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                    />
                                  </div>

                                  <div>
                                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                                      Min font size
                                    </label>
                                    <input
                                      type="number"
                                      min={6}
                                      max={100}
                                      value={z.font_size_min ?? 20}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "font_size_min",
                                          parseInt(e.target.value) || 12
                                        )
                                      }
                                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                    />
                                  </div>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                  <div>
                                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                                      Weight
                                    </label>
                                    <select
                                      value={z.font_weight || "bold"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "font_weight",
                                          e.target.value
                                        )
                                      }
                                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                    >
                                      <option value="bold">bold</option>
                                      <option value="normal">normal</option>
                                      <option value="semibold">semibold</option>
                                    </select>
                                  </div>

                                  <div>
                                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                                      Align
                                    </label>
                                    <select
                                      value={z.align || "center"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "align",
                                          e.target.value
                                        )
                                      }
                                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                    >
                                      <option value="center">center</option>
                                      <option value="left">left</option>
                                      <option value="right">right</option>
                                    </select>
                                  </div>
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Text colour
                                  </label>
                                  <div className="flex gap-2 items-center">
                                    <input
                                      type="color"
                                      value={z.color || "#FFFFFF"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "color",
                                          e.target.value
                                        )
                                      }
                                      className="h-9 w-12 bg-transparent cursor-pointer"
                                    />
                                    <input
                                      type="text"
                                      value={z.color || "#FFFFFF"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "color",
                                          e.target.value
                                        )
                                      }
                                      className="flex-1 p-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-slate-200"
                                    />
                                  </div>
                                </div>
                              </>
                            ) : (
                              <>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Shape
                                  </label>
                                  <select
                                    value={z.shape || "circle"}
                                    onChange={(e) =>
                                      updateZoneField(
                                        z.id,
                                        "shape",
                                        e.target.value
                                      )
                                    }
                                    className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100"
                                  >
                                    <option value="circle">circle</option>
                                    <option value="rectangle">rectangle</option>
                                  </select>
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Border width px
                                  </label>
                                  <input
                                    type="number"
                                    min={0}
                                    max={20}
                                    value={z.border_width ?? 4}
                                    onChange={(e) =>
                                      updateZoneField(
                                        z.id,
                                        "border_width",
                                        parseInt(e.target.value) || 0
                                      )
                                    }
                                    className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100"
                                  />
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Border colour
                                  </label>
                                  <div className="flex gap-2 items-center">
                                    <input
                                      type="color"
                                      value={z.border_color || "#FFFFFF"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "border_color",
                                          e.target.value
                                        )
                                      }
                                      className="h-9 w-12 bg-transparent cursor-pointer"
                                    />
                                    <input
                                      type="text"
                                      value={z.border_color || "#FFFFFF"}
                                      onChange={(e) =>
                                        updateZoneField(
                                          z.id,
                                          "border_color",
                                          e.target.value
                                        )
                                      }
                                      className="flex-1 p-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-slate-200"
                                    />
                                  </div>
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Sample Render Section */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <button
                type="button"
                onClick={handleRenderSamplePreview}
                disabled={renderingSample}
                className="w-full py-3.5 px-4 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-600/25 transition-all disabled:opacity-50"
              >
                {renderingSample ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
                <span>Render preview with sample values</span>
              </button>

              {samplePreviewB64 && (
                <div className="flex flex-col items-center gap-2 bg-slate-950 p-4 rounded-xl border border-slate-800 shadow-2xl">
                  {/* eslint-disable-next-html-element-suppression */}
                  <img
                    src={samplePreviewB64}
                    alt="Sample Render Preview"
                    className="max-h-[500px] w-auto object-contain rounded-lg border border-slate-800"
                  />
                  <p className="text-[11px] text-slate-400 italic mt-1">
                    Sample preview — field names shown as labels
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
