"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useTabState } from "@/context/TabStateContext";
import dynamic from "next/dynamic";
import {
  createAgentConversation,
  getAgentState,
  getConversationMessages,
  agentChat,
  rebuildPrompt,
  refinePrompt,
  generateAgentImage,
} from "@/lib/api";
import { useGenerationStatusMessages } from "@/hooks/useGenerationStatusMessages";
import { Zone } from "@/components/ZoneCanvas";
import {
  canvasObjectsToOverlayLayers,
  validateLayers,
  OverlayLayer,
  ZoneConfig,
} from "@/lib/zoneMapper";
import {
  Wand2,
  Send,
  RefreshCw,
  Sparkles,
  Image as ImageIcon,
  Layers,
  Check,
  Plus,
  Trash2,
  ChevronRight,
  ArrowLeft,
  Upload,
  AlertTriangle,
  Save,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Eye,
  FileCode,
  Hammer,
  Sliders,
} from "lucide-react";

// Dynamically import Konva component with SSR disabled
const ZoneCanvas = dynamic(() => import("@/components/ZoneCanvas"), {
  ssr: false,
});

const DEFAULT_ASSUMPTIONS_KEYS = [
  "occasion",
  "purpose",
  "audience",
  "colour_palette",
  "style",
  "layout_composition",
  "text_placeholders",
  "photo_placeholders",
  "logo_position",
  "mascot_position",
];

function CreateTemplateContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const convoIdParam = searchParams.get("id");

  const { state, updateState, resetState } = useTabState("agent");

  const [conversationId, setConversationId] = useState<string | null>(convoIdParam);
  
  const step = state.step ?? 1;
  const setStep = (val: number | ((prev: number) => number)) => updateState({ step: val });

  // Step 1: Chat & Assumption state
  const messages = state.messages ?? [];
  const setMessages = (val: any) => updateState({ messages: val });

  const chatInput = state.chatInput ?? "";
  const setChatInput = (val: string) => updateState({ chatInput: val });

  const assumptions = state.assumptions ?? {
    occasion: "",
    purpose: "",
    audience: "",
    colour_palette: "",
    style: "",
    layout_composition: "",
    text_placeholders: "",
    photo_placeholders: "",
    logo_position: "",
    mascot_position: "",
  };
  const setAssumptions = (val: any) => updateState({ assumptions: val });

  const userEdits = state.userEdits ?? "";
  const setUserEdits = (val: string) => updateState({ userEdits: val });

  const generatedPrompt = state.generatedPrompt ?? "";
  const setGeneratedPrompt = (val: string) => updateState({ generatedPrompt: val });

  const refinementInput = state.refinementInput ?? "";
  const setRefinementInput = (val: string) => updateState({ refinementInput: val });

  const isReady = state.isReady ?? false;
  const setIsReady = (val: boolean) => updateState({ isReady: val });

  const [rebuilding, setRebuilding] = useState(false);
  const [refining, setRefining] = useState(false);

  // Step 2: Image state
  const baseImageSrc = state.baseImageSrc ?? null;
  const setBaseImageSrc = (val: string | null) => updateState({ baseImageSrc: val });

  const uploadedFileB64 = state.uploadedFileB64 ?? null;
  const setUploadedFileB64 = (val: string | null) => updateState({ uploadedFileB64: val });

  const imgDimensions = state.imgDimensions ?? { w: 1024, h: 1536 };
  const setImgDimensions = (val: { w: number; h: number }) => updateState({ imgDimensions: val });

  // Step 3: Zone Drawing state
  const zones = state.zones ?? [
    {
      id: "headline",
      type: "text",
      x: 40,
      y: 40,
      width: 400,
      height: 60,
      label: "headline",
      instruction: "Main title greeting line for poster",
      font_family: "Poppins",
      font_size: 48,
      font_size_min: 20,
      font_weight: "bold",
      color: "#FFFFFF",
      align: "center",
      llm_can_invent: true,
    },
    {
      id: "user_photo",
      type: "image",
      x: 140,
      y: 150,
      width: 200,
      height: 200,
      label: "user_photo",
      instruction: "Upload profile photo to place here",
      shape: "circle",
      border_color: "#FFFFFF",
      border_width: 4,
      llm_can_invent: false,
    },
  ];
  const setZones = (val: any) => updateState({ zones: val });

  const selectedZoneId = state.selectedZoneId ?? null;
  const setSelectedZoneId = (val: string | null) => updateState({ selectedZoneId: val });

  const expandedZoneIds = state.expandedZoneIds ?? { headline: true };
  const setExpandedZoneIds = (val: any) => updateState({ expandedZoneIds: val });

  // Step 4: Overlay & Sample Preview state
  const overlayLayers = state.overlayLayers ?? [];
  const setOverlayLayers = (val: OverlayLayer[]) => updateState({ overlayLayers: val });

  const validationErrors = state.validationErrors ?? [];
  const setValidationErrors = (val: string[]) => updateState({ validationErrors: val });

  const samplePreviewB64 = state.samplePreviewB64 ?? null;
  const setSamplePreviewB64 = (val: string | null) => updateState({ samplePreviewB64: val });

  const showJsonExpander = state.showJsonExpander ?? false;
  const setShowJsonExpander = (val: boolean) => updateState({ showJsonExpander: val });

  const [renderingSample, setRenderingSample] = useState(false);

  // Step 5: Save State
  const [existingCategories, setExistingCategories] = useState<string[]>([]);
  const selectedCategoryOption = state.selectedCategoryOption ?? "";
  const setSelectedCategoryOption = (val: any) => updateState({ selectedCategoryOption: val });

  const customCategory = state.customCategory ?? "";
  const setCustomCategory = (val: string) => updateState({ customCategory: val });

  const templateBaseId = state.templateBaseId ?? "festival_001";
  const setTemplateBaseId = (val: string) => updateState({ templateBaseId: val });

  const userHint = state.userHint ?? "";
  const setUserHint = (val: string) => updateState({ userHint: val });

  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<"idle" | "generating" | "success" | "error">("idle");
  const { currentMessage } = useGenerationStatusMessages(generationStatus);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load existing categories from backend
  const loadCategories = async () => {
    try {
      const res = await fetch("/api/proxy/agent/categories");
      if (res.ok) {
        const data = await res.json();
        if (data.categories && Array.isArray(data.categories)) {
          setExistingCategories(data.categories);
          if (data.categories.length > 0) {
            // Only auto-set if user hasn't already picked something
            setSelectedCategoryOption((prev) => prev || data.categories[0]);
          }
        }
      }
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  };

  // Init or restore conversation
  useEffect(() => {
    const initConvo = async () => {
      setLoading(true);
      setError(null);
      try {
        loadCategories();
        if (convoIdParam) {
          resetState();
          setConversationId(convoIdParam);
          const convoData = await getConversationMessages(convoIdParam);
          if (convoData.messages) {
            setMessages(
              convoData.messages.map((m) => ({
                role: m.role,
                content: m.content,
              }))
            );
          }
          const stateData = await getAgentState(convoIdParam);
          if (stateData) {
            if (stateData.assumptions) {
              setAssumptions((prev) => ({ ...prev, ...stateData.assumptions }));
            }
            if (stateData.generated_prompt) {
              setGeneratedPrompt(stateData.generated_prompt);
              setIsReady(true);
            }
          }
        } else {
          const newConvo = await createAgentConversation();
          setConversationId(newConvo.conversation_id);
          
          // Initial greeting from agent
          const chatRes = await agentChat(newConvo.conversation_id, "");
          setMessages([
            {
              role: "assistant",
              content: chatRes.reply || "Hello! What kind of poster template would you like to design today?",
            },
          ]);
          if (chatRes.assumptions) {
            setAssumptions((prev) => ({ ...prev, ...chatRes.assumptions }));
          }
          if (chatRes.ready) setIsReady(true);
          if (chatRes.generated_prompt) setGeneratedPrompt(chatRes.generated_prompt);
        }
      } catch (err: any) {
        console.warn("Failed to initialize agent session:", err.message);
        if (convoIdParam) {
          router.replace("/create-template");
        } else {
          setError(err.message || "Failed to initialize agent session.");
        }
      } finally {
        setLoading(false);
      }
    };

    initConvo();
  }, [convoIdParam]);

  const handleSendChat = async () => {
    if (!chatInput.trim() || !conversationId) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setMessages((prev) => [...(prev || []), { role: "user", content: userMsg }]);
    setLoading(true);
    setError(null);

    try {
      const res = await agentChat(conversationId, userMsg);
      if (res.reply) {
        setMessages((prev) => [
          ...(prev || []),
          { role: "assistant", content: res.reply },
        ]);
      }
      if (res.assumptions) {
        setAssumptions((prev) => ({ ...(prev || {}), ...res.assumptions }));
      }
      if (res.ready) setIsReady(true);
      if (res.generated_prompt) setGeneratedPrompt(res.generated_prompt);
    } catch (err: any) {
      setError(err.message || "Failed to communicate with template agent.");
    } finally {
      setLoading(false);
    }
  };

  const handleRebuildPromptFromAssumptions = async () => {
    if (!conversationId) return;
    setRebuilding(true);
    setError(null);

    try {
      const res = await rebuildPrompt(conversationId, assumptions, userEdits);
      if (res.generated_prompt) {
        setGeneratedPrompt(res.generated_prompt);
        setIsReady(true);
      }
    } catch (err: any) {
      setError(err.message || "Failed to rebuild prompt.");
    } finally {
      setRebuilding(false);
    }
  };

  const handleRefinePromptWithAI = async () => {
    if (!conversationId || !refinementInput.trim()) return;
    setRefining(true);
    setError(null);

    try {
      const res = await refinePrompt(
        conversationId,
        refinementInput.trim(),
        generatedPrompt
      );
      if (res.generated_prompt) {
        setGeneratedPrompt(res.generated_prompt);
      }
      setRefinementInput("");
    } catch (err: any) {
      setError(err.message || "Failed to refine prompt.");
    } finally {
      setRefining(false);
    }
  };


  const handleGenerateImage = async () => {
    if (!conversationId) return;
    setGenerationStatus("generating");
    setError(null);

    try {
      const res = await generateAgentImage(conversationId);
      if (res.image_path) {
        setGenerationStatus("success");
        const imageUri = `/api/proxy/history/conversations/${conversationId}/image`;
        setBaseImageSrc(imageUri);

        const img = new Image();
        img.onload = () => {
          setImgDimensions({ w: img.width, h: img.height });
        };
        img.src = imageUri;

        // Wait 500ms for the success message to show before advancing
        setTimeout(() => {
          setGenerationStatus("idle");
          setStep(3); // Advance to Zone canvas step
        }, 500);
      } else {
        setGenerationStatus("error");
      }
    } catch (err: any) {
      setGenerationStatus("error");
      setError(err.message || "Failed to generate image for template.");
    }
  };

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
    setZones(
      zones.map((z) => (z.id === id ? { ...z, [key]: val } : z))
    );
  };

  const deleteZone = (id: string) => {
    setZones(zones.filter((z) => z.id !== id));
    if (selectedZoneId === id) setSelectedZoneId(null);
  };

  const toggleZoneExpand = (id: string) => {
    setExpandedZoneIds((prev) => {
      const current = prev || expandedZoneIds;
      return {
        ...current,
        [id]: !current[id],
      };
    });
  };

  const handleBuildOverlayAndPreview = () => {
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

    if (errors.length === 0) {
      setStep(4);
    }
  };

  const handleRenderSamplePreview = async () => {
    setRenderingSample(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/agent/render-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          overlay: {
            canvas: { width: imgDimensions.w, height: imgDimensions.h },
            overlay_layers: overlayLayers,
          },
          image_b64: uploadedFileB64,
          conversation_id: conversationId,
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
      setError(err.message || "Failed to render sample preview.");
    } finally {
      setRenderingSample(false);
    }
  };

  const handleSaveTemplate = async () => {
    const finalCategory =
      selectedCategoryOption === "Create new folder..."
        ? customCategory.trim().toLowerCase()
        : selectedCategoryOption.trim();

    if (!finalCategory || !templateBaseId.trim()) {
      setError("Both category and subfolder/template ID are required.");
      return;
    }

    setLoading(true);
    setError(null);

    const overlay = {
      canvas: { width: imgDimensions.w, height: imgDimensions.h },
      overlay_layers: overlayLayers,
    };

    try {
      const res = await fetch("/api/proxy/agent/save-template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: finalCategory,
          template_base_id: templateBaseId.trim(),
          user_hint: userHint.trim() || generatedPrompt,
          overlay,
          image_b64: uploadedFileB64,
          conversation_id: conversationId,
        }),
      });

      const json = await res.json();
      if (!res.ok || json.detail) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Save failed"
        );
      }

      setSaveSuccessMessage(
        json.message ||
          `Saved as ${json.template_id} in ${json.folder} - searchable immediately!`
      );
    } catch (err: any) {
      setError(err.message || "Save template failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Wand2 className="h-6 w-6 text-purple-400" />
            AI Template Creator
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            5-Step Wizard: Creative Director AI chat, editable design assumptions, prompt refinement, artwork generation & zone mapping.
          </p>
        </div>

        {/* Wizard Steps Indicator */}
        <div className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-2 rounded-xl text-xs">
          {[
            { num: 1, label: "Describe" },
            { num: 2, label: "Base Image" },
            { num: 3, label: "Zone Mapper" },
            { num: 4, label: "Preview" },
            { num: 5, label: "Save" },
          ].map((s) => (
            <div
              key={s.num}
              onClick={() => setStep(s.num)}
              className={`h-8 px-3 rounded-lg flex items-center gap-1.5 font-bold cursor-pointer transition-all ${
                step === s.num
                  ? "bg-purple-600 text-slate-900 dark:text-white shadow-md shadow-purple-600/30"
                  : step > s.num
                  ? "bg-purple-950/60 text-purple-300 border border-purple-800/50"
                  : "bg-slate-50 dark:bg-slate-950 text-slate-600"
              }`}
            >
              <span>{s.num}.</span>
              <span className="hidden sm:inline font-medium text-[11px]">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs">
          {error}
        </div>
      )}

      {/* STEP 1: Creative Director Chat & Refinable Design Assumptions */}
      {step === 1 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Creative Director Chat */}
          <div className="lg:col-span-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 flex flex-col h-[600px] shadow-xl">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-4 flex items-center gap-2">
              <Wand2 className="h-4 w-4 text-purple-400" />
              Creative Director Chat
            </h3>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 mb-4">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    m.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] p-3.5 rounded-2xl text-xs leading-relaxed ${
                      m.role === "user"
                        ? "bg-indigo-600 text-slate-900 dark:text-white rounded-br-none shadow-md"
                        : "bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none"
                    }`}
                  >
                    {m.content}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
                placeholder="Message the Creative Director..."
                className="flex-1 p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 text-xs"
              />
              <button
                onClick={handleSendChat}
                disabled={loading}
                className="p-3 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white rounded-xl shadow-md transition-all disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Right Column: Design Details & Customization (Form for Assumptions & Prompt Refinement) */}
          <div className="lg:col-span-6 space-y-6">
            {/* Editable Assumptions Form */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-purple-400" />
                  Editable Design Assumptions
                </h3>
                <span className="text-[10px] text-slate-500">Inferred by AI Agent</span>
              </div>

              <p className="text-xs text-slate-600 dark:text-slate-400">
                Review or refine the design assumptions extracted by the Creative Director:
              </p>

              <div className="grid grid-cols-2 gap-3 max-h-[260px] overflow-y-auto pr-1">
                {DEFAULT_ASSUMPTIONS_KEYS.map((key) => (
                  <div key={key}>
                    <label className="block text-[10px] font-semibold text-slate-600 dark:text-slate-400 capitalize mb-1">
                      {key.replace(/_/g, " ")}
                    </label>
                    <input
                      type="text"
                      value={assumptions[key] || ""}
                      onChange={(e) =>
                        setAssumptions({
                          ...assumptions,
                          [key]: e.target.value,
                        })
                      }
                      placeholder={`e.g. ${key.replace(/_/g, " ")}`}
                      className="w-full p-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-xs text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-purple-500 focus:outline-none"
                    />
                  </div>
                ))}
              </div>

              <div>
                <label className="block text-[10px] font-semibold text-slate-600 dark:text-slate-400 uppercase mb-1">
                  Additional Visual Constraints / Styling Instructions
                </label>
                <textarea
                  rows={2}
                  value={userEdits}
                  onChange={(e) => setUserEdits(e.target.value)}
                  placeholder="e.g., Use corporate dark red gradients, keep text areas minimalistic..."
                  className="w-full p-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-xs text-slate-800 dark:text-slate-200 resize-none focus:ring-1 focus:ring-purple-500 focus:outline-none"
                />
              </div>

              <button
                onClick={handleRebuildPromptFromAssumptions}
                disabled={rebuilding}
                className="w-full py-2.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-darkpurple-300 border border-slate-700 font-medium rounded-xl text-xs flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {rebuilding ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Hammer className="h-4 w-4" />
                )}
                <span>Rebuild Prompt from Assumptions</span>
              </button>
            </div>

            {/* Generated Prompt Editor & Refinement */}
            {(isReady || generatedPrompt) && (
              <div className="bg-white dark:bg-slate-900 border border-purple-900/40 rounded-2xl p-6 shadow-xl space-y-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-800 dark:text-purple-300 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-purple-700 dark:text-purple-400" />
                  Image Generation Prompt
                </h3>

                <div>
                  <label className="block text-[10px] text-slate-600 dark:text-slate-400 uppercase font-semibold mb-1">
                    Edit Prompt directly if needed
                  </label>
                  <textarea
                    rows={3}
                    value={generatedPrompt}
                    onChange={(e) => setGeneratedPrompt(e.target.value)}
                    className="w-full p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-mono text-purple-700 dark:text-purple-200 focus:ring-2 focus:ring-purple-500 focus:outline-none resize-none"
                  />
                </div>

                {/* Refinement with AI */}
                <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                    Refinement Instructions
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={refinementInput}
                      onChange={(e) => setRefinementInput(e.target.value)}
                      placeholder="e.g., make it a darker blue background, make it look more premium"
                      className="flex-1 p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-purple-500 focus:outline-none"
                    />
                    <button
                      onClick={handleRefinePromptWithAI}
                      disabled={refining || !refinementInput.trim()}
                      className="py-2 px-3 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white font-medium rounded-lg text-xs flex items-center gap-1 transition-all disabled:opacity-50 shrink-0"
                    >
                      {refining ? (
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Wand2 className="h-3.5 w-3.5" />
                      )}
                      <span>Refine Prompt with AI </span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={handleGenerateImage}
                      disabled={generationStatus !== "idle" && generationStatus !== "error"}
                      className="py-3 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-slate-900 dark:text-white font-semibold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-600/20 w-full disabled:opacity-80 disabled:cursor-not-allowed"
                      aria-live="polite"
                    >
                      {generationStatus === "generating" || generationStatus === "success" ? (
                        <RefreshCw className="h-4 w-4 animate-spin shrink-0" />
                      ) : (
                        <Sparkles className="h-4 w-4 shrink-0" />
                      )}
                      <span className="truncate">
                        {generationStatus === "idle" || generationStatus === "error" 
                          ? "Generate Image with AI" 
                          : currentMessage}
                      </span>
                    </button>
                    {(generationStatus === "generating" || generationStatus === "success") && (
                      <div className="h-1 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden relative">
                        <div className="absolute top-0 left-0 h-full bg-gradient-to-r from-purple-400 to-indigo-400 w-1/2 animate-[shimmer_1.5s_infinite_linear]" style={{ transformOrigin: 'left', animation: 'shimmer 1.5s infinite linear' }} />
                        <style>{`
                          @keyframes shimmer {
                            0% { transform: translateX(-100%); }
                            100% { transform: translateX(200%); }
                          }
                        `}</style>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => setStep(2)}
                    className="py-3 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-medium rounded-xl text-xs flex items-center justify-center gap-1 border border-slate-700"
                  >
                    <span>Skip AI image — upload PNG </span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 2: Base Image Generation/Upload */}
      {step === 2 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 max-w-2xl mx-auto space-y-6 shadow-xl text-center">
          <div className="flex flex-col items-center gap-3">
            <div className="h-12 w-12 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center">
              <ImageIcon className="h-6 w-6" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Generate Base Template Background
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400 max-w-md">
              AI will generate a high-resolution base artwork using the prompt built from your conversation assumptions, or upload your own PNG.
            </p>
          </div>

          {generatedPrompt && (
            <div className="p-4 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-purple-300 italic font-mono">
              "{generatedPrompt}"
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <button
                onClick={handleGenerateImage}
                disabled={generationStatus !== "idle" && generationStatus !== "error"}
                className="py-3.5 px-4 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white font-medium rounded-xl shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 text-xs transition-all w-full disabled:opacity-80 disabled:cursor-not-allowed"
                aria-live="polite"
              >
                {generationStatus === "generating" || generationStatus === "success" ? (
                  <RefreshCw className="h-4 w-4 animate-spin shrink-0" />
                ) : (
                  <Sparkles className="h-4 w-4 shrink-0" />
                )}
                <span className="truncate">
                  {generationStatus === "idle" || generationStatus === "error" 
                    ? "Generate Image via AI" 
                    : currentMessage}
                </span>
              </button>
              {(generationStatus === "generating" || generationStatus === "success") && (
                <div className="h-1 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden relative">
                  <div className="absolute top-0 left-0 h-full bg-purple-500 w-1/2 animate-[shimmer_1.5s_infinite_linear]" style={{ transformOrigin: 'left', animation: 'shimmer 1.5s infinite linear' }} />
                </div>
              )}
            </div>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="py-3.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-700 font-medium rounded-xl flex items-center justify-center gap-2 text-xs transition-all"
            >
              <Upload className="h-4 w-4 text-purple-400" />
              <span>Upload Custom PNG</span>
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/png, image/jpeg"
              onChange={handleFileUpload}
              className="hidden"
            />
          </div>

          {baseImageSrc && (
            <div className="p-4 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-purple-300">
              <span className="font-semibold">
                Image Loaded ({imgDimensions.w} × {imgDimensions.h} px)
              </span>
              <button
                onClick={() => setStep(3)}
                className="py-2 px-4 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white rounded-lg text-xs font-medium transition-all"
              >
                Continue with this Image
              </button>
            </div>
          )}

          <div className="flex justify-between items-center pt-6 border-t border-slate-200 dark:border-slate-800">
            <button
              onClick={() => setStep(1)}
              className="text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:text-white flex items-center gap-1"
            >
              <ArrowLeft className="h-4 w-4" /> Back to Chat
            </button>
            <button
              onClick={() => setStep(3)}
              className="py-2.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-900 dark:text-white font-medium rounded-xl text-xs"
            >
              Skip to Canvas Zone Mapping
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Zone Mapper (Streamlit Architecture & UX) */}
      {step === 3 && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl space-y-2">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Layers className="h-5 w-5 text-purple-400" />
              Draw placeholder boxes on your template
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Drag mouse directly on the template canvas below to draw rectangular text or image placeholder boxes. Configure each field in the cards under the canvas.
            </p>
          </div>

          <div className="flex flex-col items-center justify-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
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

          {zones.length === 0 ? (
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center text-slate-600 dark:text-slate-400 text-xs">
              Draw at least one box on the image above to configure layer properties.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {zones.length} box(es) placed. Configure below:
                </h3>
              </div>

              <div className="space-y-4">
                {zones.map((z, idx) => {
                  const zoneKey = z._key || `zone_${idx}`;
                  const isExpanded = expandedZoneIds[zoneKey] ?? (idx === 0);
                  const isText = z.type === "text";

                  return (
                    <div
                      key={zoneKey}
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xl"
                    >
                      <div
                        onClick={() => toggleZoneExpand(zoneKey)}
                        className="p-4 bg-slate-50 dark:bg-slate-950/70 hover:bg-slate-100 dark:bg-slate-800/80 cursor-pointer flex items-center justify-between border-b border-slate-200 dark:border-slate-800 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <span className="h-6 w-6 rounded-lg bg-purple-600/30 text-purple-300 font-bold text-xs flex items-center justify-center">
                            {idx + 1}
                          </span>
                          <span className="font-semibold text-xs text-slate-900 dark:text-white">
                            Field {idx + 1}: {z.id} ({z.type})
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteZone(z.id);
                            }}
                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                          )}
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-white dark:bg-slate-900">
                          {/* Left Column (c1) */}
                          <div className="space-y-4">
                            <div>
                              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                                Field ID (must match Excel column name)
                              </label>
                              <input
                                type="text"
                                value={z.id}
                                onChange={(e) =>
                                  updateZoneField(z.id, "id", e.target.value)
                                }
                                className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                              />
                            </div>

                            <div>
                              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500"
                              >
                                <option value="text">text</option>
                                <option value="image">image</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                              />
                            </div>

                            <div className="flex items-center gap-2 pt-1">
                              <input
                                type="checkbox"
                                id={`llm_invent_${z.id}`}
                                checked={z.llm_can_invent ?? false}
                                onChange={(e) =>
                                  updateZoneField(
                                    z.id,
                                    "llm_can_invent",
                                    e.target.checked
                                  )
                                }
                                className="h-4 w-4 accent-purple-600 rounded border-slate-200 dark:border-slate-800 cursor-pointer"
                              />
                              <label
                                htmlFor={`llm_invent_${z.id}`}
                                className="text-xs text-slate-700 dark:text-slate-300 cursor-pointer"
                              >
                                AI can generate this if not provided
                              </label>
                            </div>
                          </div>

                          {/* Right Column (c2) */}
                          <div className="space-y-4">
                            {isText ? (
                              <>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                    className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500"
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
                                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100"
                                    />
                                  </div>

                                  <div>
                                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100"
                                    />
                                  </div>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                  <div>
                                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500"
                                    >
                                      <option value="bold">bold</option>
                                      <option value="normal">normal</option>
                                      <option value="semibold">semibold</option>
                                    </select>
                                  </div>

                                  <div>
                                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500"
                                    >
                                      <option value="center">center</option>
                                      <option value="left">left</option>
                                      <option value="right">right</option>
                                    </select>
                                  </div>
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="flex-1 p-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-mono text-slate-800 dark:text-slate-200"
                                    />
                                  </div>
                                </div>
                              </>
                            ) : (
                              <>
                                <div>
                                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                    className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500"
                                  >
                                    <option value="circle">circle</option>
                                    <option value="rectangle">rectangle</option>
                                  </select>
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                    className="w-full p-2.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-slate-100"
                                  />
                                </div>

                                <div>
                                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
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
                                      className="flex-1 p-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-mono text-slate-800 dark:text-slate-200"
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

              <div className="flex justify-between items-center pt-4 border-t border-slate-200 dark:border-slate-800">
                <button
                  onClick={() => setStep(2)}
                  className="py-2.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs flex items-center gap-1"
                >
                  <ArrowLeft className="h-4 w-4" /> Back to upload
                </button>
                <button
                  onClick={handleBuildOverlayAndPreview}
                  className="py-3 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-slate-900 dark:text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-purple-600/20"
                >
                  <span>Build overlay and preview </span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 4: Preview (Sample Render Preview & Overlay Inspection) */}
      {step === 4 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 max-w-3xl mx-auto space-y-6 shadow-xl">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Preview your template</h2>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
              Inspect your overlay layer JSON configuration and render sample preview labels directly on the artwork.
            </p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowJsonExpander(!showJsonExpander)}
              className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-purple-300 hover:bg-white dark:bg-slate-900 transition-colors"
            >
              <span className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-purple-400" />
                overlay.json (click to inspect)
              </span>
              {showJsonExpander ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>

            {showJsonExpander && (
              <pre className="p-4 bg-slate-50 dark:bg-slate-950 text-[11px] font-mono text-slate-700 dark:text-slate-300 border-t border-slate-200 dark:border-slate-800 max-h-[300px] overflow-y-auto">
                {JSON.stringify(
                  {
                    canvas: { width: imgDimensions.w, height: imgDimensions.h },
                    overlay_layers: overlayLayers,
                  },
                  null,
                  2
                )}
              </pre>
            )}
          </div>

          <div className="space-y-4 pt-2">
            <button
              onClick={handleRenderSamplePreview}
              disabled={renderingSample}
              className="w-full py-3.5 px-4 bg-purple-600 hover:bg-purple-500 text-slate-900 dark:text-white font-medium rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-600/25 transition-all disabled:opacity-50"
            >
              {renderingSample ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              <span>Render preview with sample values</span>
            </button>

            {samplePreviewB64 && (
              <div className="flex flex-col items-center gap-2 bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl">
                {/* eslint-disable-next-html-element-suppression */}
                <img
                  src={samplePreviewB64}
                  alt="Sample Render Preview"
                  className="max-h-[500px] w-auto object-contain rounded-lg border border-slate-200 dark:border-slate-800"
                />
                <p className="text-[11px] text-slate-600 dark:text-slate-400 italic mt-1">
                  Sample preview — field names shown as labels
                </p>
              </div>
            )}
          </div>

          <div className="flex justify-between items-center pt-6 border-t border-slate-200 dark:border-slate-800">
            <button
              onClick={() => setStep(3)}
              className="py-2.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs flex items-center gap-1"
            >
              <ArrowLeft className="h-4 w-4" /> Revise boxes
            </button>
            <button
              onClick={() => setStep(5)}
              className="py-3 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-slate-900 dark:text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg"
            >
              <span>Looks good — save </span>
            </button>
          </div>
        </div>
      )}

      {/* STEP 5: Save (Category, Subfolder Validation, Tags & Indexing) */}
      {step === 5 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 max-w-2xl mx-auto space-y-6 shadow-xl">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Save your template</h2>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
              Select or create a category folder, choose template ID, and let AI generate search metadata for immediate index retrieval.
            </p>
          </div>

          {saveSuccessMessage ? (
            <div className="p-6 rounded-2xl bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-center space-y-4 shadow-2xl">
              <div className="h-12 w-12 rounded-xl bg-emerald-600/30 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle className="h-8 w-8" />
              </div>
              <p className="text-sm font-semibold leading-relaxed">
                {saveSuccessMessage}
              </p>
              <div className="pt-2 flex justify-center gap-3">
                <a
                  href="/generate"
                  className="py-2.5 px-5 bg-emerald-600 hover:bg-emerald-500 text-slate-900 dark:text-white font-medium rounded-xl text-xs transition-all shadow-md"
                >
                  Generate Poster Now
                </a>
                <button
                  onClick={() => setStep(1)}
                  className="py-2.5 px-5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-medium rounded-xl text-xs transition-all border border-slate-700"
                >
                  Create Another Template
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1">
                  Category folder name
                </label>
                <select
                  value={selectedCategoryOption}
                  onChange={(e) => setSelectedCategoryOption(e.target.value)}
                  className="w-full p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-purple-500"
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
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Enter new category folder name
                  </label>
                  <input
                    type="text"
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    placeholder="e.g. diwali"
                    className="w-full p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    Lowercase, no spaces. e.g. holi, diwali, hiring
                  </p>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1">
                  Subfolder/Template base ID
                </label>
                <input
                  type="text"
                  value={templateBaseId}
                  onChange={(e) => setTemplateBaseId(e.target.value)}
                  placeholder="e.g. diwali"
                  className="w-full p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                  Cannot match the category folder name or any other category folder name. If name already exists in target category, system saves with sequential number automatically.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1">
                  Brief description (AI will enrich this for better search)
                </label>
                <textarea
                  rows={3}
                  value={userHint}
                  onChange={(e) => setUserHint(e.target.value)}
                  placeholder="Diwali festival greeting poster for MS Fincap employees"
                  className="w-full p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-900 dark:text-slate-100 text-xs resize-none focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-between items-center pt-6 border-t border-slate-200 dark:border-slate-800">
                <button
                  onClick={() => setStep(4)}
                  className="py-2.5 px-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-xl text-xs flex items-center gap-1"
                >
                  <ArrowLeft className="h-4 w-4" /> Back to preview
                </button>
                <button
                  onClick={handleSaveTemplate}
                  disabled={loading}
                  className="py-3 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-slate-900 dark:text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-purple-600/25 transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      <span>Generating smart tags & saving...</span>
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      <span>Generate tags and save</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CreateTemplatePage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-slate-600 dark:text-slate-400 text-xs">Loading template agent...</div>
      }
    >
      <CreateTemplateContent />
    </Suspense>
  );
}
