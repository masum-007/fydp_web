"use client";


const reports=[

{
id:"NE-2026-001",
result:"FAKE",
confidence:"97.6%",
date:"Today"
},

{
id:"NE-2026-002",
result:"REAL",
confidence:"98.1%",
date:"Today"
},

{
id:"NE-2026-003",
result:"FAKE",
confidence:"91.4%",
date:"Yesterday"
}

];



export default function ReportTable(){


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
mb-8
"

>

Investigation Reports

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
Case ID
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
reports.map((report)=>(


<tr

key={report.id}

className="
border-b
border-white/10
text-center
"

>


<td className="
py-5
text-left
">

{report.id}

</td>



<td

className={

report.result==="FAKE"

?

"text-red-400"

:

"text-green-400"

}

>

{report.result}

</td>




<td>

{report.confidence}

</td>



<td>

{report.date}

</td>


</tr>


))

}



</tbody>


</table>



</div>

)

}