import { ImageResponse } from '@vercel/og'
import { NextRequest } from 'next/server'

export const runtime = 'edge'

// Google Fonts URLs (TTF format)
const SPACE_GROTESK_BOLD_URL = 'https://fonts.gstatic.com/s/spacegrotesk/v22/V8mQoQDjQSkFtoMM3T6r8E7mF71Q-gOoraIAEj4PVksj.ttf'
const SYNE_BOLD_URL = 'https://fonts.gstatic.com/s/syne/v24/8vIS7w4qzmVxsWxjBZRjr0FKM_3fvj6k.ttf'

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const username = searchParams.get('username') || 'user'
  const displayName = searchParams.get('displayName') || username
  const score = searchParams.get('score') || ''
  const tier = searchParams.get('tier') || ''

  // Load fonts in parallel from Google Fonts CDN
  const [syneFontData, spaceGroteskFontData] = await Promise.all([
    fetch(SYNE_BOLD_URL).then((res) => res.arrayBuffer()),
    fetch(SPACE_GROTESK_BOLD_URL).then((res) => res.arrayBuffer()),
  ])

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0a0a0a',
          position: 'relative',
        }}
      >
        {/* Background gradient */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'radial-gradient(ellipse 100% 80% at 50% 100%, rgba(249, 84, 0, 0.2) 0%, transparent 50%)',
          }}
        />

        {/* Main card */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '900px',
            height: '540px',
            background: 'rgba(20, 20, 22, 0.95)',
            borderRadius: '24px',
            border: '1px solid rgba(249, 84, 0, 0.3)',
            padding: '40px',
            position: 'relative',
          }}
        >
          {/* Brand */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
            <span style={{ fontSize: '28px', fontWeight: 700, color: '#f95400', fontFamily: 'Syne' }}>
              Loudrr
            </span>
          </div>

          {/* Welcome title */}
          <span style={{ fontSize: '64px', fontWeight: 700, color: '#ffffff', marginBottom: '8px', fontFamily: 'Space Grotesk' }}>
            Welcome!
          </span>

          {/* Subtitle */}
          <span style={{ fontSize: '28px', fontWeight: 600, color: '#f95400', marginBottom: '24px', fontFamily: 'Space Grotesk' }}>
            You've been approved
          </span>

          {/* Profile section */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            {/* Avatar placeholder */}
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: 'rgba(249, 84, 0, 0.2)',
                border: '2px solid #f95400',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '28px',
                fontWeight: 700,
                color: '#f95400',
                fontFamily: 'Space Grotesk',
              }}
            >
              {displayName[0]?.toUpperCase() || 'U'}
            </div>

            {/* Name + stats */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '24px', fontWeight: 700, color: '#fff', fontFamily: 'Space Grotesk' }}>
                {displayName}
              </span>
              {(score || tier) && (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {score && (
                    <span style={{ fontSize: '16px', color: 'rgba(255,255,255,0.6)', fontFamily: 'Space Grotesk' }}>
                      Score: {score}
                    </span>
                  )}
                  {score && tier && (
                    <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
                  )}
                  {tier && (
                    <span style={{ fontSize: '16px', color: '#f95400', fontWeight: 600, fontFamily: 'Space Grotesk' }}>
                      {tier.toUpperCase()}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Username pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 28px',
              background: 'rgba(249, 84, 0, 0.1)',
              borderRadius: '100px',
              border: '1px solid rgba(249, 84, 0, 0.3)',
            }}
          >
            <svg width={24} height={24} viewBox="0 0 24 24" fill="#f95400">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            <span style={{ fontSize: '24px', fontWeight: 700, color: '#f95400', fontFamily: 'Space Grotesk' }}>
              @{username}
            </span>
          </div>

          {/* Bottom section */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 'auto', gap: '8px' }}>
            <div style={{ width: '300px', height: '1px', background: 'linear-gradient(90deg, transparent, rgba(249, 84, 0, 0.4), transparent)', marginBottom: '16px' }} />
            <span style={{ fontSize: '16px', color: 'rgba(255,255,255,0.5)', fontFamily: 'Space Grotesk' }}>
              Earn karma by engaging. Spend karma to grow.
            </span>
            <span style={{ fontSize: '16px', fontWeight: 600, color: '#f95400', fontFamily: 'Space Grotesk' }}>
              Tap below to start
            </span>
          </div>
        </div>
      </div>
    ),
    {
      width: 1012,
      height: 638,
      fonts: [
        {
          name: 'Syne',
          data: syneFontData,
          style: 'normal',
          weight: 700,
        },
        {
          name: 'Space Grotesk',
          data: spaceGroteskFontData,
          style: 'normal',
          weight: 700,
        },
      ],
    }
  )
}
