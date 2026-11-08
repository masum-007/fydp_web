"use client";


import {
useState
} from "react";


import Sidebar from "@/components/Sidebar";

import ImageUploader from "@/components/ImageUploader";

import ImagePreview from "@/components/ImagePreview";

import ProcessingSteps from "@/components/ProcessingSteps";

import AnalysisResult from "@/components/AnalysisResult";

import ExplainabilityCard from "@/components/ExplainabilityCard";

import ForensicResult from "@/components/ForensicResult";
import GradCAMViewer from "@/components/GradCAMViewer";
import FeatureImportance from "@/components/FeatureImportance";
import ReportButton from "@/components/ReportButton";


export default function Analyze(){


const [image,setImage]=useState<string|null>(null);


const [processing,setProcessing]=useState(false);



function upload(file:File){


setImage(
URL.createObjectURL(file)
);


setProcessing(true);


}



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
text-white
"

>

Analyze Evidence

</h1>


<p

className="
text-slate-400
mt-4
text-lg
"

>
Upload suspicious images for AI forensic analysis

</p>




<div className="
mt-10
max-w-5xl
space-y-10
">


<ImageUploader

onUpload={upload}

/>



<ImagePreview

image={image}

/>



<ProcessingSteps

active={processing}

/>



{
processing &&

<>

<ForensicResult/>


<GradCAMViewer/>


<FeatureImportance/>


<div className="
flex
justify-center
py-10
">

<ReportButton/>

</div>

</>

}



</div>


</div>

)

}