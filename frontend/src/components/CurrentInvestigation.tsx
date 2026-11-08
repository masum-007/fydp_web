import {
  FolderSearch,
  Image,
  Clock,
  ShieldCheck
} from "lucide-react";


export default function CurrentInvestigation(){


return (

<div

className="
rounded-3xl
border
border-cyan-400/20
bg-gradient-to-br
from-cyan-400/10
to-blue-500/10
backdrop-blur-xl
p-8
"

>


<div

className="
flex
items-center
gap-3
mb-8
"

>


<div

className="
rounded-xl
bg-cyan-400/10
p-3
text-cyan-400
"

>

<FolderSearch/>

</div>



<div>

<h2

className="
text-2xl
font-bold
"

>

Current Investigation

</h2>


<p

className="
text-slate-400
"

>

Active forensic case overview

</p>


</div>


</div>





<div

className="
grid
md:grid-cols-2
gap-6
"

>


<Info

icon={<ShieldCheck/>}

title="Case ID"

value="NE-2026-001"

/>


<Info

icon={<Image/>}

title="Evidence Files"

value="0 Images"

/>


<Info

icon={<Clock/>}

title="Last Analysis"

value="Waiting"

/>


<Info

icon={<FolderSearch/>}

title="Status"

value="Ready"

/>


</div>



</div>


)

}





function Info({

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
bg-black/20
p-5
flex
items-center
gap-4
"

>


<div

className="
text-cyan-400
"

>

{icon}

</div>



<div>

<p

className="
text-slate-400
text-sm
"

>

{title}

</p>


<h3

className="
font-semibold
mt-1
"

>

{value}

</h3>


</div>


</div>


)

}