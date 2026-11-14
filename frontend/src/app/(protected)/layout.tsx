import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Sidebar from "@/components/Sidebar";

export default function ProtectedLayout({children}: {children: React.ReactNode}) {
  return <ProtectedRoute><div className="min-h-screen bg-[#050816] pt-28 text-white lg:pl-[305px]">
    <Sidebar />
    <div className="mx-auto max-w-[1540px]">{children}</div>
  </div></ProtectedRoute>;
}
