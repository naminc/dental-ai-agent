import type { Metadata } from "next";
import "./globals.css";
import { APP_CONFIG } from "@/lib/constants";

export const metadata: Metadata = {
  title: `${APP_CONFIG.NAME} - ${APP_CONFIG.DESCRIPTION}`,
  description:
    APP_CONFIG.DESCRIPTION,
  generator: "v0.app",
  icons: {
    icon: [
      {
        url: "/icon-light-32x32.png",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/icon-dark-32x32.png",
        media: "(prefers-color-scheme: dark)",
      },
      {
        url: "/icon.svg",
        type: "image/svg+xml",
      },
    ],
    apple: "/apple-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
