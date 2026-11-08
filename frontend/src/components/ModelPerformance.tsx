export default function ModelPerformance(){


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
mb-6
"

>

Ensemble Model Performance

</h2>



<div

className="
grid
md:grid-cols-3
gap-6
"

>


<Item
name="Accuracy"
value="90.96%"
/>


<Item
name="ROC-AUC"
value="0.9621"
/>


<Item
name="F1 Score"
value="0.9085"
/>


</div>



</div>


)


}



function Item({

name,
value

}:{

name:string;
value:string;

}){


return (

<div

className="
rounded-2xl
bg-black/20
p-6
text-center
"

>


<p className="text-slate-400">

{name}

</p>


<h3 className="text-3xl font-bold mt-3">

{value}

</h3>


</div>


)

}