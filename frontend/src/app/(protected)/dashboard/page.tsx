import Sidebar from "@/components/Sidebar";
import StatsCard from "@/components/StatsCard";
import CaseTable from "@/components/CaseTable";
import ModelPerformance from "@/components/ModelPerformance";
import SystemStatus from "@/components/SystemStatus";
import ModelComparison from "@/components/ModelComparison";
import ActivityTimeline from "@/components/ActivityTimeline";
import QuickActions from "@/components/QuickActions";
import CurrentInvestigation from "@/components/CurrentInvestigation";

import {
FileSearch,
ShieldAlert,
CheckCircle,
FileText
} from "lucide-react";



export default function Dashboard(){


return (

<div

className="
min-h-screen
pt-32
"


>


<Sidebar/>


<main

className="
lg:ml-[340px]
px-8
pt-6
pb-20
text-white
max-w-[1600px]
"
>


<h1

className="
text-5xl
font-bold
"

>

Welcome back,
<span className="text-cyan-400">
 Investigator
</span>

</h1>


<p

className="
text-slate-400
mt-4
text-lg
"

>

AI-powered forensic workspace for deepfake detection,
explainability analysis and investigation management.

</p>



<div

className="
mt-6
inline-flex
items-center
gap-3
rounded-full
border
border-green-400/20
bg-green-400/10
px-5
py-2
text-green-300
"

>

<span
className="
h-3
w-3
rounded-full
bg-green-400
animate-pulse
"
/>

NeuralEdge AI Engine Online

</div>




<div

className="
grid
sm:grid-cols-2
xl:grid-cols-4
gap-6
mt-12
"

>


<StatsCard

title="Total Analyses"

value="1248"

icon={<FileSearch/>}

/>


<StatsCard

title="Fake Detected"

value="743"

icon={<ShieldAlert/>}

/>


<StatsCard

title="Real Images"

value="505"

icon={<CheckCircle/>}

/>


<StatsCard

title="Reports"

value="921"

icon={<FileText/>}

/>



</div>

<div className="mt-10">

<CurrentInvestigation/>

</div>

<div className="mt-10">

<ModelPerformance/>
<div className="mt-10">

<SystemStatus/>

</div>



<div className="
mt-10
grid
xl:grid-cols-2
gap-10
">


<ModelComparison/>


<ActivityTimeline/>


</div>



<div className="mt-10">

<QuickActions/>

</div>
</div>



<div className="mt-10">

<CaseTable/>

</div>



</main>


</div>


)


}