"use client";


import {
Award,
BarChart3
} from "lucide-react";

import {motion} from "framer-motion";


const models=[

{
name:"Ensemble",
score:90.96,
best:true
},

{
name:"MobileNetV2",
score:89.43
},

{
name:"Xception",
score:88.35
},

{
name:"ResNet50V2",
score:88.04
}

];



export default function ModelComparison(){


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


<div className="
flex
items-center
gap-3
mb-8
">


<BarChart3
className="text-cyan-400"
/>


<h2 className="
text-2xl
font-bold
">

Model Performance Analytics

</h2>


</div>




<div className="
space-y-7
">


{
models.map((model)=>(


<div
key={model.name}
>


<div className="
flex
justify-between
mb-2
">


<div className="
flex
items-center
gap-3
">

<span>

{model.name}

</span>


{
model.best &&

<Award
size={18}
className="text-yellow-400"
/>

}


</div>



<span className="
text-cyan-400
font-semibold
">

{model.score}%

</span>


</div>




<div className="
h-3
rounded-full
bg-black/40
overflow-hidden
">


<motion.div

initial={{
width:0
}}

animate={{
width:`${model.score}%`
}}

transition={{
duration:1
}}

className="
h-full
rounded-full
bg-gradient-to-r
from-cyan-400
to-blue-500
"

/>


</div>



</div>


))

}


</div>



<div className="
mt-8
rounded-2xl
bg-black/20
p-5
text-sm
text-slate-400
">


Evaluation Dataset:

<span className="text-white">

RedFace Benchmark

</span>


<br/>


Primary Metric:

<span className="text-white">

Accuracy

</span>


</div>



</motion.div>


)

}