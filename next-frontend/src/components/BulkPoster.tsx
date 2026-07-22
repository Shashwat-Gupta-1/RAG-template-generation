"use client";

import { useState, useEffect } from "react";
import { Loader2, FileSpreadsheet, Upload, Send, Eye, ImageIcon } from "lucide-react";
import { useAuth } from "./AuthProvider";

export function BulkPoster() {
  const { token } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [directCaption, setDirectCaption] = useState("");
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [excelColumns, setExcelColumns] = useState<string[]>([]);
  const [layers, setLayers] = useState<any[]>([]);
  const [isMapperModalOpen, setIsMapperModalOpen] = useState(false);
  const [isStyleExpanded, setIsStyleExpanded] = useState(false);
  const [isMappingConfirmed, setIsMappingConfirmed] = useState(false);
  // Job progress state
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);

  // Layout & Style overrides
  const [canvasSize, setCanvasSize] = useState<{width: number, height: number}>({ width: 1024, height: 1536 });
  const [layoutOverrides, setLayoutOverrides] = useState<Record<string, {x?: number, y?: number}>>({});
  const [styleOverrides, setStyleOverrides] = useState<Record<string, {font_family?: string, font_weight?: string, font_size?: number, color?: string}>>({});
  
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Polling for job status
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/job-status/${jobId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
          },
        });
        if (res.ok) {
          const data = await res.json();
          setJobStatus(data);
          
          if (data.status === "done" || data.status === "failed") {
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error("Failed to poll job status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, token]);

  const handleDownload = async (url: string) => {
    try {
      const res = await fetch(`http://localhost:8000${url}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to download file");
      
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `bulk_posters_${jobId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      setError(err.message || "Failed to download ZIP");
    }
  };

  const handlePreview = async () => {
    if (!prompt.trim() || !excelFile) {
      setError("Please enter a prompt and upload an Excel file.");
      return;
    }

    setIsPreviewing(true);
    setError("");
    setSuccess("");

    try {
      const formData = new FormData();
      formData.append("prompt", prompt);
      formData.append("excel_file", excelFile);
      if (photo) formData.append("photo", photo);
      if (directCaption) formData.append("direct_caption", directCaption);
      
      if (Object.keys(columnMap).length > 0) {
        formData.append("column_mapping", JSON.stringify(columnMap));
      }
      if (Object.keys(layoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(layoutOverrides));
      }
      if (Object.keys(styleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(styleOverrides));
      }

      const res = await fetch("http://localhost:8000/bulk/preview", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        if (data.excel_columns) setExcelColumns(data.excel_columns);
        if (data.overlay_layers) setLayers(data.overlay_layers);
        if (data.column_map && Object.keys(columnMap).length === 0) setColumnMap(data.column_map);

        if (res.status === 422 && data.errors) {
          throw new Error("Validation failed: " + JSON.stringify(data.errors));
        }
        throw new Error(data.error || data.detail || "Failed to generate preview.");
      }

      if (data.status === "ambiguous") {
        throw new Error("Ambiguous prompt. Please be more specific about the template.");
      } else if (data.status === "no_match") {
        throw new Error("No matching template found.");
      }

      if (data.excel_columns) setExcelColumns(data.excel_columns);
      if (data.overlay_layers) setLayers(data.overlay_layers);
      if (data.column_map && Object.keys(columnMap).length === 0) setColumnMap(data.column_map);
      if (data.canvas) setCanvasSize({ width: data.canvas.width || 1024, height: data.canvas.height || 1536 });

      if (data.preview_image) {
        setPreviewImage(`data:image/png;base64,${data.preview_image}`);
      } else {
        throw new Error(data.error || "Failed to load preview.");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim() || !excelFile) {
      setError("Please enter a prompt and upload an Excel file.");
      return;
    }

    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      const formData = new FormData();
      formData.append("prompt", prompt);
      formData.append("excel_file", excelFile);
      if (photo) formData.append("photo", photo);
      if (directCaption) formData.append("direct_caption", directCaption);

      if (Object.keys(columnMap).length > 0) {
        formData.append("column_mapping", JSON.stringify(columnMap));
      }
      if (Object.keys(layoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(layoutOverrides));
      }
      if (Object.keys(styleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(styleOverrides));
      }

      const res = await fetch("http://localhost:8000/bulk", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 422 && data.errors) {
          throw new Error("Validation failed: " + JSON.stringify(data.errors));
        }
        throw new Error(data.error || data.detail || "Failed to start bulk generation.");
      }

      if (data.status === "ambiguous") {
        throw new Error("Ambiguous prompt. Please be more specific about the template.");
      } else if (data.status === "no_match") {
        throw new Error("No matching template found.");
      }

      setJobId(data.job_id);
      setSuccess(`Job started! ID: ${data.job_id}. Rows queued: ${data.total_rows}`);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
      {/* Input Section */}
      <div className="flex flex-col gap-6 h-full">
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            What poster do you need?
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Diwali poster for the whole team"
            className="w-full h-24 px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            Direct Caption (Applies to all rows)
          </label>
          <input
            type="text"
            value={directCaption}
            onChange={(e) => setDirectCaption(e.target.value)}
            placeholder="e.g. Happy Holidays to everyone!"
            className="w-full px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Upload Excel Sheet
            </label>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-zinc-700 border-dashed rounded-xl cursor-pointer bg-zinc-800/20 hover:bg-zinc-800/50 transition-all">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <FileSpreadsheet className="w-8 h-8 text-zinc-500 mb-2" />
                <p className="text-xs text-zinc-400 text-center px-2">
                  <span className="font-medium text-indigo-400">Click to upload</span> Excel
                </p>
                {excelFile && (
                  <p className="text-[10px] text-green-400 mt-2 font-medium truncate max-w-full px-2">
                    {excelFile.name}
                  </p>
                )}
              </div>
              <input
                type="file"
                className="hidden"
                accept=".xlsx,.xls"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    setExcelFile(e.target.files[0]);
                  }
                }}
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Upload Base Photo (optional)
            </label>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-zinc-700 border-dashed rounded-xl cursor-pointer bg-zinc-800/20 hover:bg-zinc-800/50 transition-all">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <Upload className="w-8 h-8 text-zinc-500 mb-2" />
                <p className="text-xs text-zinc-400 text-center px-2">
                  <span className="font-medium text-indigo-400">Click to upload</span> Image
                </p>
                {photo && (
                  <p className="text-[10px] text-green-400 mt-2 font-medium truncate max-w-full px-2">
                    {photo.name}
                  </p>
                )}
              </div>
              <input
                type="file"
                className="hidden"
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    setPhoto(e.target.files[0]);
                  }
                }}
              />
            </label>
          </div>
        </div>

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-xl text-green-400 text-sm">
            {success}
          </div>
        )}

        <div className="flex gap-4">
          <button
            onClick={handlePreview}
            disabled={isPreviewing || !prompt.trim() || !excelFile}
            className="flex-1 py-3 px-4 bg-zinc-700 hover:bg-zinc-600 text-white font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 focus:ring-offset-zinc-900 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPreviewing ? (
              <Loader2 className="animate-spin h-5 w-5" />
            ) : (
              <>
                <Eye className="w-5 h-5 mr-2" />
                Preview First Row
              </>
            )}
          </button>

          <button
            onClick={handleGenerate}
            disabled={isLoading || !prompt.trim() || !excelFile}
            className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-900 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
          >
            {isLoading ? (
              <Loader2 className="animate-spin h-5 w-5" />
            ) : (
              <>
                <Send className="w-5 h-5 mr-2" />
                Start Job
              </>
            )}
          </button>
        </div>

        {/* Adjust Styling & Layout Editor (Moved to Left Column) */}
        {layers.length > 0 && excelColumns.length > 0 && isMappingConfirmed && (
          <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl mt-auto">
            <button
              onClick={() => setIsStyleExpanded(!isStyleExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
            >
              <div>
                <h3 className="font-semibold text-white text-left">Adjust Positions & Styling</h3>
                <p className="text-sm text-zinc-400 text-left mt-1">Change text sizes, fonts, and positions for all posters</p>
              </div>
              <div className="text-zinc-500">
                {isStyleExpanded ? "▲" : "▼"}
              </div>
            </button>
            
            {isStyleExpanded && (
              <div className="p-6 border-t border-zinc-800 space-y-8 max-h-[600px] overflow-y-auto">
                {layers.map((layer) => {
                  if (!layer.id || !layer.box) return null;
                  const isText = layer.type?.toLowerCase() === "text";
                  
                  // Read current overrides or fallback to original layer properties
                  const currentLayout = layoutOverrides[layer.id] || { x: layer.box.x, y: layer.box.y };
                  const currentStyle = styleOverrides[layer.id] || {};
                  
                  return (
                    <div key={layer.id} className="bg-zinc-950 p-5 rounded-xl border border-zinc-800/50 space-y-4">
                      <h4 className="font-semibold text-indigo-300">Placeholder: {layer.id}</h4>

                      {/* Layout X/Y Controls */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-zinc-400">X Position</label>
                            <span className="text-xs text-zinc-500">{currentLayout.x}px</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max={canvasSize.width}
                            value={currentLayout.x || 0}
                            onChange={(e) => setLayoutOverrides({
                              ...layoutOverrides, 
                              [layer.id]: { ...currentLayout, x: parseInt(e.target.value) }
                            })}
                            className="w-full"
                          />
                        </div>
                        <div>
                          <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-zinc-400">Y Position</label>
                            <span className="text-xs text-zinc-500">{currentLayout.y}px</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max={canvasSize.height}
                            value={currentLayout.y || 0}
                            onChange={(e) => setLayoutOverrides({
                              ...layoutOverrides, 
                              [layer.id]: { ...currentLayout, y: parseInt(e.target.value) }
                            })}
                            className="w-full"
                          />
                        </div>
                      </div>

                      {/* Style Controls (Only for text layers) */}
                      {isText && (
                        <div className="grid grid-cols-2 gap-4 mt-2 pt-4 border-t border-zinc-800/50">
                          <div>
                            <label className="block text-xs font-medium text-zinc-400 mb-1">Font Family</label>
                            <select 
                              value={currentStyle.font_family || ""}
                              onChange={(e) => setStyleOverrides({
                                ...styleOverrides,
                                [layer.id]: { ...currentStyle, font_family: e.target.value }
                              })}
                              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white"
                            >
                              <option value="">(Default)</option>
                              <option value="Poppins">Poppins</option>
                              <option value="NotoSans">NotoSans</option>
                              <option value="Arial">Arial</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-zinc-400 mb-1">Font Weight</label>
                            <select 
                              value={currentStyle.font_weight || ""}
                              onChange={(e) => setStyleOverrides({
                                ...styleOverrides,
                                [layer.id]: { ...currentStyle, font_weight: e.target.value }
                              })}
                              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white"
                            >
                              <option value="">(Default)</option>
                              <option value="regular">Normal</option>
                              <option value="bold">Bold</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-zinc-400 mb-1">Font Size</label>
                            <input
                              type="number"
                              value={currentStyle.font_size || layer.style?.font_size || 48}
                              onChange={(e) => setStyleOverrides({
                                ...styleOverrides,
                                [layer.id]: { ...currentStyle, font_size: parseInt(e.target.value) }
                              })}
                              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-zinc-400 mb-1">Color (Hex)</label>
                            <input
                              type="text"
                              placeholder="#FFFFFF"
                              value={currentStyle.color || ""}
                              onChange={(e) => setStyleOverrides({
                                ...styleOverrides,
                                [layer.id]: { ...currentStyle, color: e.target.value }
                              })}
                              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white uppercase"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                <div className="sticky bottom-0 bg-zinc-900/90 backdrop-blur-md pt-4 pb-2 border-t border-zinc-800">
                  <button
                    onClick={handlePreview}
                    disabled={isPreviewing}
                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors shadow-lg flex items-center justify-center disabled:opacity-50"
                  >
                    {isPreviewing ? <Loader2 className="animate-spin h-5 w-5 mr-2" /> : null}
                    Apply Styles & Re-render Preview
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Job Status Panel */}
      {jobId && jobStatus && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 mt-6 col-span-1 lg:col-span-2">
          <h3 className="font-semibold text-lg text-white mb-4">Job Status</h3>
          <div className="space-y-4">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Status:</span>
              <span className="font-medium text-white capitalize">{jobStatus.status}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Progress:</span>
              <span className="font-medium text-white">
                {jobStatus.completed} / {jobStatus.total} ({jobStatus.skipped} skipped)
              </span>
            </div>
            
            {/* Progress bar */}
            <div className="w-full bg-zinc-800 rounded-full h-2.5 overflow-hidden">
              <div 
                className={`h-2.5 rounded-full ${jobStatus.status === 'failed' ? 'bg-red-500' : 'bg-indigo-500'} transition-all duration-500`} 
                style={{ width: `${Math.max(5, (jobStatus.completed / (jobStatus.total || 1)) * 100)}%` }}
              ></div>
            </div>

            {jobStatus.status === "failed" && (
              <div className="p-4 bg-red-500/20 border border-red-500/50 rounded-xl text-red-400 text-sm">
                {jobStatus.error}
              </div>
            )}

            {jobStatus.status === "done" && jobStatus.download_url && (
              <button
                onClick={() => handleDownload(jobStatus.download_url)}
                className="w-full py-3 px-4 mt-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors shadow-lg flex items-center justify-center"
              >
                Download ZIP Archive
              </button>
            )}
          </div>
        </div>
      )}

      {/* Preview Section */}
      <div className="flex flex-col h-full space-y-6">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 flex flex-col items-center justify-center min-h-[400px]">
          {previewImage ? (
            <div className="relative w-full h-full flex flex-col items-center">
              <h3 className="text-sm font-medium text-zinc-400 mb-4 self-start">Live Preview (Row 1)</h3>
              <img
                src={previewImage}
                alt="Generated preview"
                className="max-h-[500px] w-auto object-contain rounded-lg shadow-2xl shadow-black/50"
              />
            </div>
          ) : (
            <div className="flex flex-col items-center text-zinc-600">
              <ImageIcon className="w-16 h-16 mb-4 opacity-50" />
              <p>Preview of the first row will appear here</p>
            </div>
          )}
        </div>

        {/* Column Mapping Editor Section */}
        {layers.length > 0 && excelColumns.length > 0 && (
          <>
            <button
              onClick={() => setIsMapperModalOpen(true)}
              className="w-full py-4 px-6 bg-zinc-800 hover:bg-zinc-700 text-white font-semibold rounded-2xl transition-colors shadow-lg border border-zinc-700 flex justify-between items-center"
            >
              <div className="text-left">
                <span className="block">Review & Adjust Column Mapping</span>
                <span className="block text-sm text-zinc-400 font-normal mt-1">Match Excel columns to template fields</span>
              </div>
              <span className="text-indigo-400">Open Map</span>
            </button>

            {isMapperModalOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                <div className="bg-zinc-900 border border-zinc-700 rounded-3xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
                  
                  {/* Modal Header */}
                  <div className="px-6 py-5 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/80">
                    <div>
                      <h3 className="font-semibold text-lg text-white">Review & Adjust Column Mapping</h3>
                      <p className="text-sm text-zinc-400">Choose which Excel column maps to each template placeholder</p>
                    </div>
                    <button 
                      onClick={() => setIsMapperModalOpen(false)}
                      className="text-zinc-500 hover:text-white transition-colors"
                    >
                      ✕
                    </button>
                  </div>

                  {/* Modal Body */}
                  <div className="p-6 overflow-y-auto space-y-4 flex-1">
                    {layers.map((layer) => {
                      if (!layer.id) return null;
                      const canInvent = layer.llm_can_invent;
                      if (canInvent) return null;
                      
                      const currentMappedCol = columnMap[layer.id] || "";

                      return (
                        <div key={layer.id} className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/50 flex flex-col">
                          <label className="text-sm font-semibold text-indigo-300 mb-2">
                            Field: {layer.id}
                          </label>
                          <select 
                            value={currentMappedCol}
                            onChange={(e) => setColumnMap({ ...columnMap, [layer.id]: e.target.value })}
                            className="w-full px-3 py-2.5 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          >
                            <option value="">(Choose column...)</option>
                            {excelColumns.map((col) => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                        </div>
                      );
                    })}
                  </div>

                  {/* Modal Footer */}
                  <div className="p-5 border-t border-zinc-800 bg-zinc-900/90 flex gap-3">
                    <button
                      onClick={() => setIsMapperModalOpen(false)}
                      className="flex-1 py-3 px-4 bg-zinc-800 hover:bg-zinc-700 text-white font-medium rounded-xl transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => {
                        setIsMappingConfirmed(true);
                        setIsMapperModalOpen(false);
                        handlePreview();
                      }}
                      disabled={isPreviewing}
                      className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors shadow-lg flex items-center justify-center disabled:opacity-50"
                    >
                      {isPreviewing ? <Loader2 className="animate-spin h-5 w-5 mr-2" /> : null}
                      Update Preview
                    </button>
                  </div>

                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
