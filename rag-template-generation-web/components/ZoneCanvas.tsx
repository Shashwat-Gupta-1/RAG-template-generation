"use client";

import React, { useState, useEffect, useRef } from "react";
import { Stage, Layer, Rect, Text as KonvaText, Image as KonvaImage, Transformer } from "react-konva";

export interface Zone {
  id: string;
  _key?: string;
  type: "text" | "image";
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string;
  instruction?: string;
  font_family?: string;
  font_size?: number;
  font_size_min?: number;
  font_weight?: string;
  color?: string;
  align?: string;
  shape?: string;
  border_color?: string;
  border_width?: number;
  llm_can_invent?: boolean;
}

interface ZoneCanvasProps {
  imageSrc?: string;
  zones: Zone[];
  onZonesChange: (zones: Zone[]) => void;
  selectedZoneId: string | null;
  onSelectZone: (id: string | null) => void;
  width?: number;
  height?: number;
}

export default function ZoneCanvas({
  imageSrc,
  zones,
  onZonesChange,
  selectedZoneId,
  onSelectZone,
  width = 680,
  height = 850,
}: ZoneCanvasProps) {
  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const trRef = useRef<any>(null);

  useEffect(() => {
    if (!imageSrc) return;
    const img = new window.Image();
    img.crossOrigin = "Anonymous";
    img.src = imageSrc;
    img.onload = () => {
      setImageObj(img);
    };
  }, [imageSrc]);

  useEffect(() => {
    if (selectedZoneId && trRef.current) {
      const node = trRef.current.getStage()?.findOne("#" + selectedZoneId);
      if (node) {
        trRef.current.nodes([node]);
        trRef.current.getLayer()?.batchDraw();
      }
    } else if (trRef.current) {
      trRef.current.nodes([]);
      trRef.current.getLayer()?.batchDraw();
    }
  }, [selectedZoneId, zones]);

  const handleMouseDown = (e: any) => {
    // If user clicks on an existing rectangle or transformer handle, let Konva handle selection/drag
    const clickedOnStage = e.target === e.target.getStage() || e.target.className === "Image";
    if (!clickedOnStage) {
      return;
    }

    onSelectZone(null);
    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;

    setIsDrawing(true);
    setStartPos({ x: Math.round(pointer.x), y: Math.round(pointer.y) });
    setCurrentRect({ x: Math.round(pointer.x), y: Math.round(pointer.y), width: 0, height: 0 });
  };

  const handleMouseMove = (e: any) => {
    if (!isDrawing || !startPos) return;

    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;

    const x = Math.min(startPos.x, pointer.x);
    const y = Math.min(startPos.y, pointer.y);
    const w = Math.abs(pointer.x - startPos.x);
    const h = Math.abs(pointer.y - startPos.y);

    setCurrentRect({
      x: Math.round(x),
      y: Math.round(y),
      width: Math.round(w),
      height: Math.round(h),
    });
  };

  const handleMouseUp = () => {
    if (isDrawing && currentRect) {
      if (currentRect.width > 15 && currentRect.height > 15) {
        const newId = `field_${zones.length + 1}`;
        const newZone: Zone = {
          id: newId,
          _key: `zone_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
          type: "text",
          x: currentRect.x,
          y: currentRect.y,
          width: currentRect.width,
          height: currentRect.height,
          label: newId,
          instruction: `Enter value for ${newId}`,
          font_family: "Poppins",
          font_size: 48,
          font_size_min: 20,
          font_weight: "bold",
          color: "#FFFFFF",
          align: "center",
          llm_can_invent: false,
        };
        onZonesChange([...zones, newZone]);
        onSelectZone(newId);
      }
    }
    setIsDrawing(false);
    setStartPos(null);
    setCurrentRect(null);
  };

  const handleDragEnd = (id: string, e: any) => {
    const nextZones = zones.map((z) => {
      if (z.id === id) {
        return {
          ...z,
          x: Math.round(e.target.x()),
          y: Math.round(e.target.y()),
        };
      }
      return z;
    });
    onZonesChange(nextZones);
  };

  const handleTransformEnd = (id: string, e: any) => {
    const node = e.target;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();

    node.scaleX(1);
    node.scaleY(1);

    const nextZones = zones.map((z) => {
      if (z.id === id) {
        return {
          ...z,
          x: Math.round(node.x()),
          y: Math.round(node.y()),
          width: Math.max(20, Math.round(node.width() * scaleX)),
          height: Math.max(20, Math.round(node.height() * scaleY)),
        };
      }
      return z;
    });
    onZonesChange(nextZones);
  };

  return (
    <div className="border-2 border-indigo-500/40 rounded-xl overflow-hidden bg-slate-950 flex justify-center items-center shadow-2xl relative cursor-crosshair">
      <Stage
        width={width}
        height={height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        <Layer>
          {imageObj && (
            <KonvaImage
              image={imageObj}
              width={width}
              height={height}
            />
          )}

          {/* Render existing zones */}
          {zones.map((z, idx) => {
            const isSelected = z.id === selectedZoneId;
            const isText = z.type === "text";
            return (
              <React.Fragment key={z.id}>
                <Rect
                  id={z.id}
                  x={z.x}
                  y={z.y}
                  width={z.width}
                  height={z.height}
                  fill={isText ? "rgba(79, 142, 247, 0.2)" : "rgba(16, 185, 129, 0.2)"}
                  stroke={isSelected ? "#a855f7" : isText ? "#4F8EF7" : "#10b981"}
                  strokeWidth={isSelected ? 3 : 2}
                  dash={isSelected ? undefined : [4, 4]}
                  draggable
                  onClick={() => onSelectZone(z.id)}
                  onTap={() => onSelectZone(z.id)}
                  onDragEnd={(e) => handleDragEnd(z.id, e)}
                  onTransformEnd={(e) => handleTransformEnd(z.id, e)}
                />
                <KonvaText
                  x={z.x + 6}
                  y={z.y + 6}
                  text={`Field ${idx + 1}: ${z.id} (${z.type})`}
                  fontSize={12}
                  fill={isSelected ? "#e9d5ff" : isText ? "#60a5fa" : "#34d399"}
                  fontStyle="bold"
                  listening={false}
                />
              </React.Fragment>
            );
          })}

          {/* Render box currently being drawn by mouse */}
          {isDrawing && currentRect && (
            <Rect
              x={currentRect.x}
              y={currentRect.y}
              width={currentRect.width}
              height={currentRect.height}
              fill="rgba(79, 142, 247, 0.3)"
              stroke="#4F8EF7"
              strokeWidth={2}
              dash={[4, 4]}
            />
          )}

          <Transformer
            ref={trRef}
            boundBoxFunc={(oldBox, newBox) => {
              if (newBox.width < 10 || newBox.height < 10) {
                return oldBox;
              }
              return newBox;
            }}
          />
        </Layer>
      </Stage>
    </div>
  );
}
