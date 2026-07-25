export interface LayerBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LayerStyle {
  font_family?: string;
  font_size?: number;
  font_size_min?: number;
  font_weight?: string;
  font_style?: string;
  color?: string;
  align?: string;
  vertical_align?: string;
  shape?: string;
  border_color?: string;
  border_width?: number;
}

export interface OverlayLayer {
  id: string;
  type: "text" | "image";
  placeholder: string;
  instruction: string;
  llm_can_invent: boolean;
  box: LayerBox;
  style: LayerStyle;
  editable: boolean;
}

export interface CanvasObject {
  type?: string;
  left: number;
  top: number;
  width: number;
  height: number;
  [key: string]: any;
}

export interface ZoneConfig {
  id?: string;
  type?: "text" | "image";
  instruction?: string;
  llm_can_invent?: boolean;
  font_family?: string;
  font_size?: number;
  font_size_min?: number;
  font_weight?: string;
  font_style?: string;
  color?: string;
  align?: string;
  shape?: string;
  border_color?: string;
  border_width?: number;
}

/**
 * Converts drawable canvas rectangles to overlay_layers.
 * Scales display coordinates (e.g. 480x640) to actual PNG pixels (e.g. 1024x1536).
 */
export function canvasObjectsToOverlayLayers(
  canvasObjects: CanvasObject[],
  fieldConfigs: Record<string, ZoneConfig>,
  imgWidth: number,
  imgHeight: number,
  displayWidth: number,
  displayHeight: number
): OverlayLayer[] {
  const scaleX = imgWidth / displayWidth;
  const scaleY = imgHeight / displayHeight;
  const layers: OverlayLayer[] = [];

  canvasObjects.forEach((obj, i) => {
    // Only process rectangular zones
    if (obj.type && obj.type !== "rect" && obj.type !== "Rect") {
      return;
    }

    const cfg = fieldConfigs[String(i)] || fieldConfigs[obj.id || ""] || {};
    const rawId = cfg.id || obj.id || `field_${i + 1}`;
    const fieldId = rawId.trim().replace(/\s+/g, "_").toLowerCase();
    const fieldType = (cfg.type || obj.type || "text") === "image" ? "image" : "text";

    const box: LayerBox = {
      x: Math.max(0, Math.round(obj.left * scaleX)),
      y: Math.max(0, Math.round(obj.top * scaleY)),
      width: Math.round(obj.width * scaleX),
      height: Math.round(obj.height * scaleY),
    };

    if (fieldType === "text") {
      layers.push({
        id: fieldId,
        type: "text",
        placeholder: `{{${fieldId}}}`,
        instruction: (cfg.instruction !== undefined && cfg.instruction.trim() !== "") ? cfg.instruction.trim() : `Value for ${fieldId}`,
        llm_can_invent: cfg.llm_can_invent ?? false,
        box,
        style: {
          font_family: cfg.font_family || "Poppins",
          font_size: Number(cfg.font_size ?? 48),
          font_size_min: Number(cfg.font_size_min ?? 20),
          font_weight: cfg.font_weight || "bold",
          font_style: cfg.font_style || "normal",
          color: cfg.color || "#FFFFFF",
          align: cfg.align || "center",
          vertical_align: "middle",
        },
        editable: true,
      });
    } else {
      layers.push({
        id: fieldId,
        type: "image",
        placeholder: `{{${fieldId}}}`,
        instruction: (cfg.instruction !== undefined && cfg.instruction.trim() !== "") ? cfg.instruction.trim() : "Upload image to place here",
        llm_can_invent: false,
        box,
        style: {
          shape: cfg.shape || "circle",
          border_color: cfg.border_color || "#FFFFFF",
          border_width: Number(cfg.border_width ?? 4),
        },
        editable: true,
      });
    }
  });

  return layers;
}

/**
 * Validates overlay layers according to size, ID, font, and canvas boundary rules.
 * Returns array of error string descriptions. Empty array = valid.
 */
export function validateLayers(
  layers: OverlayLayer[],
  canvasW: number,
  canvasH: number
): string[] {
  const errors: string[] = [];
  const idsSeen = new Set<string>();

  layers.forEach((layer, i) => {
    const fid = layer.id || "";

    if (!fid) {
      errors.push(`Zone #${i + 1} has no field ID.`);
    } else if (idsSeen.has(fid)) {
      errors.push(`Duplicate field ID: '${fid}'. Each zone must have a unique ID.`);
    } else {
      idsSeen.add(fid);
    }

    const box = layer.box || { x: 0, y: 0, width: 0, height: 0 };
    if (box.width < 20 || box.height < 10) {
      errors.push(`Field '${fid}' box is too small — draw a larger rectangle.`);
    }

    if (box.x + box.width > canvasW) {
      errors.push(`Field '${fid}' extends past right edge of image (${box.x + box.width}px > ${canvasW}px).`);
    }
    if (box.y + box.height > canvasH) {
      errors.push(`Field '${fid}' extends past bottom edge of image (${box.y + box.height}px > ${canvasH}px).`);
    }

    if (layer.type === "text") {
      const s = layer.style || {};
      const minFont = Number(s.font_size_min ?? 20);
      const mainFont = Number(s.font_size ?? 48);
      if (minFont >= mainFont) {
        errors.push(`Field '${fid}': minimum font size (${minFont}) must be smaller than main font size (${mainFont}).`);
      }
    }
  });

  return errors;
}
