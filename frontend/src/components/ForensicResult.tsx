"use client";


import {motion} from "framer-motion";
import {
ShieldAlert,
Activity,
Cpu
} from "lucide-react";


export default function ForensicResult(){


return (

<motion.div

initial={{
opacity:0,
y:30
}}

animate={{
opacity:1,
y:0
}}

className="
rounded-3xl
border
border-red-400/20
bg-red-400/5
p-8
"

>


<div className="
flex
items-center
gap-4
">


<ShieldAlert

className="
text-red-400
"

size={35}

/>


<h2 className="
text-3xl
font-bold
">

Detection Result

</h2>


</div>




<div className="
mt-8
text-center
">


<p className="
text-slate-400
">

Classification

</p>


<h1 className="
mt-3
text-6xl
font-bold
text-red-400
">

FAKE

</h1>


</div>




<div className="
grid
md:grid-cols-3
gap-5
mt-10
">


<Metric

icon={<Activity/>}

title="Confidence"

value="97.6%"

/>


<Metric

icon={<Cpu/>}

title="Model"

value="Ensemble"

/>


<Metric

icon={<ShieldAlert/>}

title="Threshold"

value="0.56"

/>


</div>



</motion.div>

)

}





function Metric({

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
bg-black/30
p-5
"

>


<div className="
text-cyan-400
">

{icon}

</div>


<p className="
text-slate-400
mt-3
">

{title}

</p>


<h3 className="
text-xl
font-bold
mt-2
">

{value}

</h3>


</div>

)

}