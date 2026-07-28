import { NextResponse } from "next/server";
import { GoogleGenAI } from "@google/genai";

let aiClient: GoogleGenAI | null = null;
function getGeminiClient() {
  if (!aiClient) {
    const apiKey = process.env.GEMINI_API_KEY;
    if (apiKey && apiKey !== "MY_GEMINI_API_KEY") {
      aiClient = new GoogleGenAI({
        apiKey,
        httpOptions: {
          headers: {
            "User-Agent": "aistudio-build",
          },
        },
      });
    }
  }
  return aiClient;
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { templateName, festival, topic, customInstructions } = body;
    const ai = getGeminiClient();

    if (!ai) {
      return NextResponse.json({
        title: festival || topic || "Celebrating Financial Growth",
        headline: "Empowering Your Wealth Journey with MS Fincap AI",
        tagline: "Smart investments for a secure and prosperous future.",
        bullets: [
          "Guaranteed Security & Transparency",
          "Tailored Financial Portfolio Guidance",
          "24/7 AI-Assisted Market Insights",
        ],
        disclaimer: "Investments are subject to market risks. Read all scheme related documents carefully.",
      });
    }

    const prompt = `You are the lead marketing copywriter for MS Fincap AI Intelligence, an elite financial institution.
Generate a crisp, high-converting poster copy for:
Template: ${templateName || "Financial Growth"}
Topic/Festival: ${festival || topic || "Independence Day Special"}
Additional Notes: ${customInstructions || "Include financial freedom theme"}

Return strict JSON with the following key names:
{
  "title": "Short catchy poster title (3-5 words)",
  "headline": "Powerful headline sentence",
  "tagline": "Subtitle or call to action sentence",
  "bullets": ["Point 1", "Point 2", "Point 3"],
  "disclaimer": "Standard financial disclaimer"
}`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
      },
    });

    const text = response.text || "";
    let jsonResult;
    try {
      jsonResult = JSON.parse(text);
    } catch (e) {
      jsonResult = {
        title: festival || "Financial Festival",
        headline: "Empowering Your Wealth Journey",
        tagline: "Smart investments for a secure future.",
        bullets: ["Growth Solutions", "Risk Protection", "AI Guidance"],
        disclaimer: "Investments subject to market risks.",
      };
    }

    return NextResponse.json(jsonResult);
  } catch (error: any) {
    console.error("AI Generation Error:", error);
    return NextResponse.json(
      { error: error.message || "Failed to generate poster text" },
      { status: 500 }
    );
  }
}
