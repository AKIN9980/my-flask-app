const socket = io();
let username = localStorage.getItem("nickname");

if (!username) {
  username = "user_" + Math.floor(Math.random() * 10000);
  localStorage.setItem("nickname", username);
}

const form = document.getElementById("form");
const input = document.getElementById("input");
const messages = document.getElementById("messages");

form.addEventListener("submit", function(e) {
  e.preventDefault();
  if (input.value) {
    socket.emit("message", {
      username: username,
      message: input.value
    });
    input.value = "";
  }
});

socket.on("message", function(data) {
  const item = document.createElement("li");
  item.textContent = `${data.username}: ${data.message}`;
  messages.appendChild(item);
  window.scrollTo(0, document.body.scrollHeight);
});

