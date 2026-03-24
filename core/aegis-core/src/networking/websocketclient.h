#pragma once

#include <string>
#include <vector>
#include <functional>
#include <memory>
#include <atomic>
#include <mutex>
#include <queue>

namespace aegis {

/**
 * @enum ConnectionState
 * @brief WebSocket connection states
 */
enum class ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Reconnecting,
    Error
};

/**
 * @struct WebSocketMessage
 * @brief WebSocket message container
 */
struct WebSocketMessage {
    std::string data;
    bool is_binary = false;
    double timestamp = 0.0;
};

/**
 * @class WebSocketClient
 * @brief Asynchronous WebSocket client for state synchronization
 */
class WebSocketClient {
public:
    WebSocketClient();
    ~WebSocketClient();
    
    /**
     * @brief Connect to WebSocket server
     * @param url Server URL (ws:// or wss://)
     * @return true if connection initiated successfully
     */
    bool connect(const std::string& url);
    
    /**
     * @brief Disconnect from server
     */
    void disconnect();
    
    /**
     * @brief Send JSON message
     * @param json JSON string to send
     * @return true if message queued
     */
    bool send_json(const std::string& json);
    
    /**
     * @brief Send binary data
     * @param data Binary data
     * @param size Data size
     * @return true if message queued
     */
    bool send_binary(const uint8_t* data, size_t size);
    
    /**
     * @brief Get connection state
     */
    ConnectionState get_state() const { return state_.load(); }
    
    /**
     * @brief Check if connected
     */
    bool is_connected() const { return state_.load() == ConnectionState::Connected; }
    
    /**
     * @brief Set message callback
     */
    using MessageCallback = std::function<void(const WebSocketMessage&)>;
    void set_message_callback(MessageCallback callback);
    
    /**
     * @brief Set connection state callback
     */
    using StateCallback = std::function<void(ConnectionState)>;
    void set_state_callback(StateCallback callback);
    
    /**
     * @brief Process pending messages (call from main loop)
     */
    void process_messages();
    
    /**
     * @brief Get last error message
     */
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
    
    // Connection handling would use libwebsockets or similar in production
    // This is a simplified implementation
    bool connection_thread_running_ = false;
};

/**
 * @class Serializer
 * @brief JSON serialization for AI state
 */
class Serializer {
public:
    /**
     * @brief Serialize AI state to JSON
     */
    static std::string serialize_state(const class AISystemState& state);
    
    /**
     * @brief Deserialize AI state from JSON
     */
    static bool deserialize_state(const std::string& json, class AISystemState& state);
    
    /**
     * @brief Create presence transfer message
     */
    static std::string create_presence_message(const class AISystemState& state);
    
    /**
     * @brief Parse presence transfer message
     */
    static bool parse_presence_message(const std::string& json, class AISystemState& state);
};

/**
 * @class NetworkManager
 * @brief High-level networking management
 */
class NetworkManager {
public:
    NetworkManager();
    ~NetworkManager();
    
    /**
     * @brief Initialize network subsystem
     */
    bool initialize();
    
    /**
     * @brief Shutdown network subsystem
     */
    void shutdown();
    
    /**
     * @brief Connect to AEGIS network
     */
    bool connect(const std::string& server_url);
    
    /**
     * @brief Disconnect from network
     */
    void disconnect();
    
    /**
     * @brief Sync state to network
     */
    void sync_state(const class AISystemState& state);
    
    /**
     * @brief Process network events
     */
    void update();
    
    /**
     * @brief Check if connected
     */
    bool is_connected() const { return client_ && client_->is_connected(); }
    
    /**
     * @brief Set state receive callback
     */
    using StateCallback = std::function<void(const class AISystemState&)>;
    void set_state_callback(StateCallback callback);
    
private:
    std::unique_ptr<WebSocketClient> client_;
    StateCallback state_callback_;
    class AISystemState* current_state_ = nullptr;
};

} // namespace aegis
