# 🚀 Social Media Web Application

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3-lightgrey)
![Socket.IO](https://img.shields.io/badge/Socket.IO-WebSocket-brightgreen)
![SQLite](https://img.shields.io/badge/Database-SQLite3-yellow)
![License](https://img.shields.io/badge/License-MIT-blue)

A full-stack real-time social media web app built with **Flask** and **Socket.IO**, featuring secure user auth, friend requests, private chats, media uploads, and a modern responsive UI — all deployed on **Render.com**.

## 🔗 Live Demo

👉 **[Try It Here](https://social-media-webapp-8qbm.onrender.com/login)**  
(*Give it a few seconds to wake up if inactive*)

---

## 🛠 Tech Stack

- **Backend:** Python (Flask), Flask-SocketIO
- **Frontend:** HTML5, CSS3, Bootstrap 5
- **Database:** SQLite3
- **Security:** Passlib (password hashing), Flask session handling
- **Real-Time:** WebSockets with Socket.IO
- **Deployment:** Render.com

---

## ⚙️ Core Features

- 🔐 **User Authentication** with encrypted password storage  
- 📁 **Media Uploads:** Upload and view images, videos, audio, and documents (up to 500MB)  
- 🧑‍🤝‍🧑 **Friend System:** Send, accept, reject, or remove friend requests  
- 📬 **Real-Time Chat:** One-to-one private messaging via WebSockets  
- 👤 **Profile Management:** Manage profile picture, email, and more  
- 🔍 **Live User Search:** Instantly search for users and connect  
- 🌓 **Responsive UI:** Clean Bootstrap layout with dark mode toggle  
- 🧱 **Persistent Storage:** Efficient relational design using SQLite3

---

## 💡 Project Goals

To design and implement a **modular, scalable, and secure full-stack app** with:
- Real-time communication capabilities
- Media-rich content handling
- Production-ready structure and deployment
- RESTful and WebSocket hybrid integration

---

## 🎯 Highlights & Architecture

- ✅ **Authentication:** PBKDF2 hashed passwords using Passlib  
- ✅ **Session Management:** Flask sessions + secure login/logout flow  
- ✅ **Real-Time Engine:** Flask-SocketIO using eventlet for scalable WebSocket handling  
- ✅ **Modular Codebase:** Clear separation of logic, routes, and database operations  
- ✅ **File Security:** `secure_filename`, MIME validation, unique UUID storage paths  
- ✅ **Media Preview & Download:** Preview images, videos, or play audio directly  
- ✅ **Friendship Logic:** Mutual relationship tracking and request feed  
- ✅ **UI/UX:** Bootstrap-powered, responsive across devices with modern UI controls  

---

## 📂 Project Structure

📁 Social_Media_Webapp
/app.py
/requirements.txt

---

## 🚀 Deployment

This app is deployed live via [Render](https://render.com), configured with:
- Gunicorn + Eventlet for WebSocket support
- Persistent SQLite storage
- Secure environment variables & production WSGI setup


## 🔗 Once Again, Try It Live:
👉 [https://social-media-webapp-8qbm.onrender.com/login](https://social-media-webapp-8qbm.onrender.com/login)
