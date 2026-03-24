#include "networking/websocketclient.h"

namespace aegis {

WebSocketClient::WebSocketClient() = default;
WebSocketClient::~WebSocketClient() = default;

bool WebSocketClient::connect(const std::string& url) {
    url_ = url;
    set_state(ConnectionState::Connecting);
    // Would use libwebsockets in production
    return true;
}

void WebSocketClient::disconnect() {
    set_state(ConnectionState::Disconnected);
}

bool WebSocketClient::send_json(const std::string& json) {
    if (!is_connected()) return false;
    // Would send via WebSocket
    return true;
}

bool WebSocketClient::send_binary(const uint8_t* data, size_t size) {
    if (!is_connected()) return false;
    return true;
}

void WebSocketClient::set_message_callback(MessageCallback callback) {
    message_callback_ = callback;
}

void WebSocketClient::set_state_callback(StateCallback callback) {
    state_callback_ = callback;
}

void WebSocketClient::process_messages() {
    std::lock_guard<std::mutex> lock(message_queue_mutex_);
    while (!message_queue_.empty()) {
        auto msg = message_queue_.front();
        message_queue_.pop();
        if (message_callback_) {
            message_callback_(msg);
        }
    }
}

std::string WebSocketClient::get_last_error() const {
    return last_error_;
}

void WebSocketClient::set_state(ConnectionState state) {
    state_.store(state);
    if (state_callback_) {
        state_callback_(state);
    }
}

void WebSocketClient::on_message_received(const WebSocketMessage& msg) {
    std::lock_guard<std::mutex> lock(message_queue_mutex_);
    message_queue_.push(msg);
}

NetworkManager::NetworkManager() = default;
NetworkManager::~NetworkManager() = default;

bool NetworkManager::initialize() {
    client_ = std::make_unique<WebSocketClient>();
    return true;
}

void NetworkManager::shutdown() {
    disconnect();
    client_.reset();
}

bool NetworkManager::connect(const std::string& server_url) {
    if (!client_) return false;
    return client_->connect(server_url);
}

void NetworkManager::disconnect() {
    if (client_) {
        client_->disconnect();
    }
}

void NetworkManager::sync_state(const AISystemState& state) {
    if (!client_ || !client_->is_connected()) return;
    
    std::string json = state.to_json();
    client_->send_json(json);
}

void NetworkManager::update() {
    if (client_) {
        client_->process_messages();
    }
}

void NetworkManager::set_state_callback(StateCallback callback) {
    state_callback_ = callback;
}

} // namespace aegis
