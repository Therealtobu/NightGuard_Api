async function obfuscate(){

  const code =
    document.getElementById("input").value

  const res = await fetch(
    "https://nightguard.onrender.com/api/obfuscate",
    {
      method:"POST",
      headers:{
        "Content-Type":"application/json"
      },
      body:JSON.stringify({code:code})
    }
  )

  const data = await res.json()

  document.getElementById("output").value =
    data.result
}
