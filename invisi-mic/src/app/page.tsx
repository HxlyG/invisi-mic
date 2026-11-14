import Sidebar from "@/_components/Sidebar/Sidebar";
import Toolbar from "@/_components/Toolbar/Toolbar";
import Topbar from "@/_components/Topbar";
import Viewport from "@/_components/Viewport/Viewport";

export const instant = false;

export default function Home() {
  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <div className="flex min-h-0 flex-1">
        <main className="relative min-w-0 flex-1">
          <Viewport />
          <Toolbar />
        </main>
        <Sidebar />
      </div>
    </div>
  );
}
