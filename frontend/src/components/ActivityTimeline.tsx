"use client";
import {motion} from "framer-motion";

const activities=[

"Image analysis completed - Case NE-004",

"Grad-CAM explanation generated",

"Forensic report created",

"New investigation started"

];


export default function ActivityTimeline(){


return (

<motion.div

initial={{
opacity:0,
x:30
}}

animate={{
opacity:1,
x:0
}}

transition={{
duration:.5
}}

>


<h2

className="
text-2xl
font-bold
mb-6
"

>

Recent Activity

</h2>



<div className="space-y-5">


{
activities.map((item,index)=>(


<div

key={index}

className="
flex
gap-4
items-center
"

>


<div

className="
h-3
w-3
rounded-full
bg-cyan-400
"

>



</div>



<p className="text-slate-300">

{item}

</p>


</div>


))

}


</div>


</motion.div>


)


}