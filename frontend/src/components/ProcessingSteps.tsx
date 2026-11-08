"use client";


import {
Check,
Loader2
} from "lucide-react";


import {motion} from "framer-motion";


const steps=[

"Image validation",

"RGB preprocessing",

"Running Ensemble Model",

"Generating Grad-CAM explanation",

"Preparing forensic report"

];



export default function ProcessingSteps({

active

}:{

active:boolean;

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

className="
rounded-3xl
border
border-white/10
bg-white/5
backdrop-blur-xl
p-8
"


>


<h2 className="
text-2xl
font-bold
mb-8
">

AI Processing Pipeline

</h2>




<div className="
space-y-6
">


{

steps.map((step,index)=>(


<div

key={step}

className="
flex
items-center
gap-5
"

>


<div

className="
h-10
w-10
rounded-full
flex
items-center
justify-center
bg-cyan-400/10
"

>


{

active && index===2

?

<Loader2

className="
text-cyan-400
animate-spin
"

/>

:

<Check

className="
text-green-400
"

/>

}


</div>



<p className="
text-lg
">

{step}

</p>


</div>


))

}



</div>


</motion.div>

)

}