#pragma once

#include <memory>
#include <atomic>
#include <thread>
#include <condition_variable>

namespace aegis {

class Renderer;
class AudioEngine;
class FFTProcessor;
class StateManager;
class OrbitalCore;
class NetworkManager;

/**
 * @class Application
 * @brief Main AEGIS Core application
 * 
 * Manages the application lifecycle, main loop, and coordinates
 * all subsystems (rendering, audio, networking, state).
 */
class Application {
public:
    Application();
    ~Application();
    
    // Non-copyable
    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;
    
    /**
     * @brief Initialize the application
     * @return true if successful
     */
    bool initialize();
    
    /**
     * @brief Run the application main loop
     */
    void run();
    
    /**
     * @brief Request application shutdown
     */
    void request_shutdown();
    
    /**
     * @brief Check if running
     */
    bool is_running() const { return running_.load(); }
    
    /**
     * @brief Get renderer
     */
    Renderer* get_renderer() { return renderer_.get(); }
    
    /**
     * @brief Get audio engine
     */
    AudioEngine* get_audio_engine() { return audio_engine_.get(); }
    
    /**
     * @brief Get FFT processor
     */
    FFTProcessor* get_fft_processor() { return fft_processor_.get(); }
    
    /**
     * @brief Get state manager
     */
    StateManager* get_state_manager() { return state_manager_.get(); }
    
    /**
     * @brief Get orbital core
     */
    OrbitalCore* get_orbital_core() { return orbital_core_.get(); }
    
    /**
     * @brief Get network manager
     */
    NetworkManager* get_network_manager() { return network_manager_.get(); }
    
    /**
     * @brief Set API state (from external system)
     */
    void set_state(AIState state);
    
    /**
     * @brief Update audio level (from external system)
     */
    void update_audio_level(const AudioReactiveData& audio_data);
    
    /**
     * @brief Connect to network
     */
    bool connect(const std::string& server_url);
    
    /**
     * @brief Get application version
     */
    static const char* get_version() { return "2.0.0"; }
    
private:
    void main_loop();
    void render_loop();
    void audio_loop();
    void update(float delta_time);
    
    bool running_ = false;
    bool initialized_ = false;
    
    // Subsystems
    std::unique_ptr<Renderer> renderer_;
    std::unique_ptr<AudioEngine> audio_engine_;
    std::unique_ptr<FFTProcessor> fft_processor_;
    std::unique_ptr<StateManager> state_manager_;
    std::unique_ptr<OrbitalCore> orbital_core_;
    std::unique_ptr<NetworkManager> network_manager_;
    
    // Threading
    std::thread render_thread_;
    std::thread audio_thread_;
    
    std::atomic<bool> audio_running_{false};
    
    // Sync
    std::mutex audio_mutex_;
    std::condition_variable audio_cv_;
    AudioReactiveData current_audio_data_;
    
    // Timing
    float target_frame_time_ = 1.0f / 60.0f; // 60 FPS
    float accumulator_ = 0.0f;
};

/**
 * @brief Create and run the application
 */
int run_application();

} // namespace aegis
