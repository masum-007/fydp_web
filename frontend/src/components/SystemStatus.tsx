"use client";
import {motion} from "framer-motion";

import {
  Cpu,
  Activity,
  ShieldCheck
} from "lucide-react";


export default function SystemStatus(){


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
duration:.5
}}

className="
rounded-3xl
border
border-white/10
bg-white/5
backdrop-blur-xl
p-8
"

>


<h2

className="
text-2xl
font-bold
mb-6
"

>

AI System Status

</h2>



<div

className="
grid
md:grid-cols-3
gap-6
"

>


<Status

icon={<Activity/>}

title="System"

value="Online"

/>


<Status

icon={<Cpu/>}

title="Model"

value="Ensemble Engine"

/>



<Status

icon={<ShieldCheck/>}

title="Explainability"

value="Grad-CAM Ready"

/>



</div>


</motion.div>

)

}




function Status({

icon,
title,
value

}:{

icon:React.ReactNode;
title:string;
value:string;

}){


return (

<div

className="
rounded-2xl
bg-black/20
p-6
"

>


<div

className="
text-cyan-400
mb-4
"

>

{icon}

</div>


<p className="text-slate-400">

{title}

</p>


<h3

className="
font-bold
mt-2
"

>

{value}

</h3>


</div>

)

}