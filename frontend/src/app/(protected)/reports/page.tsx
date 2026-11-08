import Sidebar from "@/components/Sidebar";

import ReportStats from "@/components/ReportStats";

import ReportTable from "@/components/ReportTable";

import ReportPreview from "@/components/ReportPreview";



export default function Reports(){


return (

<div

className="
min-h-screen
pt-32
lg:ml-[340px]
px-8
pb-20
text-white
"

>


<Sidebar/>



<h1

className="
text-5xl
font-bold
"

>

Forensic Reports

</h1>



<p

className="
mt-4
text-slate-400
text-lg
"

>

Generated AI investigation reports and evidence records

</p>



<div className="mt-12">

<ReportStats/>

</div>



<div

className="
mt-10
grid
xl:grid-cols-2
gap-10
"

>


<ReportTable/>


<ReportPreview/>


</div>



</div>


)

}