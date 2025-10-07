let chatHistory = [];
let threadId = null;

// ==================== SEND MESSAGE ====================
async function sendMessage() {
    const userInput = document.getElementById('user-input');
    const message = userInput.value.trim();

    if (message) {
        // Add user message immediately
        addMessageToChat('user', message);

        // Small delay before clearing input (prevents flicker)
        setTimeout(() => { userInput.value = ''; }, 100);

        // Temporary placeholder while waiting
        const thinkingMsg = addMessageToChat('bot', '👨‍🍳 Chef CTS is thinking...');
        let botMessageElement = thinkingMsg; // Reference to update later

        try {
            const response = await fetch('http://127.0.0.1:8000/chef_bot.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    threadId: threadId
                })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Backend result:', result);

                if (result.threadId) threadId = result.threadId;

                // Handle both string and object message types
                const botReply =
                    typeof result.message === "string"
                        ? result.message
                        : result.message?.content || "";

                if (botReply && botReply.trim().length > 0) {
                    // Update placeholder instead of adding new
                    botMessageElement.textContent = botReply;
                } else {
                    botMessageElement.textContent = "Hmm… Chef CTS didn’t send any text back.";
                }
            } else {
                throw new Error('Server response was not ok.');
            }
        } catch (error) {
            console.error('Error:', error);
            botMessageElement.textContent = 'Sorry, I encountered an error. Please try again.';
        }
    }
}

// ==================== ADD MESSAGE TO CHAT ====================
function addMessageToChat(sender, message) {
    if (!message) return; // Prevent empty messages

    const chatOutput = document.getElementById('chat-output');
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.textContent = message;

    // Append new message instead of replacing old ones
    chatOutput.appendChild(messageElement);

    // Auto-scroll to bottom
    chatOutput.scrollTop = chatOutput.scrollHeight;

    // Save to local chat history
    chatHistory.push({
        role: sender === 'user' ? 'user' : 'assistant',
        content: message
    });

    // Return element so we can modify it later (for live updates)
    return messageElement;
}

// ==================== SEND ON ENTER ====================
document.getElementById('user-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// ==================== INITIAL MESSAGE ====================
addMessageToChat('bot', '👋 Hello! I am Chef CTS. How can I assist you with your culinary questions today?');
