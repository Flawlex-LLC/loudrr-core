import { ImageResponse } from '@vercel/og'
import { NextRequest } from 'next/server'

export const runtime = 'edge'

// Google Fonts URLs (TTF format)
const SPACE_GROTESK_BOLD_URL = 'https://fonts.gstatic.com/s/spacegrotesk/v22/V8mQoQDjQSkFtoMM3T6r8E7mF71Q-gOoraIAEj4PVksj.ttf'
const SYNE_BOLD_URL = 'https://fonts.gstatic.com/s/syne/v24/8vIS7w4qzmVxsWxjBZRjr0FKM_3fvj6k.ttf'

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const baseUrl = `${url.protocol}//${url.host}`

  // Load fonts and high-quality logo
  const [syneFontData, spaceGroteskFontData, logoData] = await Promise.all([
    fetch(SYNE_BOLD_URL).then(res => res.arrayBuffer()),
    fetch(SPACE_GROTESK_BOLD_URL).then(res => res.arrayBuffer()),
    fetch(`${baseUrl}/loudrr-icon.png`).then(res => res.arrayBuffer()),
  ])

  const logoBase64 = `data:image/png;base64,${Buffer.from(logoData).toString('base64')}`

  const { searchParams } = new URL(request.url)
  const xUsername = searchParams.get('username') || 'user'
  const displayName = searchParams.get('displayName') || xUsername
  const telegramUsername = searchParams.get('telegram') || ''

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
          background: 'linear-gradient(135deg, #0d0d0f 0%, #0a0a0c 50%, #080808 100%)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Ambient glow - top */}
        <div
          style={{
            position: 'absolute',
            top: '-20%',
            left: '30%',
            width: '500px',
            height: '400px',
            background: 'radial-gradient(ellipse at center, rgba(249, 84, 0, 0.12) 0%, transparent 70%)',
            filter: 'blur(60px)',
          }}
        />

        {/* Ambient glow - bottom */}
        <div
          style={{
            position: 'absolute',
            bottom: '-15%',
            right: '20%',
            width: '600px',
            height: '400px',
            background: 'radial-gradient(ellipse at center, rgba(249, 84, 0, 0.08) 0%, transparent 70%)',
            filter: 'blur(80px)',
          }}
        />

        {/* Halftone dots overlay */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: `radial-gradient(circle, rgba(255, 255, 255, 0.03) 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
          }}
        />

        {/* Main card */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            width: '880px',
            height: '520px',
            background: 'linear-gradient(180deg, rgba(8, 8, 10, 0.98) 0%, rgba(5, 5, 6, 0.99) 100%)',
            borderRadius: '32px',
            border: '1px solid rgba(249, 84, 0, 0.15)',
            padding: 0,
            position: 'relative',
            boxShadow: '0 0 0 1px rgba(255,255,255,0.03), 0 4px 24px rgba(0,0,0,0.4), 0 12px 48px rgba(0,0,0,0.3)',
          }}
        >
          {/* Card inner gradient overlay */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              borderRadius: '32px',
              background: 'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(249, 84, 0, 0.06) 0%, transparent 50%)',
            }}
          />

          {/* Halftone dots - white, small, tight spacing */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              borderRadius: '32px',
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='6' height='6' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='3' cy='3' r='0.8' fill='%23ffffff' fill-opacity='0.08'/%3E%3C/svg%3E")`,
              backgroundSize: '6px 6px',
            }}
          />

          {/* Glossy shine - full edge to edge sweep */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              borderRadius: '32px',
              background: 'linear-gradient(110deg, transparent 0%, rgba(255,255,255,0.04) 15%, rgba(255,255,255,0.10) 35%, rgba(255,255,255,0.14) 50%, rgba(255,255,255,0.10) 65%, rgba(255,255,255,0.04) 85%, transparent 100%)',
            }}
          />

          {/* Top edge highlight */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: '15%',
              right: '15%',
              height: '1px',
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)',
            }}
          />

          {/* Brand header with high-quality logo */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              marginBottom: '16px',
              zIndex: 1,
            }}
          >
            <img
              src={logoBase64}
              width={56}
              height={56}
              style={{
                objectFit: 'contain',
                filter: 'drop-shadow(0 2px 8px rgba(249, 84, 0, 0.3))',
              }}
            />
            <span
              style={{
                fontSize: '36px',
                fontWeight: 700,
                color: '#f95400',
                fontFamily: 'Syne',
                letterSpacing: '-0.5px',
                textShadow: '0 2px 12px rgba(249, 84, 0, 0.4)',
              }}
            >
              Loudrr
            </span>
          </div>

          {/* Main title with gradient text effect */}
          <div
            style={{
              display: 'flex',
              marginBottom: '24px',
              zIndex: 1,
            }}
          >
            <span
              style={{
                fontSize: '56px',
                fontWeight: 700,
                color: '#ffffff',
                fontFamily: 'Space Grotesk',
                letterSpacing: '-1.5px',
                textShadow: '0 4px 24px rgba(249, 84, 0, 0.3), 0 0 48px rgba(249, 84, 0, 0.15)',
              }}
            >
              You're on the Waitlist!
            </span>
          </div>

          {/* Profile section - Two columns */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '24px',
              padding: '20px 32px',
              background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.08) 0%, rgba(249, 84, 0, 0.03) 100%)',
              borderRadius: '20px',
              border: '1px solid rgba(249, 84, 0, 0.15)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.03)',
              zIndex: 1,
            }}
          >
            {/* Column 1: TG Avatar */}
            <div
              style={{
                width: '72px',
                height: '72px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #f95400 0%, #ff7b33 50%, #f95400 100%)',
                padding: '3px',
                boxShadow: '0 0 20px rgba(249, 84, 0, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, rgba(249, 84, 0, 0.2) 0%, rgba(18, 14, 12, 0.95) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <span
                  style={{
                    fontSize: '32px',
                    fontWeight: 700,
                    color: '#f95400',
                    fontFamily: 'Space Grotesk',
                  }}
                >
                  {displayName[0]?.toUpperCase() || 'U'}
                </span>
              </div>
            </div>

            {/* Column 2: X username + to be verified */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                gap: '4px',
              }}
            >
              {/* Row 1: X icon + username */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <svg width={22} height={22} viewBox="0 0 24 24" fill="#f95400">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
                <span style={{ fontSize: '24px', fontWeight: 600, color: '#f95400', fontFamily: 'Space Grotesk' }}>
                  @{xUsername}
                </span>
              </div>
              {/* Row 2: to be verified - aligned left with X icon */}
              <span style={{ fontSize: '15px', color: 'rgba(255,255,255,0.5)', fontFamily: 'Space Grotesk' }}>
                (to be verified)
              </span>
            </div>
          </div>

          {/* Bottom section */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: '24px', gap: '8px', zIndex: 1 }}>
            {/* Sleek gradient separator line */}
            <div
              style={{
                width: '320px',
                height: '0.5px',
                background: 'linear-gradient(90deg, transparent 0%, rgba(249, 84, 0, 0.4) 30%, rgba(249, 84, 0, 0.5) 50%, rgba(249, 84, 0, 0.4) 70%, transparent 100%)',
                marginBottom: '12px',
              }}
            />
            <span style={{ fontSize: '17px', color: 'rgba(255,255,255,0.55)', fontFamily: 'Space Grotesk' }}>
              We'll notify you here when you get access
            </span>
            <span
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: '#f95400',
                fontFamily: 'Syne',
                letterSpacing: '1.5px',
                textShadow: '0 2px 12px rgba(249, 84, 0, 0.5)',
              }}
            >
              Go Loudrr
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
