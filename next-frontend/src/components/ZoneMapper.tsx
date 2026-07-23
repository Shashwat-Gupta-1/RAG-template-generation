"use client";

import React, { useState, useRef, useEffect, MouseEvent } from 'react';
import { X } from 'lucide-react';

export interface Zone {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  type: 'text' | 'image';
  selected?: boolean;
}

interface ZoneMapperProps {
  imageUrl: string;
  imageNaturalWidth: number;
  imageNaturalHeight: number;
  zones: Zone[];
  onChange: (zones: Zone[]) => void;
  onSelectZone: (id: string | null) => void;
}

export default function ZoneMapper({
  imageUrl,
  imageNaturalWidth,
  imageNaturalHeight,
  zones,
  onChange,
  onSelectZone
}: ZoneMapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentBox, setCurrentBox] = useState<{ x: number, y: number, w: number, h: number } | null>(null);

  const [scale, setScale] = useState(1);

  useEffect(() => {
    if (containerRef.current) {
      const displayWidth = containerRef.current.clientWidth;
      setScale(imageNaturalWidth / displayWidth);
    }
  }, [imageNaturalWidth, imageUrl]); // Added imageUrl to recalculate scale if image changes

  const handleMouseDown = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('.zone-box')) return;

    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setIsDrawing(true);
    setStartPos({ x, y });
    setCurrentBox({ x, y, w: 0, h: 0 });
    onSelectZone(null); 
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const y = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

    const bx = Math.min(startPos.x, x);
    const by = Math.min(startPos.y, y);
    const bw = Math.abs(x - startPos.x);
    const bh = Math.abs(y - startPos.y);

    setCurrentBox({ x: bx, y: by, w: bw, h: bh });
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    if (currentBox && currentBox.w > 10 && currentBox.h > 10) {
      const newZone: Zone = {
        id: `field_${zones.length + 1}`, 
        x: Math.round(currentBox.x * scale),
        y: Math.round(currentBox.y * scale),
        width: Math.round(currentBox.w * scale),
        height: Math.round(currentBox.h * scale),
        type: 'text'
      };
      const updatedZones = [...zones, newZone];
      onChange(updatedZones);
      onSelectZone(newZone.id);
    }
    setCurrentBox(null);
  };

  const handleDelete = (id: string, e: MouseEvent) => {
    e.stopPropagation();
    onChange(zones.filter(z => z.id !== id));
    onSelectZone(null);
  };

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className="relative w-full cursor-crosshair select-none overflow-hidden rounded-lg bg-[#111827]"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageUrl}
        alt="Template"
        className="w-full block pointer-events-none"
        draggable={false}
      />
      
      {zones.map((zone) => {
        const isSelected = zone.selected;
        return (
          <div
            key={zone.id}
            className="zone-box absolute group transition-all duration-150"
            onClick={(e) => {
              e.stopPropagation();
              onSelectZone(zone.id);
            }}
            style={{
              left: `${zone.x / scale}px`,
              top: `${zone.y / scale}px`,
              width: `${zone.width / scale}px`,
              height: `${zone.height / scale}px`,
              border: `2px solid #6366f1`,
              backgroundColor: isSelected ? 'rgba(99, 102, 241, 0.4)' : 'rgba(99, 102, 241, 0.2)',
              cursor: 'pointer',
              boxSizing: 'border-box'
            }}
          >
            {/* Label Pill */}
            <div className="absolute top-0 left-0 -mt-[2px] -ml-[2px] bg-[#6366f1] text-white text-[10px] font-medium px-2 py-0.5 rounded-br-md rounded-tl-sm pointer-events-none shadow-sm">
              {zone.id}
            </div>

            {/* Delete Button */}
            <button
              onClick={(e) => handleDelete(zone.id, e)}
              className={`absolute top-0 right-0 -mt-2 -mr-2 bg-[#1f2937] text-gray-400 hover:text-white hover:bg-red-500 border border-gray-600 rounded-full w-6 h-6 flex items-center justify-center shadow-lg transition-colors duration-150 ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
              title="Delete zone"
            >
              <X size={12} strokeWidth={3} />
            </button>
          </div>
        );
      })}

      {isDrawing && currentBox && (
        <div
          style={{
            position: 'absolute',
            left: currentBox.x,
            top: currentBox.y,
            width: currentBox.w,
            height: currentBox.h,
            border: '2px dashed #6366f1',
            backgroundColor: 'rgba(99, 102, 241, 0.2)',
            pointerEvents: 'none'
          }}
        />
      )}
    </div>
  );
}
