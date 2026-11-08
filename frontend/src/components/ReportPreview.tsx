"use client";


import {

FileDown,
ShieldCheck

} from "lucide-react";



export default function ReportPreview(){


return (

<div

className="
rounded-3xl
border
border-cyan-400/20
bg-cyan-400/5
p-8
"

>


<div

className="
flex
items-center
gap-4
"

>


<ShieldCheck

className="
text-cyan-400
"

/>


<h2

className="
text-2xl
font-bold
"

>

Forensic Report Preview

</h2>


</div>



<div

className="
mt-8
space-y-5
"

>


<Item
title="Case ID"
value="NE-2026-001"
/>


<Item
title="Prediction"
value="FAKE IMAGE"
/>


<Item
title="Model"
value="Ensemble"
/>


<Item
title="Explainability"
value="Grad-CAM Generated"
/>


</div>



<button

className="
mt-8
flex
items-center
gap-3
rounded-xl
bg-gradient-to-r
from-cyan-500
to-blue-600
px-7
py-3
font-semibold
"

>


<FileDown/>

Download PDF

</button>



</div>


)

}



function Item({

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
p-4
"

>

<p className="text-slate-400">

{title}

</p>


<p className="font-semibold mt-1">

{value}

</p>


</div>


)

}