const cases=[

{
id:"NE-001",
result:"Fake",
confidence:"97.6%",
date:"Today"
},

{
id:"NE-002",
result:"Real",
confidence:"98.1%",
date:"Today"
},

{
id:"NE-003",
result:"Fake",
confidence:"91.4%",
date:"Yesterday"
}


];



export default function CaseTable(){


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

Recent Investigations

</h2>



<table

className="
w-full
"

>


<thead>

<tr

className="
text-slate-400
border-b
border-white/10
"

>

<th className="text-left py-4">
Case
</th>

<th>
Result
</th>

<th>
Confidence
</th>

<th>
Date
</th>


</tr>

</thead>



<tbody>


{
cases.map((item)=>(


<tr

key={item.id}

className="
border-b
border-white/5
text-center
"

>


<td className="py-5 text-left">

{item.id}

</td>


<td

className={

item.result==="Fake"

?

"text-red-400"

:

"text-green-400"

}

>

{item.result}

</td>


<td>

{item.confidence}

</td>


<td>

{item.date}

</td>


</tr>


))

}


</tbody>


</table>


</div>


)


}