"use client";
import {motion} from "framer-motion";

import Link from "next/link";
import {
Upload,
FileText,
FolderOpen
} from "lucide-react";


export default function QuickActions(){


const actions=[

{
name:"Analyze New Image",
icon:<Upload/>,
link:"/analyze"
},

{
name:"View Reports",
icon:<FileText/>,
link:"/reports"
},

{
  name: "Manage Cases",
  icon: <FolderOpen />,
  link: "/cases"
}

];


return (

<motion.div

initial={{
opacity:0,
y:20
}}

animate={{
opacity:1,
y:0
}}

>


<h2

className="
text-2xl
font-bold
mb-6
"

>

Quick Actions

</h2>


<div

className="
grid
md:grid-cols-3
gap-5
"

>


{
actions.map((action)=>(


<Link

key={action.name}

href={action.link}

className="
flex
items-center
gap-4
rounded-2xl
bg-black/20
p-5
hover:bg-cyan-400/10
transition
"

>

<div

className="
text-cyan-400
"

>

{action.icon}

</div>


<span>

{action.name}

</span>


</Link>


))

}


</div>


</motion.div>


)

}