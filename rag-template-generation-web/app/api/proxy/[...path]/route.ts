import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

async function forward(req: NextRequest, path: string[]) {
  const token = req.cookies.get("session_token")?.value;
  const targetUrl = `${FASTAPI_URL}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const contentType = req.headers.get("content-type") || "";
  let body: any = undefined;

  if (req.method !== "GET" && req.method !== "HEAD") {
    if (contentType.includes("multipart/form-data")) {
      // Pass through file uploads untouched
      body = await req.arrayBuffer();
      headers.set("content-type", contentType);
    } else if (contentType.includes("application/json")) {
      body = await req.text();
      headers.set("content-type", "application/json");
    } else {
      body = await req.arrayBuffer();
    }
  }

  try {
    const res = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });

    const responseContentType = res.headers.get("content-type") || "";

    if (res.status === 204 || res.status === 205 || res.status === 304) {
      return new NextResponse(null, { status: res.status });
    }

    // Binary responses (images, ZIP files)
    if (
      responseContentType.includes("image/") ||
      responseContentType.includes("application/zip") ||
      responseContentType.includes("application/octet-stream")
    ) {
      const buf = await res.arrayBuffer();
      return new NextResponse(buf, {
        status: res.status,
        headers: { "content-type": responseContentType },
      });
    }

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { "content-type": responseContentType },
    });
  } catch (err: any) {
    console.error(`Proxy error forwarding to ${targetUrl}:`, err);
    return NextResponse.json(
      { error: "Backend service unreachable", details: err.message },
      { status: 503 }
    );
  }
}

export async function GET(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return forward(req, params.path);
}
export async function POST(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return forward(req, params.path);
}
export async function DELETE(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return forward(req, params.path);
}
export async function PUT(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return forward(req, params.path);
}
