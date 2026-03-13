<p align="center">
<img src="https://i.postimg.cc/FFyzWBmx/Screenshot-20260311-202220-Cap-Cut.jpg" width="100%">
</p>

<p align="center">
<img src="https://i.postimg.cc/3N8Tb9Ck/Untitled-1772938586433-9-M65hnv.png" width="120">
</p>

<h1 align="center">NightGuard</h1>

<p align="center">
Next-Generation Lua Obfuscation Engine
</p>

<p align="center">
Advanced Virtual Machine • AST Obfuscation • Cryptographic Protection
</p>

---

# 🌙 About NightGuard

**NightGuard** is a modern Lua obfuscation engine designed to protect scripts against reverse engineering, static analysis and decompilation.

Built with a hybrid architecture combining **AST transformations, custom virtual machines and cryptographic layers**, NightGuard focuses on making protected code extremely difficult to analyze while keeping runtime performance stable.

NightGuard is inspired by modern commercial-grade obfuscators but built with a custom pipeline optimized for flexibility and extensibility.

---

# 🚀 Core Architecture

NightGuard uses a **multi-layer protection pipeline**.
This layered approach ensures that attackers must break multiple protection mechanisms before reaching the original logic.

---

# 🔐 Protection Layers

### AST Obfuscation

NightGuard transforms the source code before compilation.

Features include:

• Local variable renaming  
• Mixed Boolean Arithmetic (MBA) transforms  
• Opaque predicates  
• Dead code injection  
• Constant splitting  

These techniques make static analysis significantly harder.

---

### Virtual Machine

NightGuard executes protected scripts inside a **custom register-based VM**.

Features:

• Custom instruction set  
• Opcode mutation  
• Polymorphic handlers  
• State-machine dispatch  
• Bytecode virtualization  

This prevents traditional Lua decompilers from understanding the code.

---

### Cryptographic Layer

Before execution the bytecode is:
Compressed → Encrypted → Loaded by VM
NightGuard includes:

• Rolling XOR stream encryption  
• Per-script keys  
• Bytecode segmentation  
• Integrity checks  

This ensures that dumping the script memory still requires additional reversing work.

---

# 🧠 Design Goals

NightGuard is designed around three core principles:

### Security

Multiple independent layers make automated deobfuscation extremely difficult.

### Flexibility

The engine is modular and can easily integrate new protection modules.

### Polymorphism

Each build can generate a different VM layout and instruction mapping.

---

# ⚡ Feature Overview

| Feature | Status |
|-------|-------|
AST Transformations | ✔ |
Register Virtual Machine | ✔ |
Opcode Randomization | ✔ |
Bytecode Encryption | ✔ |
Compression Layer | ✔ |
Dead Code Injection | ✔ |
MBA Transform | ✔ |
Anti Debug | ✔ |

---

# 📊 Obfuscation Strategy

NightGuard focuses on combining multiple defensive layers instead of relying on a single technique.
AST Protection + Virtual Machine + Crypto Layer = Hybrid Obfuscation
This approach significantly increases the effort required for reverse engineering.

---

# 🛠 Development

NightGuard is continuously evolving with new protection techniques and optimizations.

Future improvements include:

• deeper VM polymorphism  
• instruction layout mutation  
• execution fingerprinting  
• advanced anti-tamper mechanisms  

---

# 🌌 Philosophy

> “Obfuscation should not only hide code —  
> it should reshape how the code exists.”

NightGuard aims to transform scripts into something fundamentally different from their original structure.

---

<p align="center">
Built with passion for software protection
</p>
