let chatHistory = [];
let threadId = null;

async function sendMessage() {
    const userInput = document.getElementById('user-input');
    const chatOutput = document.getElementById('chat-output');
    const message = userInput.value.trim();

    if (message) {
        // Add user message to chat
        addMessageToChat('user', message);
        userInput.value = '';

        // Send message to server
        try {
            const response = await fetch('http://127.0.0.1:8000/chef_bot.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    threadId: threadId
                })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.threadId) {
                    threadId = result.threadId;
                }
                if (result.message) {
                    addMessageToChat('bot', result.message);
                }
            } else {
                throw new Error('Server response was not ok.');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessageToChat('bot', 'Sorry, I encountered an error. Please try again.');
        }
    }
}

function addMessageToChat(sender, message) {
    const chatOutput = document.getElementById('chat-output');
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.textContent = message;
    chatOutput.appendChild(messageElement);
    chatOutput.scrollTop = chatOutput.scrollHeight;

    // Add to chat history
    chatHistory.push({ role: sender === 'user' ? 'user' : 'assistant', content: message });
}

// Allow sending message with Enter key
document.getElementById('user-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Initial bot message
addMessageToChat('bot', 'Hello! I am Chef Bot. How can I assist you with your culinary questions today?');