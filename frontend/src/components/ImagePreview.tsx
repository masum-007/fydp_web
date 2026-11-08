"use client";


import {motion} from "framer-motion";
import {
Image as ImageIcon,
FileImage
} from "lucide-react";


export default function ImagePreview({

image

}:{

image:string|null;

}){


if(!image)
return null;



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
mb-6
">


<ImageIcon
className="
text-cyan-400
"
/>


<h2 className="
text-2xl
font-bold
">

Evidence Preview

</h2>


</div>




<div className="
grid
md:grid-cols-2
gap-8
items-center
">


<img

src={image}

className="
rounded-2xl
max-h-[450px]
mx-auto
border
border-white/10
"

/>



<div

className="
space-y-5
"

>


<Info
label="Evidence Type"
value="Image"
/>


<Info
label="AI Processing"
value="Ready"
/>


<Info
label="Analysis Mode"
value="Deepfake Detection"
/>



</div>


</div>



</motion.div>


)

}



function Info({

label,
value

}:{

label:string;
value:string;

}){


return (

<div

className="
rounded-xl
bg-black/20
p-4
"

>


<p className="
text-slate-400
text-sm
">

{label}

</p>


<p className="
font-semibold
mt-1
">

{value}

</p>


</div>

)

}