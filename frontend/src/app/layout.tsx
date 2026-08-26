import type { Metadata } from 'next';
import '../index.css';

export const metadata: Metadata = {
  title: 'Punarvritt',
  description: 'Circular economy, plastic waste recycling, and EPR compliance platform frontend authentication flow for Brands and Recyclers.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
