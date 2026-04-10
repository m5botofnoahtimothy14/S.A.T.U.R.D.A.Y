#include "state/statemanager.h"

namespace aegis {

Color3 Color3::from_hex(uint32_t hex) {
    return Color3(
        ((hex >> 16) & 0xFF) / 255.0f,
        ((hex >> 8) & 0xFF) / 255.0f,
        (hex & 0xFF) / 255.0f
    );
}

uint32_t Color3::to_hex() const {
    return (static_cast<uint32_t>(r * 255) << 16) |
           (static_cast<uint32_t>(g * 255) << 8) |
           static_cast<uint32_t>(b * 255);
}

Color3 Color3::lerp(const Color3& other, float t) const {
    return Color3(
        r + (other.r - r) * t,
        g + (other.g - g) * t,
        b + (other.b - b) * t
    );
}

AIStateData AIStateData::for_state(AIState state) {
    AIStateData data;
    
    switch (state) {
        case AIState::Idle:
            data.core_color = Color3::amber();
            data.glow_color = Color3(1.0f, 0.5f, 0.0f);
            data.inner_color = Color3(1.0f, 0.9f, 0.5f);
            data.pulse_speed = 1.0f;
            data.pulse_amplitude = 0.1f;
            data.rotation_speed = 0.2f;
            data.distortion_strength = 0.3f;
            data.bloom_intensity = 1.0f;
            break;
            
        case AIState::Listening:
            data.core_color = Color3::cool_blue();
            data.glow_color = Color3(0.2f, 0.4f, 1.0f);
            data.inner_color = Color3(0.5f, 0.7f, 1.0f);
            data.pulse_speed = 2.0f;
            data.pulse_amplitude = 0.05f;
            data.rotation_speed = 0.3f;
            data.distortion_strength = 0.2f;
            data.field_tightness = 1.5f;
            data.bloom_intensity = 0.8f;
            break;
            
        case AIState::Speaking:
            data.core_color = Color3::gold();
            data.glow_color = Color3(1.0f, 0.8f, 0.2f);
            data.inner_color = Color3(1.0f, 1.0f, 0.7f);
            data.pulse_speed = 3.0f;
            data.pulse_amplitude = 0.2f;
            data.rotation_speed = 0.5f;
            data.distortion_strength = 0.6f;
            data.bloom_intensity = 1.5f;
            break;
            
        case AIState::Secure:
            data.core_color = Color3::violet();
            data.glow_color = Color3(0.5f, 0.1f, 0.8f);
            data.inner_color = Color3(0.8f, 0.4f, 1.0f);
            data.pulse_speed = 0.5f;
            data.pulse_amplitude = 0.15f;
            data.rotation_speed = 0.1f;
            data.distortion_strength = 0.4f;
            data.bloom_intensity = 2.0f;
            break;
            
        case AIState::Transfer:
            data.core_color = Color3::cyan();
            data.glow_color = Color3(0.0f, 1.0f, 1.0f);
            data.inner_color = Color3(0.5f, 1.0f, 1.0f);
            data.pulse_speed = 8.0f;
            data.pulse_amplitude = 0.5f;
            data.rotation_speed = 1.0f;
            data.distortion_strength = 1.0f;
            data.bloom_intensity = 3.0f;
            break;
    }
    
    return data;
}

std::string AISystemState::to_json() const {
    std::string json = "{";
    json += "\"state\":" + std::to_string(static_cast<int>(current_state));
    json += ",\"audio_reactivity\":" + std::to_string(audio_reactivity);
    json += ",\"core_scale\":" + std::to_string(core_scale);
    json += ",\"timestamp\":" + std::to_string(timestamp);
    json += "}";
    return json;
}

AISystemState AISystemState::from_json(const std::string& json) {
    AISystemState state;
    state.current_state = AIState::Idle;
    return state;
}

StateManager::StateManager() = default;
StateManager::~StateManager() = default;

void StateManager::initialize() {
    current_state_ = AIState::Idle;
    current_state_data_ = AIStateData::for_state(AIState::Idle);
    interpolated_data_ = current_state_data_;
}

void StateManager::shutdown() {
}

void StateManager::set_state(AIState new_state, bool immediate) {
    if (new_state == current_state_ && !immediate) return;
    
    AIState old_state = current_state_;
    target_state_ = new_state;
    
    current_state_ = new_state;
    current_state_data_ = AIStateData::for_state(new_state);
    
    if (immediate) {
        target_state_data_ = current_state_data_;
        interpolated_data_ = current_state_data_;
        transition_time_ = transition_duration_;
    } else {
        target_state_data_ = current_state_data_;
        transition_time_ = 0.0f;
    }
    
    on_state_changed(old_state, new_state);
}

void StateManager::update_audio_level(const AudioReactiveData& audio_data) {
    float smooth_factor = 0.15f;
    audio_bass_factor_ = audio_bass_factor_ * (1 - smooth_factor) + audio_data.bass_smooth * smooth_factor;
    audio_mid_factor_ = audio_mid_factor_ * (1 - smooth_factor) + audio_data.mid_smooth * smooth_factor;
    audio_treble_factor_ = audio_treble_factor_ * (1 - smooth_factor) + audio_data.treble_smooth * smooth_factor;
    audio_overall_factor_ = audio_overall_factor_ * (1 - smooth_factor) + audio_data.overall_smooth * smooth_factor;
    
    smoothed_audio_level_ = audio_overall_factor_;
}

void StateManager::update(float delta_time) {
    transition_time_ += delta_time;
    
    float t = std::min(transition_time_ / transition_duration_, 1.0f);
    
    interpolate_state_data(t);
}

void StateManager::interpolate_state_data(float t) {
    interpolated_data_.core_color = current_state_data_.core_color.lerp(target_state_data_.core_color, t);
    interpolated_data_.glow_color = current_state_data_.glow_color.lerp(target_state_data_.glow_color, t);
    interpolated_data_.inner_color = current_state_data_.inner_color.lerp(target_state_data_.inner_color, t);
    
    interpolated_data_.pulse_speed = current_state_data_.pulse_speed + 
        (target_state_data_.pulse_speed - current_state_data_.pulse_speed) * t;
    interpolated_data_.pulse_amplitude = current_state_data_.pulse_amplitude + 
        (target_state_data_.pulse_amplitude - current_state_data_.pulse_amplitude) * t;
    interpolated_data_.rotation_speed = current_state_data_.rotation_speed + 
        (target_state_data_.rotation_speed - current_state_data_.rotation_speed) * t;
    interpolated_data_.distortion_strength = current_state_data_.distortion_strength + 
        (target_state_data_.distortion_strength - current_state_data_.distortion_strength) * t;
    
    interpolated_data_.pulse_amplitude += audio_overall_factor_ * 0.2f;
    interpolated_data_.distortion_strength += audio_bass_factor_ * 0.3f;
    interpolated_data_.bloom_intensity = interpolated_data_.bloom_intensity * (1.0f + audio_overall_factor_ * 0.5f);
    
    interpolated_data_.transition_progress = t;
}

void StateManager::on_state_changed(AIState old_state, AIState new_state) {
    if (state_change_callback_) {
        state_change_callback_(old_state, new_state);
    }
}

AISystemState StateManager::get_system_state() const {
    AISystemState state;
    state.current_state = current_state_;
    state.state_data = interpolated_data_;
    state.audio_reactivity = audio_overall_factor_;
    state.timestamp = 0.0; // Would get actual timestamp
    return state;
}

void StateManager::apply_state(const AISystemState& state) {
    set_state(state.current_state, true);
}

void StateManager::set_state_change_callback(StateChangeCallback callback) {
    state_change_callback_ = callback;
}

void StateManager::initiate_transfer(const std::string& target_node) {
    transferring_ = true;
    transfer_progress_ = 0.0f;
    set_state(AIState::Transfer, false);
}

} // namespace aegis
