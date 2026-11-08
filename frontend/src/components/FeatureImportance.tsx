export default function FeatureImportance(){


const features=[

{
name:"Facial Artifact Region",
score:"92%"
},

{
name:"Texture Inconsistency",
score:"87%"
},

{
name:"Compression Pattern",
score:"81%"
}

];


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


<h2 className="
text-2xl
font-bold
">

Feature Importance

</h2>



<div className="
mt-8
space-y-5
">


{
features.map(item=>(


<div key={item.name}>


<div className="
flex
justify-between
mb-2
">

<span>
{item.name}
</span>


<span className="
text-cyan-400
">

{item.score}

</span>


</div>


<div className="
h-3
rounded-full
bg-black/40
">

<div

className="
h-full
rounded-full
bg-gradient-to-r
from-cyan-400
to-blue-500
"

style={{
width:item.score
}}

/>


</div>


</div>


))

}


</div>


</div>


)

}