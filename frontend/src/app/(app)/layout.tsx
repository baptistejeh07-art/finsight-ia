import { Sidebar } from "@/components/sidebar";
import { TopNav } from "@/components/top-nav";

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <Sidebar />
      <TopNav />
      <div className="md:pl-56 min-h-screen">{children}</div>
    </>
  );
}
