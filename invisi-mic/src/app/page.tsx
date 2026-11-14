import Sidebar from "@/_components/Sidebar/Sidebar";
import Topbar from "@/_components/Topbar";
import Image from "next/image";

export default function Home() {
  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <div className="flex min-h-0 flex-1">
        <main className="flex-1" />
        <Sidebar />
      </div>
    </div>
  );
}
