import Sidebar from "@/components/Sidebar";


export default function ModelAnalytics(){

return (

<div

className="
min-h-screen
pt-32
lg:ml-[340px]
px-8
text-white
"

>


<Sidebar/>


<h1 className="
text-5xl
font-bold
">

Model Analytics

</h1>


<p className="
mt-4
text-slate-400
">

Deep learning model performance monitoring

</p>


<div className="
mt-10
rounded-3xl
bg-white/5
border
border-white/10
p-10
">


<h2 className="
text-2xl
font-bold
">

NeuralEdge Ensemble Model

</h2>


<div className="
mt-6
space-y-3
">

<p>
Accuracy: 90.96%
</p>

<p>
ROC-AUC: 0.9621
</p>

<p>
F1 Score: 0.9085
</p>


</div>


</div>


</div>

)

}