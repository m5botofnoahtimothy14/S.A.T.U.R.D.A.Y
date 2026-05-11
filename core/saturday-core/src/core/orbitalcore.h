#pragma once

#include <memory>
#include <vector>
#include <array>
#include <cmath>

#include "state/aisstate.h"
#include "rendering/shader.h"
#include "rendering/mesh.h"

namespace aegis {

class OrbitalCore {
public:
    OrbitalCore();
    ~OrbitalCore();
    
    bool initialize(int width, int height);
    
    void shutdown();
    
    void set_state(const AIStateData& state_data, float transition = 1.0f);
    
    void set_audio_data(const AudioReactiveData& audio_data);
    
    void update(float delta_time, double time);
    
    void render();
    
    void resize(int width, int height);
    
    unsigned int get_output_texture() const;
    
    bool is_initialized() const { return initialized_; }
    
    void set_post_processing(bool enabled) { post_processing_enabled_ = enabled; }
    
private:
    Mesh sphere_mesh_;
    Shader core_shader_;
    
    std::vector<Mesh> ring_meshes_;
    Shader ring_shader_;
    
    Mesh arc_mesh_;
    Shader arc_shader_;
    
    Mesh particle_mesh_;
    Shader particle_shader_;
    
    Shader bloom_shader_;
    Shader composite_shader_;
    Mesh quad_mesh_;
    unsigned int framebuffer_ = 0;
    unsigned int color_texture_ = 0;
    unsigned int bloom_texture_ = 0;
    unsigned int temp_texture_ = 0;
    
    bool initialized_ = false;
    bool post_processing_enabled_ = true;
    
    int viewport_width_ = 1280;
    int viewport_height_ = 720;
    
    AIStateData current_state_;
    AIStateData target_state_;
    float state_transition_ = 1.0f;
    
    AudioReactiveData audio_data_;
    
    double time_ = 0.0f;
    float rotation_ = 0.0f;
    float pulse_phase_ = 0.0f;
    
    bool transferring_ = false;
    float transfer_progress_ = 0.0f;
    
    struct CoreUniforms {
        float time = 0.0f;
        float delta_time = 0.0f;
        
        float core_scale = 1.0f;
        float core_opacity = 1.0f;
        
        float core_color[3] = {1.0f, 0.7f, 0.0f};
        float glow_color[3] = {1.0f, 0.5f, 0.0f};
        float inner_color[3] = {1.0f, 0.9f, 0.5f};
        
        float pulse_speed = 1.0f;
        float pulse_amplitude = 0.1f;
        float rotation_speed = 0.2f;
        float distortion_strength = 0.5f;
        
        float bass_react = 0.0f;
        float mid_react = 0.0f;
        float treble_react = 0.0f;
        float overall_react = 0.0f;
        
        float transfer_progress = 0.0f;
        
        float aspect_ratio = 1.0f;
    } uniforms_;
    
    bool create_framebuffer();
    void destroy_framebuffer();
    void update_uniforms();
    
    bool create_shaders();
};

class StartupSequence {
public:
    StartupSequence();
    
    void start();
    
    bool update(float delta_time);
    
    float get_progress() const { return progress_; }
    
    std::string get_phase_name() const;
    
    bool is_complete() const { return complete_; }
    
    std::string get_overlay_text() const;
    
    float get_overlay_opacity() const;
    
private:
    enum class Phase {
        Black,
        EnergyLine,
        OrbitalGrid,
        ParticleConvergence,
        CoreIgnition,
        OnlineText,
        Complete
    };
    
    Phase current_phase_ = Phase::Black;
    float progress_ = 0.0f;
    float phase_time_ = 0.0f;
    bool complete_ = false;
    
    static constexpr float kBlackDuration = 0.5f;
    static constexpr float kEnergyLineDuration = 0.5f;
    static constexpr float kOrbitalGridDuration = 0.5f;
    static constexpr float kParticleConvergenceDuration = 0.5f;
    static constexpr float kCoreIgnitionDuration = 0.5f;
    static constexpr float kOnlineTextDuration = 1.5f;
    
    void next_phase();
};

} // namespace aegis
