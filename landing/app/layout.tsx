import type { Metadata } from "next";
import { Syne } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  weight: ["700", "800"],
  variable: "--font-syne",
});

export const metadata: Metadata = {
  title: "Loudrr - Earn Karma by Engaging",
  description: "Loudrr is a karma-based attention marketplace. Earn karma by engaging with posts. Spend karma to get engagement on yours.",
  icons: {
    icon: [
      { url: "/loudrr-icon.png", type: "image/png" },
    ],
    apple: "/loudrr-icon.png",
  },
  openGraph: {
    title: "Loudrr - Earn Karma by Engaging",
    description: "Join the waitlist for Loudrr - a karma-based attention marketplace.",
    type: "website",
  },
};

// GTM Container ID
const GTM_ID = "GTM-5N3W93HT";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={syne.variable}>
      <head>
        {/* Google Tag Manager */}
        <Script
          id="gtm-script"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
              new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
              j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
              'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
              })(window,document,'script','dataLayer','${GTM_ID}');
            `,
          }}
        />
      </head>
      <body className="antialiased">
        {/* Google Tag Manager (noscript) */}
        <noscript>
          <iframe
            src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
            height="0"
            width="0"
            style={{ display: "none", visibility: "hidden" }}
          />
        </noscript>
        {children}
      </body>
    </html>
  );
}
