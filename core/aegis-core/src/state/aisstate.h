#pragma once

#include <string>
#include <array>
#include <vector>
#include <functional>
#include <memory>

namespace aegis {

enum class AIState {
    Idle,       // Default resting state - slow breathing amber glow
    Listening,  // Active listening - tightened energy field, cooler tone
    Speaking,   // Speaking/output - fluid FFT-driven golden surges
    Secure,     // Secure mode - violet inner core
    Transfer    // Presence transfer - collapse to beam, re-materialize
};

struct Color3 {
    float r = 0.0f, g = 0.0f, b = 0.0f;
    
    Color3() = default;
    Color3(float r_, float g_, float b_) : r(r_), g(g_), b(b_) {}
    
    static Color3 from_hex(uint32_t hex);
    uint32_t to_hex() const;
    
    Color3 lerp(const Color3& other, float t) const;
    
    static Color3 amber() { return Color3(1.0f, 0.7f, 0.0f); }
    static Color3 gold() { return Color3(1.0f, 0.85f, 0.0f); }
    static Color3 cyan() { return Color3(0.0f, 1.0f, 1.0f); }
    static Color3 violet() { return Color3(0.6f, 0.2f, 0.8f); }
    static Color3 cool_blue() { return Color3(0.3f, 0.5f, 1.0f); }
    static Color3 white() { return Color3(1.0f, 1.0f, 1.0f); }
    static Color3 black() { return Color3(0.0f, 0.0f, 0.0f); }
};

struct AIStateData {
    Color3 core_color;
    Color3 glow_color;
    Color3 inner_color;
    
    float pulse_speed = 1.0f;       // Base pulse rate
    float pulse_amplitude = 0.1f;   // Pulse intensity
    float rotation_speed = 0.2f;    // Axial rotation
    float distortion_strength = 0.5f;
    
    float ring_count = 2.0f;
    float ring_expansion = 1.0f;
    float ring_orbit_speed = 0.3f;
    
    float arc_count = 3.0f;
    float arc_intensity = 0.5f;
    
    float field_tightness = 1.0f;   // Energy field density
    float bloom_intensity = 1.0f;
    
    float transition_progress = 1.0f;
    
    static AIStateData for_state(AIState state);
};

struct AISystemState {
    AIState current_state = AIState::Idle;
    
    AIStateData state_data;
    float audio_reactivity = 0.0f;
    
    float core_scale = 1.0f;
    float core_opacity = 1.0f;
    float glow_radius = 1.5f;
    
    float time = 0.0f;
    float rotation = 0.0f;
    float pulse_phase = 0.0f;
    
    bool is_transferring = false;
    float transfer_progress = 0.0f;
    std::string target_node;
    
    std::string device_id;
    std::string version = "2.0.0";
    double timestamp = 0.0;
    
    std::array<float, 8> audio_bands = {0};
    
    std::string to_json() const;
    
    static AISystemState from_json(const std::string& json);
};

class StateManager {
public:
    StateManager();
    ~StateManager();
    
    void initialize();
    
    void shutdown();
    
    void set_state(AIState new_state, bool immediate = false);
    
    AIState get_state() const { return current_state_; }
    
    const AIStateData& get_state_data() const { return current_state_data_; }
    
    const AIStateData& get_interpolated_data() const { return interpolated_data_; }
    
    void update_audio_level(const AudioReactiveData& audio_data);
    
    void update(float delta_time);
    
    AISystemState get_system_state() const;
    
    void apply_state(const AISystemState& state);
    
    using StateChangeCallback = std::function<void(AIState, AIState)>;
    void set_state_change_callback(StateChangeCallback callback);
    
    void initiate_transfer(const std::string& target_node);
    
    bool is_transferring() const { return transferring_; }
    
    float get_transfer_progress() const { return transfer_progress_; }
    
private:
    void interpolate_state_data(float t);
    void on_state_changed(AIState old_state, AIState new_state);
    
    AIState current_state_ = AIState::Idle;
    AIState target_state_ = AIState::Idle;
    
    AIStateData current_state_data_;
    AIStateData target_state_data_;
    AIStateData interpolated_data_;
    
    float transition_time_ = 0.0f;
    float transition_duration_ = 1.0f; // 1 second default transition
    
    bool transferring_ = false;
    float transfer_progress_ = 0.0f;
    
    float audio_bass_factor_ = 0.0f;
    float audio_mid_factor_ = 0.0f;
    float audio_treble_factor_ = 0.0f;
    float audio_overall_factor_ = 0.0f;
    
    float smoothed_audio_level_ = 0.0f;
    
    StateChangeCallback state_change_callback_;
};

} // namespace aegis
