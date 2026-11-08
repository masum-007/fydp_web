"use client";


import {
UploadCloud
} from "lucide-react";


import {
useState
} from "react";



export default function ImageUploader({

onUpload

}:{

onUpload:(file:File)=>void;

}){


const [drag,setDrag]=useState(false);



function handleFile(
file:File
){

onUpload(file);

}




return (

<div

onDragOver={(e)=>{

e.preventDefault();

setDrag(true);

}}

onDragLeave={()=>setDrag(false)}


onDrop={(e)=>{

e.preventDefault();

setDrag(false);

const file=e.dataTransfer.files[0];

if(file)
handleFile(file);

}}


className={`
relative
overflow-hidden
rounded-3xl
border-2
border-dashed
p-12
text-center
transition
duration-300

${
drag

?

"border-cyan-400 bg-cyan-400/10"

:

"border-white/20 bg-white/5"

}

`}

>
    <div

className="
absolute
inset-0
bg-gradient-to-r
from-transparent
via-cyan-400/10
to-transparent
animate-pulse
pointer-events-none
"

/>


<UploadCloud

size={55}

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
text-white
"

>

Upload Evidence Image

</h2>



<p

className="
mt-3
text-slate-400
"

>

Drag & drop suspicious image

or click browse

</p>



<input

type="file"

accept="image/*"

className="
mt-6
block
mx-auto
text-sm
text-slate-300
file:mr-4
file:rounded-xl
file:border-0
file:bg-cyan-500
file:px-5
file:py-2
file:text-white
file:font-semibold
hover:file:bg-cyan-600
"

onChange={(e)=>{

const file=e.target.files?.[0];

if(file)
handleFile(file);

}}

/>



<p

className="
mt-5
text-sm
text-slate-500
"

>

Supported formats:
PNG JPG WEBP

</p>


</div>

)


}