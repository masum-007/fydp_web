"use client";
import { ReactNode } from "react";
import {motion} from "framer-motion";

export default function StatsCard({

title,
value,
icon


}:{

title:string;
value:string;
icon:ReactNode;

}){


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

transition={{
duration:0.5
}}

className="
rounded-3xl
border
border-white/10
bg-white/5
backdrop-blur-xl
p-7
hover:-translate-y-1
transition
"

>


<div
className="
text-cyan-400
mb-5
"
>

{icon}

</div>


<p

className="
text-slate-400
"

>

{title}

</p>



<h2

className="
text-4xl
font-bold
mt-2
"

>

{value}

</h2>



</motion.div>


)

}