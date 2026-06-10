import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "PeopleGraph",
  description: "Professional people lookup portal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
