import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PHC Scribe Review",
  description: "Clinical review and labelling for the PHC Scribe benchmark.",
  robots: { index: false, follow: false },
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#070d10",
};

function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute -left-40 -top-48 h-[560px] w-[560px] animate-drift rounded-full bg-leaf-500/20 blur-[130px]" />
      <div className="absolute -right-48 top-1/4 h-[520px] w-[520px] animate-drift rounded-full bg-cyan-500/[.14] blur-[130px] [animation-delay:-6s]" />
      <div className="absolute -bottom-56 left-1/4 h-[460px] w-[460px] animate-drift rounded-full bg-fuchsia-500/[.08] blur-[130px] [animation-delay:-11s]" />
      <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,black,transparent)]" />
    </div>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-dvh">
        <Aurora />
        {children}
      </body>
    </html>
  );
}
