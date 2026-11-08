"use client";


import {
ShieldAlert
} from "lucide-react";


import {motion} from "framer-motion";


export default function AnalysisResult(){


return (

<motion.div

initial={{
opacity:0,
scale:.95
}}

animate={{
opacity:1,
scale:1
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

Analysis Result

</h2>


</div>



<div className="
mt-8
text-center
">


<p className="
text-slate-400
">

Prediction

</p>


<h1 className="
text-6xl
font-bold
text-red-400
mt-3
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


<Card
title="Confidence"
value="97.6%"
/>


<Card
title="Threshold"
value="0.56"
/>


<Card
title="Model"
value="Ensemble"
/>


</div>


</motion.div>


)

}



function Card({

title,
value

}:{

title:string;
value:string;

}){


return (

<div

className="
rounded-2xl
bg-black/30
p-5
text-center
"

>

<p className="
text-slate-400
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