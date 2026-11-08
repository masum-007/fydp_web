"use client";

import { useAuth } from "./auth/AuthProvider";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  ShieldCheck,
  UserCircle,
  ChevronDown
} from "lucide-react";


export default function Navbar(){

const {
user,
logout
}=useAuth();

const router=useRouter();

const pathname = usePathname();



const publicLinks = [

{
name:"Home",
path:"/"
},

{
name:"Try Detection",
path:"/detect"
}

];


const privateLinks = [

{
name:"Dashboard",
path:"/dashboard"
},

{
name:"Analyze",
path:"/analyze"
},

{
name:"Cases",
path:"/cases"
},

{
name:"Reports",
path:"/reports"
}

];


const links =
user?.role === "investigator"
?
privateLinks
:
publicLinks;



return (

<nav

className="
fixed
top-0
left-0
right-0
z-50
px-6
pt-5
"

>


<div

className="
max-w-7xl
mx-auto
flex
items-center
justify-between
rounded-2xl
border
border-white/10
bg-[#0b1020]/80
backdrop-blur-xl
px-8
py-4
shadow-lg
"

>



{/* LOGO */}


<Link

href="/"

className="
flex
items-center
gap-3
group
"

>


<div

className="
flex
items-center
justify-center
h-11
w-11
rounded-xl
bg-cyan-400/10
border
border-cyan-400/30
group-hover:bg-cyan-400/20
transition
"

>


<ShieldCheck

className="
text-cyan-400
"

size={26}

/>


</div>



<div>


<h1
className="
text-xl
font-bold
tracking-wide
text-white
"
>
NeuralEdge AI
</h1>



<p

className="
text-xs
text-slate-400
"

>

AI Forensic Intelligence

</p>


</div>



</Link>





{/* NAV LINKS */}


<div

className="
hidden
md:flex
items-center
gap-2
"

>


{
links.map((link)=>(


<Link

key={link.path}

href={link.path}

className={`

px-5
py-2.5
rounded-xl
transition
duration-300

${
pathname===link.path

?

"bg-cyan-400/10 text-cyan-300"

:

"text-slate-300 hover:bg-white/10 hover:text-white"

}

`}

>


{link.name}


</Link>


))

}



</div>






{/* USER AREA */}

<div

className="
hidden
md:flex
items-center
gap-3
rounded-xl
border
border-white/10
bg-white/5
px-4
py-2
"

>


<UserCircle

className="
text-cyan-400
"

size={25}

/>


<div
className="
text-left
"

>


<p

className="
text-sm
font-medium
text-white
"

>

{
user?.role === "investigator"

?

"Investigator"

:

"Guest User"

}

</p>



<p

className="
text-xs
text-slate-400
"

>

{
user?.role === "investigator"

?

"Active Session"

:

"Public Access"

}

</p>


</div>



{

user?.role === "investigator"

?

<button

onClick={()=>{

logout();

router.push("/");

}}

className="
text-xs
text-red-400
hover:text-red-300
ml-3
"

>

Logout

</button>


:

<Link

href="/login"

className="
text-xs
text-cyan-400
hover:text-cyan-300
ml-3
"

>

Login

</Link>


}



<ChevronDown

size={16}

className="
text-slate-400
"

/>



</div>



</div>



</nav>


)

}