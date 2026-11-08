"use client";


import {
createContext,
useContext,
useState
} from "react";


type User = {

name:string;

role:"guest" | "investigator";

} | null;



type AuthContextType = {

user: User;

login:()=>void;

logout:()=>void;

};



const AuthContext = createContext<AuthContextType | undefined>(
undefined
);



export function AuthProvider({

children

}:{

children:React.ReactNode;

}){


const [user,setUser]=useState<User>({

name:"Guest",

role:"guest"

});



function login(){

setUser({

name:"Investigator",

role:"investigator"

});

}



function logout(){

setUser({

name:"Guest",

role:"guest"

});

}



return (

<AuthContext.Provider

value={{

user,

login,

logout

}}

>


{children}


</AuthContext.Provider>

)

}





export function useAuth(){


const context = useContext(AuthContext);



if(!context){

throw new Error(
"useAuth must be used inside AuthProvider"
);

}


return context;


}