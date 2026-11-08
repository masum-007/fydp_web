"use client";


import {
useState
} from "react";


import {
UploadCloud,
ShieldCheck,
AlertTriangle
} from "lucide-react";



export default function Detect(){


const [image,setImage]=useState<string|null>(null);

const [analyzed,setAnalyzed]=useState(false);



function upload(file:File){


setImage(
URL.createObjectURL(file)
);


setAnalyzed(false);

}



function analyze(){


setAnalyzed(true);

}



return (

<div

className="
min-h-screen
pt-36
px-6
text-white
"

>


<div

className="
max-w-5xl
mx-auto
text-center
"

>


<div

className="
inline-flex
items-center
gap-2
rounded-full
bg-cyan-400/10
border
border-cyan-400/20
px-5
py-2
text-cyan-300
"

>


<ShieldCheck size={18}/>

Quick Deepfake Detection

</div>




<h1

className="
mt-10
text-5xl
font-bold
"

>


Check Image Authenticity


</h1>



<p

className="
mt-5
text-lg
text-slate-400
"

>

Upload an image to receive an AI-based
deepfake detection result.

</p>





<div

className="
mt-12
rounded-3xl
border
border-white/10
bg-white/5
backdrop-blur-xl
p-10
"

>


<UploadCloud

size={50}

className="
mx-auto
text-cyan-400
"

/>



<h2

className="
mt-6
text-2xl
font-bold
"

>

Upload Image

</h2>




<input

type="file"

accept="image/*"

className="
mt-6
mx-auto
block
text-slate-300
file:bg-cyan-500
file:text-white
file:border-0
file:rounded-xl
file:px-5
file:py-2
"

onChange={(e)=>{

const file=e.target.files?.[0];

if(file)
upload(file);

}}


/>



{

image &&

<img

src={image}

className="
mt-8
mx-auto
rounded-2xl
max-h-[350px]
"

/>

}




{

image && !analyzed &&

<button

onClick={analyze}

className="
mt-8
rounded-xl
bg-gradient-to-r
from-cyan-500
to-blue-600
px-10
py-4
font-semibold
"

>

Analyze Image

</button>

}



</div>





{

analyzed &&

<Result/>

}



</div>


</div>

)

}





function Result(){


return (

<div

className="
mt-10
rounded-3xl
border
border-red-400/20
bg-red-400/5
p-10
"

>


<AlertTriangle

className="
mx-auto
text-red-400
"

size={45}

/>



<h2

className="
mt-5
text-4xl
font-bold
text-red-400
"

>

FAKE IMAGE

</h2>



<div

className="
grid
md:grid-cols-2
gap-5
mt-8
"

>


<Card

title="Confidence"

value="94.5%"

/>


<Card

title="Model"

value="NeuralEdge Ensemble"

/>



</div>




<div

className="
mt-10
rounded-xl
bg-black/20
p-6
"

>


<p

className="
text-slate-300
"

>

Want full forensic analysis?

</p>


<p

className="
text-slate-400
mt-2
"

>

Create an investigator account to access:

</p>


<ul

className="
mt-4
text-left
space-y-2
text-slate-300
"

>

<li>
✓ Case management
</li>

<li>
✓ Grad-CAM explanations
</li>

<li>
✓ PDF forensic reports
</li>


</ul>


</div>



</div>

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
rounded-xl
bg-black/20
p-5
"

>


<p className="text-slate-400">

{title}

</p>


<h3

className="
text-2xl
font-bold
mt-2
"

>

{value}

</h3>


</div>


)

}