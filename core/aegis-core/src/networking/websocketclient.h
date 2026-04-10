#pragma once

#include <string>
#include <vector>
#include <functional>
#include <memory>
#include <atomic>
#include <mutex>
#include <queue>

namespace aegis {

enum class ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Reconnecting,
    Error
};

struct WebSocketMessage {
    std::string data;
    bool is_binary = false;
    double timestamp = 0.0;
};

class WebSocketClient {
public:
    WebSocketClient();
    ~WebSocketClient();
    
    bool connect(const std::string& url);
    
    void disconnect();
    
    bool send_json(const std::string& json);
    
    bool send_binary(const uint8_t* data, size_t size);
    
    ConnectionState get_state() const { return state_.load(); }
    
    bool is_connected() const { return state_.load() == ConnectionState::Connected; }
    
    using MessageCallback = std::function<void(const WebSocketMessage&)>;
    void set_message_callback(MessageCallback callback);
    
    using StateCallback = std::function<void(ConnectionState)>;
    void set_state_callback(StateCallback callback);
    
    void process_messages();
    
    std::string get_last_error() const;
    
private:
    void set_state(ConnectionState state);
    void on_message_received(const WebSocketMessage& msg);
    
    std::string url_;
    std::atomic<ConnectionState> state_{ConnectionState::Disconnected};
    std::string last_error_;
    
    MessageCallback message_callback_;
    StateCallback state_callback_;
    
    std::mutex message_queue_mutex_;
    std::queue<WebSocketMessage> message_queue_;
    
    bool connection_thread_running_ = false;
};

class Serializer {
public:
    static std::string serialize_state(const class AISystemState& state);
    
    static bool deserialize_state(const std::string& json, class AISystemState& state);
    
    static std::string create_presence_message(const class AISystemState& state);
    
    static bool parse_presence_message(const std::string& json, class AISystemState& state);
};

class NetworkManager {
public:
    NetworkManager();
    ~NetworkManager();
    
    bool initialize();
    
    void shutdown();
    
    bool connect(const std::string& server_url);
    
    void disconnect();
    
    void sync_state(const class AISystemState& state);
    
    void update();
    
    bool is_connected() const { return client_ && client_->is_connected(); }
    
    using StateCallback = std::function<void(const class AISystemState&)>;
    void set_state_callback(StateCallback callback);
    
private:
    std::unique_ptr<WebSocketClient> client_;
    StateCallback state_callback_;
    class AISystemState* current_state_ = nullptr;
};

} // namespace aegis
