"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Pencil,
  MousePointer,
  Check,
  CheckCircle,
  AlertTriangle,
  AlignLeft,
  AlignCenter,
  AlignRight,
  X,
  Sparkles
} from "lucide-react";
import { HexColorPicker } from "react-colorful";

// ── Public Types ──────────────────────────────────────────────────────────────
export interface DrawnZone {
  field_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  font_family: string;
  font_size: number;
  font_weight: string;
  color: string;
  align: "left" | "center" | "right";
  llm_can_invent: boolean;
  type?: "text" | "image" | string;
}

export interface RequiredField {
  id: string;
  llm_can_invent: boolean;
  type?: "text" | "image" | string;
}

export interface ZoneEditorProps {
  posterImageUrl: string;
  requiredFields: RequiredField[];
  textValues?: Record<string, string>;
  onDone: (zones: DrawnZone[]) => void;
  onCancel: () => void;
  hintField?: string | null;
  onHintFieldClear?: () => void;
  onFieldAssigned?: (fieldId: string) => void;
  initialZones?: DrawnZone[];
  onChange?: (zones: DrawnZone[]) => void;
}

// ── Internal Types ────────────────────────────────────────────────────────────
interface InternalZone {
  zid: string;
  field_id: string;
  llm_can_invent: boolean;
  type?: "text" | "image" | string;
  dx: number;
  dy: number;
  dw: number;
  dh: number;
  font_family: string;
  font_size: number;
  font_weight: string;
  color: string;
  align: "left" | "center" | "right";
}

interface Rect { x: number; y: number; w: number; h: number; }
type Mode = "draw" | "select";
type ResizeHandleId = "tl" | "tr" | "bl" | "br" | "t" | "b" | "l" | "r";

// ── Constants ─────────────────────────────────────────────────────────────────
const HANDLE_SIZE = 8;
const PRESET_COLORS = [
  "#FFFFFF", "#000000", "#6366f1", "#10b981",
  "#ef4444", "#f59e0b", "#3b82f6", "#ec4899",
];
const FONT_FAMILIES = [
  "Poppins",
  "Inter",
  "Roboto",
  "Playfair Display",
  "Noto Sans",
  "Noto Sans Devanagari",
  "Arial",
  "Montserrat",
];

// ── Component ─────────────────────────────────────────────────────────────────
export default function ZoneEditor({
  posterImageUrl,
  requiredFields,
  textValues,
  onDone,
  onCancel,
  hintField,
  onHintFieldClear,
  onFieldAssigned,
  initialZones = [],
  onChange,
}: ZoneEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  const [mode, setMode] = useState<Mode>("draw");
  const [zones, setZones] = useState<InternalZone[]>([]);
  const [initialized, setInitialized] = useState(false);

  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);

  // Image dimensions
  const [imgLoaded, setImgLoaded] = useState(false);
  const [displayW, setDisplayW] = useState(0);
  const [nativeW, setNativeW] = useState(1024);

  // Drawing
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [liveRect, setLiveRect] = useState<Rect | null>(null);

  // Assignment popup
  const [pendingBox, setPendingBox] = useState<Rect | null>(null);
  const [assignField, setAssignField] = useState("");

  // Trigger onChange when zones change
  useEffect(() => {
    if (displayW === 0 || nativeW === 0 || !initialized) return;
    
    // Scale current display coords back to native to pass up to parent
    const scale = displayW / nativeW;
    const output: DrawnZone[] = zones.map((z) => ({
      field_id: z.field_id,
      x: Math.round(z.dx / scale), y: Math.round(z.dy / scale),
      width: Math.round(z.dw / scale), height: Math.round(z.dh / scale),
      font_family: z.font_family, font_size: z.font_size,
      font_weight: z.font_weight, color: z.color, align: z.align,
      llm_can_invent: z.llm_can_invent,
      type: z.type,
    }));
    onChange?.(output);
  }, [zones, displayW, nativeW, initialized, onChange]);

  // Resize / drag
  const [resizing, setResizing] = useState<{
    zid: string;
    handle: ResizeHandleId;
    startMouse: { x: number; y: number };
    origZone: InternalZone;
  } | null>(null);
  const [dragging, setDragging] = useState<{
    zid: string;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  // Floating Styling popup
  const [showStyling, setShowStyling] = useState(false);
  const [stylingFor, setStylingFor] = useState<string | null>(null);
  const [styleDraft, setStyleDraft] = useState({
    font_family: "Poppins",
    font_size: 32,
    font_weight: "bold",
    color: "#FFFFFF",
    align: "center" as "left" | "center" | "right",
  });

  // Click outside to dismiss popup
  useEffect(() => {
    if (!showStyling) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(e.target as Node) &&
        canvasRef.current &&
        !canvasRef.current.contains(e.target as Node)
      ) {
        setShowStyling(false);
        setStylingFor(null);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [showStyling]);

  // Feedback
  const [overlapWarning, setOverlapWarning] = useState(false);
  const [shake, setShake] = useState(false);
  const [successToast, setSuccessToast] = useState(false);

  // ── Derived ──────────────────────────────────────────────────────────────────
  const nonAiFields = requiredFields.filter((f) => !f.llm_can_invent);
  const assignedIds = new Set(zones.map((z) => z.field_id));
  const allPlaced = nonAiFields.every((f) => assignedIds.has(f.id));
  const placedCount = nonAiFields.filter((f) => assignedIds.has(f.id)).length;
  // All fields (both AI and non-AI) that haven't been assigned yet
  const unassigned = requiredFields.filter((f) => !assignedIds.has(f.id));

  useEffect(() => {
    if (hintField) { setMode("draw"); setAssignField(hintField); }
  }, [hintField]);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const check = () => {
      if (img.complete && img.naturalWidth > 0) {
        setImgLoaded(true);
      }
    };

    check();
    img.addEventListener("load", check);
    const interval = setInterval(check, 100);

    return () => {
      img.removeEventListener("load", check);
      clearInterval(interval);
    };
  }, [posterImageUrl]);

  useEffect(() => {
    if (allPlaced && zones.length > 0) {
      setSuccessToast(true);
      setTimeout(() => setSuccessToast(false), 3500);
      setMode("select");
    }
  }, [allPlaced, zones.length]);

  const syncCanvasSize = useCallback(() => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas || !imgLoaded) return;
    const rect = img.getBoundingClientRect();
    if (rect.width === 0) return;
    const newW = Math.round(rect.width);
    const newH = Math.round(rect.height);
    if (canvas.width !== newW || canvas.height !== newH) {
      canvas.width = newW;
      canvas.height = newH;
      setDisplayW(newW);
    }
    const natW = img.naturalWidth || 1024;
    setNativeW(natW);
  }, [imgLoaded]);

  useEffect(() => { syncCanvasSize(); }, [imgLoaded, syncCanvasSize]);

  // Initialize zones once displayW and nativeW are known
  useEffect(() => {
    if (displayW > 0 && nativeW > 0 && !initialized) {
      const scale = displayW / nativeW;
      setZones(initialZones.map((z, idx) => ({
        zid: `z_${Date.now()}_${idx}`,
        field_id: z.field_id,
        llm_can_invent: z.llm_can_invent,
        type: z.type || "text",
        dx: z.x * scale,
        dy: z.y * scale,
        dw: z.width * scale,
        dh: z.height * scale,
        font_family: z.font_family || "Poppins",
        font_size: z.font_size || 32,
        font_weight: z.font_weight || "bold",
        color: z.color || "#FFFFFF",
        align: z.align || "center",
      })));
      setInitialized(true);
    }
  }, [displayW, nativeW, initialized, initialZones]);

  useEffect(() => {
    const ro = new ResizeObserver(syncCanvasSize);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [syncCanvasSize]);

  // Keyboard delete
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Delete" && selectedZoneId) removeZone(selectedZoneId);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedZoneId, zones]);

  // ── Canvas Rendering ──────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    zones.forEach((z) => {
      const isSel = z.zid === selectedZoneId;

      const isImage = z.type === "image";
      const textContent = textValues?.[z.field_id];
      const hasText = !isImage && !!(textContent && textContent !== "__LLM_INVENT__" && textContent !== "__LLM_EXTRACT__" && textContent !== "__IMAGE__");

      // Highlight Box
      if (isImage) {
        ctx.fillStyle = isSel ? "rgba(16,185,129,0.25)" : "rgba(16,185,129,0.12)";
        ctx.fillRect(z.dx, z.dy, z.dw, z.dh);
        ctx.strokeStyle = isSel ? "#FFFFFF" : "#10b981";
        ctx.lineWidth = 2;
        ctx.strokeRect(z.dx, z.dy, z.dw, z.dh);

        // Center Photo label
        ctx.fillStyle = "#10b981";
        ctx.font = "bold 12px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`📷 ${z.field_id.toUpperCase()} (IMAGE)`, z.dx + z.dw / 2, z.dy + z.dh / 2);
      } else {
        ctx.fillStyle = isSel
          ? (hasText ? "rgba(99,102,241,0.15)" : "rgba(99,102,241,0.25)")
          : (hasText ? "rgba(0,0,0,0.35)" : "rgba(99,102,241,0.08)");
        ctx.fillRect(z.dx, z.dy, z.dw, z.dh);

        ctx.strokeStyle = isSel ? "#FFFFFF" : "#6366f1";
        ctx.lineWidth = 2;
        ctx.strokeRect(z.dx, z.dy, z.dw, z.dh);
      }

      // Draw real text ON TOP of the box so it's always visible
      if (hasText) {
        const scale = displayW / nativeW;
        const scaledFontSize = z.font_size * scale;

        ctx.fillStyle = z.color;
        const fwMap: Record<string, string> = {
          regular: "normal",
          medium: "500",
          semibold: "600",
          bold: "bold",
        };
        const fw = fwMap[z.font_weight.toLowerCase()] || "normal";
        ctx.font = `${fw} ${scaledFontSize}px "${z.font_family}", sans-serif`;

        wrapText(ctx, textContent, z.dx, z.dy, z.dw, z.dh, scaledFontSize * 1.2, z.align);
      }

      // Label pill
      ctx.font = "bold 11px sans-serif";
      ctx.textBaseline = "alphabetic";
      ctx.textAlign = "left";
      const pillLabel = isImage ? `📷 ${z.field_id}` : z.field_id;
      const textW = ctx.measureText(pillLabel).width;
      const pillW = textW + 12;
      const pillH = 18;
      ctx.fillStyle = isImage ? "#10b981" : "#6366f1";
      drawRoundRect(ctx, z.dx + 4, z.dy + 4, pillW, pillH, 4);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(pillLabel, z.dx + 10, z.dy + 15);

      // ✕ delete button (top-right)
      const bx = z.dx + z.dw - 22;
      const by = z.dy + 4;
      ctx.fillStyle = "rgba(220,38,38,0.9)";
      drawRoundRect(ctx, bx, by, 18, 18, 4);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("×", bx + 9, by + 10);

      // ✏️ edit button (next to delete, only for text layers)
      if (!isImage) {
        const ex = bx - 22;
        ctx.fillStyle = "rgba(99,102,241,0.9)"; // Indigo
        drawRoundRect(ctx, ex, by, 18, 18, 4);
        ctx.fill();
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "bold 13px sans-serif";
        ctx.fillText("✎", ex + 9, by + 10);
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
      }

      // Resize handles when selected
      if (isSel) {
        getHandlePoints(z.dx, z.dy, z.dw, z.dh).forEach(([hx, hy]) => {
          ctx.fillStyle = "#FFFFFF";
          ctx.fillRect(hx - HANDLE_SIZE / 2, hy - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
          ctx.strokeStyle = "#6366f1";
          ctx.lineWidth = 1.5;
          ctx.strokeRect(hx - HANDLE_SIZE / 2, hy - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
        });
      }
    });

    // Live drawing rect
    if (liveRect && liveRect.w > 0 && liveRect.h > 0) {
      ctx.fillStyle = "rgba(99,102,241,0.15)";
      ctx.fillRect(liveRect.x, liveRect.y, liveRect.w, liveRect.h);
      ctx.setLineDash([6, 3]);
      ctx.strokeStyle = "#6366f1";
      ctx.lineWidth = 2;
      ctx.strokeRect(liveRect.x, liveRect.y, liveRect.w, liveRect.h);
      ctx.setLineDash([]);
    }
  }, [zones, selectedZoneId, liveRect, displayW, nativeW, textValues]);

  // ── Canvas Helpers ────────────────────────────────────────────────────────────
  function wrapText(
    ctx: CanvasRenderingContext2D,
    text: string,
    x: number,
    y: number,
    w: number,
    h: number,
    lineHeight: number,
    align: "left" | "center" | "right"
  ) {
    const paragraphs = text.split("\n");
    const lines: string[] = [];
    
    for (let p = 0; p < paragraphs.length; p++) {
      const words = paragraphs[p].split(" ");
      let line = "";
      for (let n = 0; n < words.length; n++) {
        const testLine = line + words[n] + " ";
        const metrics = ctx.measureText(testLine);
        if (metrics.width > w && n > 0) {
          lines.push(line.trim());
          line = words[n] + " ";
        } else {
          line = testLine;
        }
      }
      lines.push(line.trim());
    }

    const totalHeight = lines.length * lineHeight;
    let startY = y + (h - totalHeight) / 2 + lineHeight * 0.8;
    
    for (let i = 0; i < lines.length; i++) {
      if (align === "center") {
        ctx.textAlign = "center";
        ctx.fillText(lines[i], x + w / 2, startY);
      } else if (align === "right") {
        ctx.textAlign = "right";
        ctx.fillText(lines[i], x + w, startY);
      } else {
        ctx.textAlign = "left";
        ctx.fillText(lines[i], x, startY);
      }
      startY += lineHeight;
    }
    // reset defaults
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function drawRoundRect(
    ctx: CanvasRenderingContext2D,
    x: number, y: number, w: number, h: number, r: number
  ) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  function getHandlePoints(x: number, y: number, w: number, h: number): [number, number][] {
    const mx = x + w / 2, my = y + h / 2;
    return [
      [x, y], [mx, y], [x + w, y],
      [x, my], [x + w, my],
      [x, y + h], [mx, y + h], [x + w, y + h],
    ];
  }

  function getCanvasCoords(e: React.MouseEvent<HTMLCanvasElement>): { x: number; y: number } {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function hitDeleteButton(px: number, py: number): string | null {
    for (const z of zones) {
      const bx = z.dx + z.dw - 22, by = z.dy + 4;
      if (px >= bx && px <= bx + 18 && py >= by && py <= by + 18) return z.zid;
    }
    return null;
  }

  function hitEditButton(px: number, py: number): string | null {
    for (const z of zones) {
      const bx = z.dx + z.dw - 22, by = z.dy + 4;
      const ex = bx - 22;
      if (px >= ex && px <= ex + 18 && py >= by && py <= by + 18) return z.zid;
    }
    return null;
  }

  function hitZone(px: number, py: number): string | null {
    for (let i = zones.length - 1; i >= 0; i--) {
      const z = zones[i];
      if (px >= z.dx && px <= z.dx + z.dw && py >= z.dy && py <= z.dy + z.dh) return z.zid;
    }
    return null;
  }

  function hitHandle(px: number, py: number, z: InternalZone): ResizeHandleId | null {
    const pts: [ResizeHandleId, number, number][] = [
      ["tl", z.dx, z.dy], ["tr", z.dx + z.dw, z.dy],
      ["bl", z.dx, z.dy + z.dh], ["br", z.dx + z.dw, z.dy + z.dh],
      ["t", z.dx + z.dw / 2, z.dy], ["b", z.dx + z.dw / 2, z.dy + z.dh],
      ["l", z.dx, z.dy + z.dh / 2], ["r", z.dx + z.dw, z.dy + z.dh / 2],
    ];
    for (const [id, hx, hy] of pts) {
      if (Math.abs(px - hx) <= HANDLE_SIZE + 2 && Math.abs(py - hy) <= HANDLE_SIZE + 2) return id;
    }
    return null;
  }

  function detectOverlap(zs: InternalZone[]): boolean {
    for (let i = 0; i < zs.length; i++) {
      for (let j = i + 1; j < zs.length; j++) {
        const a = zs[i], b = zs[j];
        if (a.dx < b.dx + b.dw && a.dx + a.dw > b.dx && a.dy < b.dy + b.dh && a.dy + a.dh > b.dy)
          return true;
      }
    }
    return false;
  }

  // ── Mouse Handlers ────────────────────────────────────────────────────────────
  const onMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);

    if (mode === "draw") {
      setIsDrawing(true);
      setDrawStart({ x, y });
      setLiveRect({ x, y, w: 0, h: 0 });
      return;
    }

    // Select mode
    const delZid = hitDeleteButton(x, y);
    if (delZid) { removeZone(delZid); return; }

    const editZid = hitEditButton(x, y);
    if (editZid) {
      setSelectedZoneId(editZid);
      const z = zones.find((z) => z.zid === editZid)!;
      if (z.type !== "image") {
        setStylingFor(editZid);
        setStyleDraft({
          font_family: z.font_family || "Poppins",
          font_size: z.font_size || 32,
          font_weight: z.font_weight || "bold",
          color: z.color || "#FFFFFF",
          align: z.align || "center",
        });
        setShowStyling(true);
      }
      return;
    }

    if (selectedZoneId) {
      const selZ = zones.find((z) => z.zid === selectedZoneId);
      if (selZ) {
        const h = hitHandle(x, y, selZ);
        if (h) { setResizing({ zid: selZ.zid, handle: h, startMouse: { x, y }, origZone: { ...selZ } }); return; }
      }
    }

    const hitZid = hitZone(x, y);
    if (hitZid) {
      setSelectedZoneId(hitZid);
      const z = zones.find((z) => z.zid === hitZid)!;
      setDragging({ zid: hitZid, offsetX: x - z.dx, offsetY: y - z.dy });

      // Open styling popup automatically when clicking a text zone
      if (z.type !== "image") {
        setStylingFor(hitZid);
        setStyleDraft({
          font_family: z.font_family || "Poppins",
          font_size: z.font_size || 32,
          font_weight: z.font_weight || "bold",
          color: z.color || "#FFFFFF",
          align: z.align || "center",
        });
        setShowStyling(true);
      } else {
        setShowStyling(false);
        setStylingFor(null);
      }
    } else {
      setSelectedZoneId(null);
      setShowStyling(false);
      setStylingFor(null);
    }
  };

  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);

    if (mode === "draw" && isDrawing && drawStart) {
      setLiveRect({ x: Math.min(drawStart.x, x), y: Math.min(drawStart.y, y), w: Math.abs(x - drawStart.x), h: Math.abs(y - drawStart.y) });
      return;
    }

    if (resizing) {
      const { handle, startMouse, origZone } = resizing;
      const dx = x - startMouse.x, dy = y - startMouse.y;
      setZones((prev) => prev.map((z) => {
        if (z.zid !== resizing.zid) return z;
        let { dx: zdx, dy: zdy, dw, dh } = origZone;
        if (handle === "tl") { zdx += dx; zdy += dy; dw -= dx; dh -= dy; }
        if (handle === "tr") { dw += dx; zdy += dy; dh -= dy; }
        if (handle === "bl") { zdx += dx; dw -= dx; dh += dy; }
        if (handle === "br") { dw += dx; dh += dy; }
        if (handle === "t")  { zdy += dy; dh -= dy; }
        if (handle === "b")  { dh += dy; }
        if (handle === "l")  { zdx += dx; dw -= dx; }
        if (handle === "r")  { dw += dx; }
        return { ...z, dx: zdx, dy: zdy, dw: Math.max(20, dw), dh: Math.max(20, dh) };
      }));
      return;
    }

    if (dragging) {
      setZones((prev) => prev.map((z) =>
        z.zid === dragging.zid ? { ...z, dx: x - dragging.offsetX, dy: y - dragging.offsetY } : z
      ));
    }
  };

  const onMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (mode === "draw" && isDrawing && liveRect) {
      setIsDrawing(false);
      setDrawStart(null);
      if (liveRect.w > 10 && liveRect.h > 10) {
        setPendingBox({ ...liveRect });
        const firstUnassigned = unassigned[0];
        if (hintField && unassigned.some((f) => f.id === hintField)) setAssignField(hintField);
        else if (firstUnassigned) setAssignField(firstUnassigned.id);
        else setAssignField("");
      }
      setLiveRect(null);
      return;
    }
    if (resizing) setResizing(null);
    if (dragging) setDragging(null);
  };

  // ── Zone Management ───────────────────────────────────────────────────────────
  function commitAssign() {
    if (!pendingBox || !assignField) return;
    const field = requiredFields.find((f) => f.id === assignField);
    const newZone: InternalZone = {
      zid: `zone_${Date.now()}`,
      field_id: assignField,
      llm_can_invent: field?.llm_can_invent ?? false,
      type: field?.type || "text",
      dx: pendingBox.x, dy: pendingBox.y, dw: pendingBox.w, dh: pendingBox.h,
      font_family: "Poppins", font_size: 32, font_weight: "bold",
      color: "#FFFFFF", align: "center",
    };
    const next = [...zones, newZone];
    setZones(next);
    setOverlapWarning(detectOverlap(next));
    setPendingBox(null);

    // Auto select & open styling popup if text field
    setSelectedZoneId(newZone.zid);
    if (newZone.type !== "image") {
      setStylingFor(newZone.zid);
      setStyleDraft({
        font_family: newZone.font_family,
        font_size: newZone.font_size,
        font_weight: newZone.font_weight,
        color: newZone.color,
        align: newZone.align,
      });
      setShowStyling(true);
    }

    onFieldAssigned?.(assignField);
    onHintFieldClear?.();
  }

  function cancelAssign() { setPendingBox(null); setAssignField(""); }

  function removeZone(zid: string) {
    const next = zones.filter((z) => z.zid !== zid);
    setZones(next);
    setOverlapWarning(detectOverlap(next));
    if (selectedZoneId === zid) { setSelectedZoneId(null); setShowStyling(false); setStylingFor(null); }
  }

  function applyStyle() {
    if (!stylingFor) return;
    setZones((prev) => prev.map((z) => z.zid === stylingFor ? { ...z, ...styleDraft } : z));
    setShowStyling(false);
    setStylingFor(null);
  }

  // ── Done ──────────────────────────────────────────────────────────────────────
  function handleDone() {
    if (!allPlaced) { setShake(true); setTimeout(() => setShake(false), 600); return; }
    const scale = displayW / nativeW;
    const output: DrawnZone[] = zones.map((z) => ({
      field_id: z.field_id,
      x: Math.round(z.dx / scale), y: Math.round(z.dy / scale),
      width: Math.round(z.dw / scale), height: Math.round(z.dh / scale),
      font_family: z.font_family, font_size: z.font_size,
      font_weight: z.font_weight, color: z.color, align: z.align,
      llm_can_invent: z.llm_can_invent,
      type: z.type,
    }));
    onDone(output);
  }

  // ── Assignment popup position ───────────────────────────────────────────────
  const popupPos = (() => {
    if (!pendingBox) return { top: 0, left: 0 };
    const containerH = containerRef.current?.clientHeight ?? 800;
    const containerW = containerRef.current?.clientWidth ?? 600;
    const spaceBelow = containerH - (pendingBox.y + pendingBox.h);
    const top = spaceBelow > 170 ? pendingBox.y + pendingBox.h + 8 : pendingBox.y - 172;
    const left = Math.min(pendingBox.x, containerW - 244);
    return { top: Math.max(4, top), left: Math.max(4, left) };
  })();

  // ── Anchored Style Popup Position Calculation ────────────────────────────────
  const stylePopupPos = (() => {
    if (!stylingFor) return { top: 0, left: 0, pointerAtTop: true, pointerX: 20 };
    const targetZone = zones.find((z) => z.zid === stylingFor);
    if (!targetZone) return { top: 0, left: 0, pointerAtTop: true, pointerX: 20 };

    const containerH = containerRef.current?.clientHeight ?? 600;
    const containerW = containerRef.current?.clientWidth ?? 800;

    const popupW = 280;
    const popupH = 430;

    const spaceBelow = containerH - (targetZone.dy + targetZone.dh);
    let pointerAtTop = true;
    let top = targetZone.dy + targetZone.dh + 14;

    if (spaceBelow < popupH && targetZone.dy > popupH + 14) {
      top = targetZone.dy - popupH - 14;
      pointerAtTop = false;
    } else if (spaceBelow < popupH) {
      top = Math.max(10, Math.min(top, containerH - popupH - 10));
    }

    let left = targetZone.dx + targetZone.dw / 2 - popupW / 2;
    if (left < 10) left = 10;
    if (left + popupW > containerW - 10) left = containerW - popupW - 10;

    const pointerX = Math.min(Math.max(20, targetZone.dx + targetZone.dw / 2 - left), popupW - 20);

    return { top, left, pointerAtTop, pointerX };
  })();

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4">
      {/* ── Toolbar ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-lg overflow-hidden border border-slate-700">
          <button
            onClick={() => setMode("draw")}
            className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-colors ${
              mode === "draw" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            <Pencil className="h-3 w-3" /> Draw Mode
          </button>
          <button
            onClick={() => setMode("select")}
            className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-colors ${
              mode === "select" ? "bg-slate-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            <MousePointer className="h-3 w-3" /> Select Mode
          </button>
        </div>

        <span className="text-xs text-slate-400 flex-1 text-center tabular-nums">
          {placedCount} of {nonAiFields.length} zones placed
        </span>

        <button
          onClick={handleDone}
          disabled={!allPlaced}
          className={`px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
            allPlaced
              ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/25"
              : "bg-slate-700 text-slate-500 cursor-not-allowed"
          } ${shake ? "animate-[shake_0.3s_ease-in-out_2]" : ""}`}
        >
          <Check className="h-3.5 w-3.5" />
          Done — Generate Poster
        </button>
      </div>

      {/* ── Canvas + image ── */}
      <div
        ref={containerRef}
        className="relative w-full rounded-xl overflow-hidden border-2 border-slate-700 shadow-2xl bg-slate-950"
      >
        <img
          ref={imgRef}
          src={posterImageUrl}
          alt="Template preview"
          className="w-full h-auto block select-none"
          draggable={false}
          onLoad={() => {
            setImgLoaded(true);
            setTimeout(syncCanvasSize, 60);
          }}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
          style={{
            cursor:
              mode === "draw"
                ? "crosshair"
                : mode === "select" && (resizing || dragging)
                ? "grabbing"
                : mode === "select" && selectedZoneId
                ? "grab"
                : "default",
          }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        />

        {/* ── Assignment popup ── */}
        {pendingBox && (
          <div
            className="absolute z-50 bg-slate-900 border border-indigo-500/60 rounded-xl shadow-2xl p-4 w-60"
            style={{ top: popupPos.top, left: popupPos.left }}
          >
            <p className="text-xs font-semibold text-slate-200 mb-3">Assign this zone to:</p>
            <select
              value={assignField}
              onChange={(e) => setAssignField(e.target.value)}
              className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-xs text-white mb-3 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              autoFocus
            >
              <option value="">— select field —</option>
              {unassigned.map((f) => (
                <option key={f.id} value={f.id}>{f.id.replace(/_/g, " ")}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                onClick={cancelAssign}
                className="flex-1 py-1.5 rounded-lg text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={commitAssign}
                disabled={!assignField}
                className="flex-1 py-1.5 rounded-lg text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium disabled:opacity-40 transition-colors"
              >
                Assign
              </button>
            </div>
          </div>
        )}

        {/* ── Anchored Figma/Canva Style Floating Popup ── */}
        {showStyling && stylingFor && (
          <div
            ref={popupRef}
            className="absolute z-50 bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl shadow-black/80 p-4 w-72 text-white space-y-3.5 animate-in fade-in zoom-in-95 duration-150"
            style={{ top: stylePopupPos.top, left: stylePopupPos.left }}
          >
            {/* Triangular Arrow Pointer */}
            <div
              className="absolute w-0 h-0 border-solid pointer-events-none"
              style={
                stylePopupPos.pointerAtTop
                  ? {
                      top: "-7px",
                      left: `${stylePopupPos.pointerX}px`,
                      borderWidth: "0 7px 7px 7px",
                      borderColor: "transparent transparent #0f172a transparent",
                    }
                  : {
                      bottom: "-7px",
                      left: `${stylePopupPos.pointerX}px`,
                      borderWidth: "7px 7px 0 7px",
                      borderColor: "#0f172a transparent transparent transparent",
                    }
              }
            />

            {/* Popup Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                <span className="text-xs font-bold text-slate-200 capitalize">
                  Style: {zones.find((z) => z.zid === stylingFor)?.field_id.replace(/_/g, " ")}
                </span>
              </div>
              <button
                onClick={() => { setShowStyling(false); setStylingFor(null); }}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Font & Weight */}
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[10px] font-medium text-slate-400 mb-1">Font</label>
                <select
                  value={styleDraft.font_family}
                  onChange={(e) => setStyleDraft((s) => ({ ...s, font_family: e.target.value }))}
                  className="w-full p-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                >
                  {FONT_FAMILIES.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-medium text-slate-400 mb-1">Weight</label>
                <select
                  value={styleDraft.font_weight}
                  onChange={(e) => setStyleDraft((s) => ({ ...s, font_weight: e.target.value }))}
                  className="w-full p-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                >
                  {["regular", "medium", "semibold", "bold"].map((w) => (
                    <option key={w} value={w}>
                      {w.charAt(0).toUpperCase() + w.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Size & Alignment */}
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[10px] font-medium text-slate-400 mb-1">Size (px)</label>
                <input
                  type="number"
                  min={10}
                  max={120}
                  value={styleDraft.font_size}
                  onChange={(e) => setStyleDraft((s) => ({ ...s, font_size: parseInt(e.target.value) || 32 }))}
                  className="w-full p-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-[10px] font-medium text-slate-400 mb-1">Align</label>
                <div className="flex bg-slate-800 p-0.5 rounded-lg border border-slate-700">
                  {(["left", "center", "right"] as const).map((a) => {
                    const isSel = styleDraft.align === a;
                    let IconComp = AlignCenter;
                    if (a === "left") IconComp = AlignLeft;
                    if (a === "right") IconComp = AlignRight;

                    return (
                      <button
                        key={a}
                        type="button"
                        onClick={() => setStyleDraft((s) => ({ ...s, align: a }))}
                        className={`flex-1 py-1 flex items-center justify-center rounded-md text-xs transition-colors ${
                          isSel ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                        }`}
                      >
                        <IconComp className="h-3 w-3" />
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Color 2D Shade Picker + Hue Strip + Hex Sync */}
            <div>
              <label className="block text-[10px] font-medium text-slate-400 mb-1.5">Color</label>
              <div className="mb-2">
                <HexColorPicker
                  color={styleDraft.color}
                  onChange={(c) => setStyleDraft((s) => ({ ...s, color: c }))}
                  style={{ width: "100%", height: "120px" }}
                />
              </div>

              {/* Color Presets & Hex Sync input */}
              <div className="flex items-center gap-2">
                <div className="flex gap-1 flex-1 overflow-x-auto">
                  {PRESET_COLORS.map((hex) => (
                    <button
                      key={hex}
                      type="button"
                      onClick={() => setStyleDraft((s) => ({ ...s, color: hex }))}
                      className="w-4 h-4 rounded-full border border-slate-700 shrink-0 transition-transform hover:scale-110"
                      style={{ backgroundColor: hex }}
                    />
                  ))}
                </div>
                <input
                  type="text"
                  value={styleDraft.color}
                  onChange={(e) => setStyleDraft((s) => ({ ...s, color: e.target.value }))}
                  className="w-20 p-1 bg-slate-800 border border-slate-700 rounded-lg text-[11px] text-white font-mono text-center uppercase focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Apply Button */}
            <button
              onClick={applyStyle}
              className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-1.5"
            >
              <Check className="h-3.5 w-3.5" />
              Apply to this zone
            </button>
          </div>
        )}

        {/* ── All-placed toast ── */}
        {successToast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-emerald-900/90 border border-emerald-700 text-emerald-300 text-xs px-4 py-2 rounded-full shadow-lg flex items-center gap-2 whitespace-nowrap pointer-events-none">
            <CheckCircle className="h-3.5 w-3.5" />
            All zones placed — click Done to generate!
          </div>
        )}
      </div>

      {/* ── Overlap warning ── */}
      {overlapWarning && (
        <div className="flex items-center gap-2 text-amber-400 bg-amber-950/40 border border-amber-800/40 rounded-xl px-4 py-2.5 text-xs">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          Zone overlap detected. Overlapping zones may cause text to appear on top of each other.
        </div>
      )}
    </div>
  );
}
