"use client";


import Link from "next/link";

import {
Menu,
X,
LayoutDashboard,
Search,
FolderOpen,
FileText,
Brain,
Settings
} from "lucide-react";


import {useState} from "react";



const menu=[

{
name:"Dashboard",
icon:<LayoutDashboard/>,
path:"/dashboard"
},

{
name:"Analyze Image",
icon:<Search/>,
path:"/analyze"
},

{
name:"Investigation Cases",
icon:<FolderOpen/>,
path:"/cases"
},

{
name:"Reports",
icon:<FileText/>,
path:"/reports"
},

{
name:"Model Analytics",
icon:<Brain/>,
path:"/model-analytics"
},

{
name:"Settings",
icon:<Settings/>,
path:"/settings"
}

];



export default function Sidebar(){


const [open,setOpen]=useState(false);



return (

<>


<button

onClick={()=>setOpen(true)}

className="
lg:hidden
fixed
top-24
left-5
z-50
rounded-xl
bg-cyan-500/20
p-3
"

>

<Menu/>

</button>




<aside

className={`
fixed
z-50
left-6
top-28
bottom-6
w-64
rounded-3xl
border
border-cyan-400/10
bg-[#080d1c]/95
backdrop-blur-xl
p-6

transition-transform

${

open

?

"translate-x-0"

:

"-translate-x-[120%] lg:translate-x-0"

}

`}

>


<div className="
flex
justify-between
mb-8
">


<h2 className="
font-bold
text-cyan-300
">

Investigation Panel

</h2>



<button

className="lg:hidden"

onClick={()=>setOpen(false)}

>

<X/>

</button>


</div>



<div className="space-y-3">


{
menu.map(item=>(


<Link

key={item.name}

href={item.path}

className="
flex
gap-4
items-center
rounded-xl
px-4
py-3
text-slate-300
hover:bg-cyan-400/10
hover:text-cyan-300
transition
"

>


{item.icon}

{item.name}


</Link>


))
}


</div>


</aside>


</>

)

}