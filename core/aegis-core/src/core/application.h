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

class Application {
public:
    Application();
    ~Application();
    
    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;
    
    bool initialize();
    
    void run();
    
    void request_shutdown();
    
    bool is_running() const { return running_.load(); }
    
    Renderer* get_renderer() { return renderer_.get(); }
    
    AudioEngine* get_audio_engine() { return audio_engine_.get(); }
    
    FFTProcessor* get_fft_processor() { return fft_processor_.get(); }
    
    StateManager* get_state_manager() { return state_manager_.get(); }
    
    OrbitalCore* get_orbital_core() { return orbital_core_.get(); }
    
    NetworkManager* get_network_manager() { return network_manager_.get(); }
    
    void set_state(AIState state);
    
    void update_audio_level(const AudioReactiveData& audio_data);
    
    bool connect(const std::string& server_url);
    
    static const char* get_version() { return "2.0.0"; }
    
private:
    void main_loop();
    void render_loop();
    void audio_loop();
    void update(float delta_time);
    
    bool running_ = false;
    bool initialized_ = false;
    
    std::unique_ptr<Renderer> renderer_;
    std::unique_ptr<AudioEngine> audio_engine_;
    std::unique_ptr<FFTProcessor> fft_processor_;
    std::unique_ptr<StateManager> state_manager_;
    std::unique_ptr<OrbitalCore> orbital_core_;
    std::unique_ptr<NetworkManager> network_manager_;
    
    std::thread render_thread_;
    std::thread audio_thread_;
    
    std::atomic<bool> audio_running_{false};
    
    std::mutex audio_mutex_;
    std::condition_variable audio_cv_;
    AudioReactiveData current_audio_data_;
    
    float target_frame_time_ = 1.0f / 60.0f; // 60 FPS
    float accumulator_ = 0.0f;
};

int run_application();

} // namespace aegis
