"use client";


import {
useAuth
} from "./AuthProvider";


import {
useRouter
} from "next/navigation";


import {
useEffect
} from "react";



export default function ProtectedRoute({

children

}:{

children:React.ReactNode;

}){


const {
user
}=useAuth();


const router=useRouter();



useEffect(()=>{


if(user?.role !== "investigator"){

router.push("/login");

}


},[user,router]);



if(user?.role !== "investigator"){

return (

<div

className="
min-h-screen
flex
items-center
justify-center
text-white
"

>

Checking authentication...

</div>

)

}



return children;


}