"use client";

import { useState } from "react";
import { Loader2, Image as ImageIcon, Upload, Send } from "lucide-react";
import { useAuth } from "./AuthProvider";

export function SinglePoster() {
  const { token } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [error, setError] = useState("");
  
  // Missing fields state
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [templateContext, setTemplateContext] = useState<{folder: string, template_id: string} | null>(null);

  // Editor state
  const [layers, setLayers] = useState<any[]>([]);
  const [canvasSize, setCanvasSize] = useState<{width: number, height: number}>({ width: 1024, height: 1536 });
  const [layoutOverrides, setLayoutOverrides] = useState<Record<string, {x?: number, y?: number}>>({});
  const [styleOverrides, setStyleOverrides] = useState<Record<string, {font_family?: string, font_weight?: string, font_size?: number, color?: string}>>({});
  const [isEditorExpanded, setIsEditorExpanded] = useState(false);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Please enter a prompt first.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("prompt", prompt);
      if (photo) {
        formData.append("image", photo);
      }

      // Include layout & style overrides if we have any (converted to JSON strings)
      if (Object.keys(layoutOverrides).length > 0) {
        formData.append("layout_overrides", JSON.stringify(layoutOverrides));
      }
      if (Object.keys(styleOverrides).length > 0) {
        formData.append("style_overrides", JSON.stringify(styleOverrides));
      }
      
      // Append any manual field values the user provided
      Object.entries(fieldValues).forEach(([key, val]) => {
        if (val.trim()) {
          formData.append(key, val.trim());
        }
      });

      // Pass along the template context if we are resuming from a needs_input state5
      if (templateContext) {
        if (templateContext.folder) formData.append("folder", templateContext.folder);
        if (templateContext.template_id) formData.append("template_id", templateContext.template_id);
      }

      const res = await fetch("http://localhost:8000/generate?json=true", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Failed to generate poster.");
      }

      const data = await res.json();

      if (data.status === "success") {
        setGeneratedImage(`data:image/png;base64,${data.image}`);
        
        // Save the layers and canvas info for the editor
        if (data.overlay_layers) {
          setLayers(data.overlay_layers);
        }
        if (data.canvas) {
          setCanvasSize({ width: data.canvas.width || 1024, height: data.canvas.height || 1536 });
        }
        
        // Ensure any values returned from the LLM (like caption) are pushed back into our editable fieldValues state
        if (data.overlay_values) {
          setFieldValues((prev) => ({ ...prev, ...data.overlay_values }));
        }

        // Reset the missing fields state on success
        setMissingFields([]);
        setTemplateContext(null);
      } else if (data.status === "ambiguous") {
        setError("Ambiguous prompt. Please be more specific about the template.");
      } else if (data.status === "needs_input") {
        setMissingFields(data.missing_fields);
        setTemplateContext({
          folder: data.folder,
          template_id: data.template_id
        });
      } else {
        setError("Unexpected response from server.");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
      {/* Input Section */}
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            What poster do you need?
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Holi poster for Rahul Kumar"
            className="w-full h-32 px-4 py-3 bg-zinc-800/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            Upload profile photo (optional)
          </label>
          <div className="flex items-center justify-center w-full">
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-zinc-700 border-dashed rounded-xl cursor-pointer bg-zinc-800/20 hover:bg-zinc-800/50 transition-all">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <Upload className="w-8 h-8 text-zinc-500 mb-2" />
                <p className="text-sm text-zinc-400">
                  <span className="font-medium text-indigo-400">Click to upload</span> or drag and drop
                </p>
                {photo && (
                  <p className="text-xs text-green-400 mt-2 font-medium">
                    Selected: {photo.name}
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

        {missingFields.length > 0 && (
          <div className="p-5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl space-y-4">
            <h3 className="font-medium text-indigo-300 flex items-center gap-2">
              Please provide missing details:
            </h3>
            <div className="space-y-4">
              {missingFields.map((field) => (
                <div key={field}>
                  <label className="block text-sm font-medium text-zinc-300 mb-1 capitalize">
                    {field.replace(/_/g, " ")}
                  </label>
                  <input
                    type="text"
                    value={fieldValues[field] || ""}
                    onChange={(e) => setFieldValues({ ...fieldValues, [field]: e.target.value })}
                    className="w-full px-3 py-2 bg-zinc-800/80 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
                    placeholder={`Enter ${field}`}
                    required
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={isLoading || !prompt.trim()}
          className="w-full py-3.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-900 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
        >
          {isLoading ? (
            <>
              <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" />
              Generating...
            </>
          ) : (
            <>
              <Send className="w-5 h-5 mr-2" />
              {missingFields.length > 0 ? "Continue Generation" : "Generate Poster"}
            </>
          )}
        </button>
      </div>

      {/* Preview Section */}
      <div className="flex flex-col h-full space-y-6">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 flex flex-col items-center justify-center min-h-[400px]">
          {generatedImage ? (
            <div className="relative w-full h-full flex flex-col items-center">
              <h3 className="text-sm font-medium text-zinc-400 mb-4 self-start">Generated Result</h3>
              <img
                src={generatedImage}
                alt="Generated poster"
                className="max-h-[800px] w-auto object-contain rounded-lg shadow-2xl shadow-black/50"
              />
            </div>
          ) : (
            <div className="flex flex-col items-center text-zinc-600">
              <ImageIcon className="w-16 h-16 mb-4 opacity-50" />
              <p>Your generated poster will appear here</p>
            </div>
          )}
        </div>

        {/* Visual Editor Section */}
        {layers.length > 0 && generatedImage && (
          <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl">
            <button
              onClick={() => setIsEditorExpanded(!isEditorExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
            >
              <div>
                <h3 className="font-semibold text-white text-left">Adjust Positions & Styling</h3>
                <p className="text-sm text-zinc-400 text-left mt-1">Change text, position, and fonts</p>
              </div>
              <div className="text-zinc-500">
                {isEditorExpanded ? "▲" : "▼"}
              </div>
            </button>
            
            {isEditorExpanded && (
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
                      
                      {/* Text Editor (Only for text layers) */}
                      {isText && (
                        <div>
                          <label className="block text-xs font-medium text-zinc-400 mb-1">Text Content</label>
                          <textarea
                            value={fieldValues[layer.id] || ""}
                            onChange={(e) => setFieldValues({ ...fieldValues, [layer.id]: e.target.value })}
                            className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white resize-none"
                            rows={2}
                          />
                        </div>
                      )}

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
                    onClick={handleGenerate}
                    disabled={isLoading}
                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl transition-colors shadow-lg flex items-center justify-center disabled:opacity-50"
                  >
                    {isLoading ? <Loader2 className="animate-spin h-5 w-5 mr-2" /> : null}
                    Apply Changes & Re-generate
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
