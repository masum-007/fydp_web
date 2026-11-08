"use client";


import {
useRouter
} from "next/navigation";


import {
useAuth
} from "./AuthProvider";



export default function LoginForm(){


const {
login

}=useAuth();


const router=useRouter();



function handleLogin(){

login();

router.push("/dashboard");

}



return (

<div

className="
w-full
max-w-md
rounded-3xl
border
border-white/10
bg-white/5
backdrop-blur-xl
p-10
"

>


<h1

className="
text-3xl
font-bold
text-white
"

>

Investigator Login

</h1>



<p

className="
text-slate-400
mt-3
"

>

Access NeuralEdge AI forensic workspace

</p>




<input

placeholder="Email"

className="
mt-8
w-full
rounded-xl
bg-black/20
border
border-white/10
p-4
text-white
"

/>



<input

placeholder="Password"

type="password"

className="
mt-4
w-full
rounded-xl
bg-black/20
border
border-white/10
p-4
text-white
"

/>



<button

onClick={handleLogin}

className="
mt-8
w-full
rounded-xl
bg-gradient-to-r
from-cyan-500
to-blue-600
py-4
font-semibold
"

>

Login

</button>



</div>

)

}