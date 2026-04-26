import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import ShaderFilters from "@/components/ShaderFilters";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NFL Draft Intelligence | Explainable AI Analytics",
  description: "A professional, out-of-sample validated XGBoost platform for NFL draft scouting, featuring SHAP-weighted historical clones and dynamic draft capital scaling.",
  openGraph: {
    title: "NFL Draft Intelligence",
    description: "Explainable AI Analytics for predictive NFL drafting.",
    images: ["/og.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "NFL Draft Intelligence",
    description: "Explainable AI Analytics for predictive NFL drafting.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ShaderFilters />
        {children}
      </body>
    </html>
  );
}
