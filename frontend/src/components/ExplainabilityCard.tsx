export default function ExplainabilityCard(){


return (

<div

className="
rounded-3xl
border
border-white/10
bg-white/5
p-8
"

>


<h2

className="
text-2xl
font-bold
"

>

Explainable AI Evidence

</h2>



<div

className="
grid
md:grid-cols-2
gap-8
mt-8
"

>


<div

className="
h-64
rounded-2xl
bg-black/30
flex
items-center
justify-center
text-slate-400
"

>

Original Image

</div>



<div

className="
h-64
rounded-2xl
bg-black/30
flex
items-center
justify-center
text-cyan-400
"

>

Grad-CAM Heatmap

</div>


</div>


</div>


)

}