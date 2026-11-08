"use client";


import {
FileText,
ShieldAlert,
CheckCircle
} from "lucide-react";


export default function ReportStats(){


return (

<div

className="
grid
md:grid-cols-3
gap-6
"

>


<Card

icon={<FileText/>}

title="Total Reports"

value="921"

/>


<Card

icon={<ShieldAlert/>}

title="Fake Cases"

value="743"

/>


<Card

icon={<CheckCircle/>}

title="Verified Real"

value="178"

/>


</div>

)

}




function Card({

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
rounded-3xl
border
border-white/10
bg-white/5
p-7
"

>


<div

className="
text-cyan-400
"

>

{icon}

</div>



<p

className="
mt-5
text-slate-400
"

>

{title}

</p>


<h2

className="
text-4xl
font-bold
mt-2
"

>

{value}

</h2>



</div>


)

}