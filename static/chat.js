const socket = io();

const input = document.getElementById('message-input');
const chatBox = document.getElementById('chat-box');

input.addEventListener('keypress', function(e) {
  if (e.key === 'Enter' && input.value.trim() !== '') {
    socket.emit('message', { text: input.value, sender: nickname });
    input.value = '';
  }
});

socket.on('message', function(data) {
  const msg = document.createElement('p');
  msg.innerHTML = `<strong>${data.sender}:</strong> ${data.text}`;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
});

