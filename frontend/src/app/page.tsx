import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

import {
  Brain,
  ShieldCheck,
  FileSearch,
  ScanFace,
  Database,
  Sparkles
} from "lucide-react";


export default function Home() {


return (

<main className="
relative
min-h-screen
bg-[#050816]
text-white
overflow-hidden
">


<Navbar />
<div className="
absolute
top-40
left-1/2
-translate-x-1/2
w-[600px]
h-[600px]
bg-cyan-500/20
blur-[140px]
rounded-full
pointer-events-none
">
</div>


{/* HERO SECTION */}

<section className="
pt-52
px-6
">


<div className="
max-w-6xl
mx-auto
text-center
">


<div className="
inline-flex
items-center
gap-2
rounded-full
border
border-cyan-400/20
bg-cyan-400/10
px-5
py-2
text-cyan-300
text-sm
"
>

<Sparkles size={18}/>

AI Forensic Intelligence Platform

</div>




<h1 className="
mt-10
text-5xl
md:text-7xl
font-extrabold
tracking-tight
leading-tight
text-white
">


Explainable AI Powered


<br/>


<span className="
bg-gradient-to-r
from-cyan-400
to-blue-500
bg-clip-text
text-transparent
">

Deepfake Detection

</span>


</h1>




<p className="
mt-8
mx-auto
max-w-3xl
text-lg
md:text-xl
text-slate-400
leading-relaxed
">


NeuralEdge AI combines deep learning,
computer vision and Explainable AI to
detect manipulated images and generate
forensic-level insights.

</p>




<div className="
mt-10
flex
justify-center
gap-5
flex-wrap
">


<a

href="/detect"

className="
rounded-xl
bg-gradient-to-r
from-cyan-500
to-blue-600
px-8
py-4
font-semibold
text-lg
shadow-lg
hover:scale-105
transition
"

>

Try Detection

</a>



<button

className="
rounded-xl
border
border-white/20
bg-white/5
px-8
py-4
font-semibold
text-lg
hover:bg-white/10
transition
"

>

Explore Technology

</button>



</div>



</div>


</section>





{/* FEATURES */}


<section className="
mt-32
px-6
">


<div className="
max-w-7xl
mx-auto
text-center
">


<h2 className="
text-4xl
font-bold
"
>

Advanced AI Capabilities

</h2>



<p className="
mt-4
text-slate-400
text-lg
">

Built for digital forensic investigation

</p>




<div className="
mt-14
grid
grid-cols-1
md:grid-cols-2
lg:grid-cols-3
gap-8
"
>


<Card

icon={<Brain/>}

title="Deep Learning Engine"

text="MobileNetV2, ResNet50V2, Xception and ensemble intelligence"

/>



<Card

icon={<ShieldCheck/>}

title="Explainable AI"

text="Grad-CAM visualization with future SHAP and LIME analysis"

/>




<Card

icon={<FileSearch/>}

title="Forensic Reports"

text="Generate investigation-ready evidence reports"

/>




<Card

icon={<ScanFace/>}

title="Deepfake Analysis"

text="Detect manipulated facial images with confidence scoring"

/>



<Card

icon={<Database/>}

title="Evidence Management"

text="Secure investigation case organization"

/>




<Card

icon={<Sparkles/>}

title="Future Ready"

text="Expandable forensic AI architecture"

/>



</div>


</div>


</section>





{/* TECHNOLOGY SECTION */}



<section className="
mt-32
pb-20
px-6
">


<div className="
max-w-5xl
mx-auto
text-center
">


<h2 className="
text-3xl
font-bold
">

Powered By

</h2>



<div className="
mt-8
flex
justify-center
flex-wrap
gap-4
">


{
[
"TensorFlow",
"MobileNetV2",
"ResNet50V2",
"Xception",
"Grad-CAM",
"SHAP"
].map((tech)=>(


<div
key={tech}

className="
rounded-xl
border
border-white/10
bg-white/5
px-6
py-3
text-slate-300
backdrop-blur
"
>

{tech}

</div>


))
}


</div>


</div>


</section>




<Footer/>


</main>

)

}





function Card({

icon,
title,
text

}:{

icon:React.ReactNode;

title:string;

text:string;

}){


return (

<div className="
group
rounded-3xl
border
border-white/10
bg-white/5
p-8
text-left
backdrop-blur-xl
transition
hover:-translate-y-2
hover:border-cyan-400/40
"
>


<div className="
mb-6
text-cyan-400
"
>

{icon}

</div>



<h3 className="
text-2xl
font-bold
"
>

{title}

</h3>



<p className="
mt-4
text-slate-400
leading-relaxed
"
>

{text}

</p>



</div>


)


}