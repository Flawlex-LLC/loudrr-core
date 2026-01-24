import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
) {
  const path = params.path.join('/');
  const url = new URL(request.url);
  // Always add trailing slash for Django's APPEND_SLASH setting
  const backendUrl = `${BACKEND_URL}/api/miniapp/${path}/${url.search}`;

  console.log(`[Proxy] ${request.method} ${backendUrl}`);

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Forward Telegram init data header
  const initData = request.headers.get('X-Telegram-Init-Data');
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  try {
    let body: string | undefined;
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      body = await request.text();
    }

    const response = await fetch(backendUrl, {
      method: request.method,
      headers,
      body,
    });

    // Handle response based on content type
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } else {
      // Non-JSON response (error page, HTML, etc.)
      const text = await response.text();
      console.error(`[Proxy] Backend returned non-JSON (${response.status}):`, text.substring(0, 200));
      return NextResponse.json(
        { error: 'Backend error', details: text.substring(0, 100) },
        { status: response.status || 502 }
      );
    }
  } catch (error) {
    console.error('[Proxy] Connection error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to backend. Is Django running on port 8000?' },
      { status: 502 }
    );
  }
}
