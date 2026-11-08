import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Sidebar from "@/components/Sidebar";


export default function ProtectedLayout({

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


<Sidebar/>


{children}


</div>


</ProtectedRoute>

)

}