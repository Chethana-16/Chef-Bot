<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Load API key from a separate, non-public file
$config = require_once 'config.php';
$api_key = $config['openai_api_key'];
$assistant_id = $config['assistant_id'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    $message = $input['message'] ?? '';
    $threadId = $input['threadId'] ?? null;

    if (!empty($message)) {
        $base_url = 'https://api.openai.com/v1/';

        try {
            // Create or retrieve thread
            if (!$threadId) {
                $threadId = createThread($base_url, $api_key);
            }

            // Add message to thread
            addMessageToThread($base_url, $api_key, $threadId, $message);

            // Run the assistant
            $run_id = runAssistant($base_url, $api_key, $threadId, $assistant_id);

            // Wait for completion and get messages
            $assistant_message = getAssistantResponse($base_url, $api_key, $threadId, $run_id);

            echo json_encode(['threadId' => $threadId, 'message' => $assistant_message]);
        } catch (Exception $e) {
            error_log('Chef Bot Error: ' . $e->getMessage());
            echo json_encode(['error' => 'An error occurred. Please try again.']);
        }
    } else {
        echo json_encode(['error' => 'Please provide a message.']);
    }
} else {
    echo json_encode(['error' => 'Invalid request method.']);
}

function createThread($base_url, $api_key) {
    $response = makeApiCall($base_url . 'threads', $api_key, 'POST');
    if (!isset($response['id'])) {
        throw new Exception('Failed to create thread');
    }
    return $response['id'];
}

function addMessageToThread($base_url, $api_key, $threadId, $message) {
    $data = [
        'role' => 'user',
        'content' => $message
    ];
    $response = makeApiCall($base_url . "threads/{$threadId}/messages", $api_key, 'POST', $data);
    if (!isset($response['id'])) {
        throw new Exception('Failed to add message to thread');
    }
}

function runAssistant($base_url, $api_key, $threadId, $assistant_id) {
    $data = [
        'assistant_id' => $assistant_id
    ];
    $response = makeApiCall($base_url . "threads/{$threadId}/runs", $api_key, 'POST', $data);
    if (!isset($response['id'])) {
        throw new Exception('Failed to run assistant');
    }
    return $response['id'];
}

function getAssistantResponse($base_url, $api_key, $threadId, $run_id) {
    $timeout = time() + 30; // 30 second timeout
    do {
        if (time() > $timeout) {
            throw new Exception('Timeout waiting for assistant response');
        }
        sleep(1);
        $run_status = makeApiCall($base_url . "threads/{$threadId}/runs/{$run_id}", $api_key, 'GET');
    } while ($run_status['status'] !== 'completed' && $run_status['status'] !== 'failed');

    if ($run_status['status'] === 'failed') {
        throw new Exception('Assistant run failed');
    }

    $messages = makeApiCall($base_url . "threads/{$threadId}/messages", $api_key, 'GET');
    if (!isset($messages['data'][0]['content'][0]['text']['value'])) {
        throw new Exception('No message content found');
    }
    return $messages['data'][0]['content'][0]['text']['value'];
}

function makeApiCall($url, $api_key, $method, $data = null) {
    $headers = [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $api_key,
        'OpenAI-Beta: assistants=v1'
    ];

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    if ($method === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);
        if ($data) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        }
    }

    $response = curl_exec($ch);
    $http_status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    
    if (curl_errno($ch)) {
        throw new Exception('Curl error: ' . curl_error($ch));
    }
    curl_close($ch);

    $decoded_response = json_decode($response, true);
    
    if ($http_status >= 400) {
        throw new Exception('API error: ' . ($decoded_response['error']['message'] ?? 'Unknown error'));
    }

    return $decoded_response;
}
?>