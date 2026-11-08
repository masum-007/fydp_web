import "./globals.css";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import Navbar from "@/components/Navbar";

import {
AuthProvider
} from "@/components/auth/AuthProvider";

const inter = Inter({
  subsets: ["latin"],
});


export const metadata = {

  title:
    "NeuralEdge AI | Explainable Deepfake Detection",

  description:
    "NeuralEdge AI - Explainable deepfake detection and digital forensic intelligence platform",

};



export default function RootLayout({

  children,

}: Readonly<{

  children: React.ReactNode;

}>) {


return (

<html lang="en">


<body
className={`
${inter.className}
bg-[#050816]
text-white
`}
>


<div className="background-grid"></div>


<AuthProvider>

<Navbar/>

{children}

</AuthProvider>



<Toaster

position="top-right"

/>


</body>


</html>

);

}