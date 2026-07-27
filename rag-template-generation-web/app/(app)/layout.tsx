import Sidebar from "@/components/Sidebar";
import { TabStateProvider } from "@/context/TabStateContext";


export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <TabStateProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
        <Sidebar />
        <main className="flex-1 overflow-y-auto h-full relative">
          {children}
        </main>
      </div>
    </TabStateProvider>
  );
}
