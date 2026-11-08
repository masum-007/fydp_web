import ProtectedRoute from "@/components/auth/ProtectedRoute";


export default function DashboardLayout({

children

}:{

children:React.ReactNode;

}){


return (

<ProtectedRoute>


<div

className="
min-h-screen
bg-[#050816]
text-white
pt-24
"

>

{children}


</div>


</ProtectedRoute>

)

}