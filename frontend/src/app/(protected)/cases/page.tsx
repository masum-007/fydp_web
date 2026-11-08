import Sidebar from "@/components/Sidebar";


export default function Cases(){

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

Investigation Cases

</h1>


<p className="
mt-4
text-slate-400
">

Manage forensic investigation cases

</p>



<div className="
mt-10
rounded-3xl
border
border-white/10
bg-white/5
p-10
">


<h2 className="
text-2xl
font-bold
">

No Active Cases

</h2>


<p className="
text-slate-400
mt-3
">

Create a new investigation after uploading evidence.

</p>


</div>


</div>

)

}