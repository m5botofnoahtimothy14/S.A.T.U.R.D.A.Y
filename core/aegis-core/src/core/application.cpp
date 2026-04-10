#include "core/application.h"
#include "core/logger.h"
#include "core/orbitalcore.h"

namespace aegis {

Application::Application() = default;

Application::~Application() {
}

bool Application::initialize() {
    AEGIS_INFO("Application", "Initializing AEGIS Core...");
    
    renderer_ = std::make_unique<Renderer>();
    audio_engine_ = std::make_unique<AudioEngine>();
    fft_processor_ = std::make_unique<FFTProcessor>();
    state_manager_ = std::make_unique<StateManager>();
    orbital_core_ = std::make_unique<OrbitalCore>();
    network_manager_ = std::make_unique<NetworkManager>();
    
    if (!renderer_->initialize(1280, 720, "AEGIS Core")) {
        AEGIS_ERROR("Application", "Failed to initialize renderer");
        return false;
    }
    
    if (!audio_engine_->initialize(44100, 1024)) {
        AEGIS_WARN("Application", "Audio initialization failed - continuing without audio");
    }
    
    fft_processor_->initialize(1024);
    
    state_manager_->initialize();
    
    if (!orbital_core_->initialize(renderer_->get_width(), renderer_->get_height())) {
        AEGIS_ERROR("Application", "Failed to initialize orbital core");
        return false;
    }
    
    network_manager_->initialize();
    
    initialized_ = true;
    running_ = true;
    
    AEGIS_INFO("Application", "AEGIS Core initialized successfully");
    return true;
}

void Application::run() {
    if (!initialized_) {
        AEGIS_ERROR("Application", "Cannot run - not initialized");
        return;
    }
    
    AEGIS_INFO("Application", "Starting main loop...");
    
    audio_engine_->start_capture();
    
    while (running_ && !renderer_->should_close()) {
        float delta = renderer_->get_delta_time();
        
        if (audio_engine_->is_capturing()) {
            const auto& samples = audio_engine_->get_samples();
            if (!samples.empty()) {
                fft_processor_->process(samples.data(), samples.size());
                
                AudioReactiveData data;
                data.bass = fft_processor_->get_bass_energy();
                data.mid = fft_processor_->get_mid_energy();
                data.treble = fft_processor_->get_treble_energy();
                data.overall = fft_processor_->get_total_energy();
                
                static float smooth_bass = 0, smooth_mid = 0, smooth_treble = 0, smooth_overall = 0;
                float s = 0.1f;
                smooth_bass = smooth_bass * (1-s) + data.bass * s;
                smooth_mid = smooth_mid * (1-s) + data.mid * s;
                smooth_treble = smooth_treble * (1-s) + data.treble * s;
                smooth_overall = smooth_overall * (1-s) + data.overall * s;
                
                data.bass_smooth = smooth_bass;
                data.mid_smooth = smooth_mid;
                data.treble_smooth = smooth_treble;
                data.overall_smooth = smooth_overall;
                
                state_manager_->update_audio_level(data);
            }
        }
        
        state_manager_->update(delta);
        
        auto state_data = state_manager_->get_interpolated_data();
        orbital_core_->set_state(state_data);
        
        renderer_->begin_frame();
        
        AudioReactiveData dummy_data;
        dummy_data.bass_smooth = state_manager_->get_interpolated_data().pulse_amplitude * 2.0f;
        dummy_data.overall_smooth = state_manager_->get_interpolated_data().bloom_intensity / 2.0f;
        orbital_core_->set_audio_data(dummy_data);
        
        orbital_core_->update(delta, renderer_->get_time());
        orbital_core_->render();
        
        renderer_->end_frame();
        
        renderer_->poll_events();
        
        network_manager_->update();
    }
    
    audio_engine_->stop_capture();
    orbital_core_->shutdown();
    renderer_->shutdown();
    network_manager_->shutdown();
    
    AEGIS_INFO("Application", "Application shutdown complete");
}

void Application::request_shutdown() {
    running_ = false;
}

void Application::set_state(AIState state) {
    if (state_manager_) {
        state_manager_->set_state(state);
    }
}

void Application::update_audio_level(const AudioReactiveData& audio_data) {
    if (state_manager_) {
        state_manager_->update_audio_level(audio_data);
    }
}

bool Application::connect(const std::string& server_url) {
    if (network_manager_) {
        network_manager_->connect(server_url);
        return true;
    }
    return false;
}

} // namespace aegis
