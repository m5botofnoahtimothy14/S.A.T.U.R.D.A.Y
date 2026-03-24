#pragma once

#include <memory>
#include <vector>
#include <array>
#include <cmath>

#include "state/aisstate.h"
#include "rendering/shader.h"
#include "rendering/mesh.h"

namespace aegis {

/**
 * @class OrbitalCore
 * @brief GPU-accelerated Orbital Intelligence Core renderer
 * 
 * Renders the AEGIS visual embodiment with:
 * - Dynamic energy sphere with vertex displacement
 * - Procedural noise distortion
 * - Orbiting particle rings
 * - Animated energy arcs
 * - Bloom post-processing
 * - Audio-reactive behavior
 */
class OrbitalCore {
public:
    OrbitalCore();
    ~OrbitalCore();
    
    /**
     * @brief Initialize the orbital core
     * @param width Viewport width
     * @param height Viewport height
     * @return true if successful
     */
    bool initialize(int width, int height);
    
    /**
     * @brief Shutdown and release resources
     */
    void shutdown();
    
    /**
     * @brief Set current state for visualization
     */
    void set_state(const AIStateData& state_data, float transition = 1.0f);
    
    /**
     * @brief Set audio reactive data
     */
    void set_audio_data(const AudioReactiveData& audio_data);
    
    /**
     * @brief Update (call each frame)
     * @param delta_time Time since last frame
     * @param time Total elapsed time
     */
    void update(float delta_time, double time);
    
    /**
     * @brief Render the core
     */
    void render();
    
    /**
     * @brief Handle window resize
     */
    void resize(int width, int height);
    
    /**
     * @brief Get render target texture for compositing
     */
    unsigned int get_output_texture() const;
    
    /**
     * @brief Check if initialized
     */
    bool is_initialized() const { return initialized_; }
    
    /**
     * @brief Enable/disable post-processing
     */
    void set_post_processing(bool enabled) { post_processing_enabled_ = enabled; }
    
private:
    // Core sphere
    Mesh sphere_mesh_;
    Shader core_shader_;
    
    // Energy rings
    std::vector<Mesh> ring_meshes_;
    Shader ring_shader_;
    
    // Energy arcs
    Mesh arc_mesh_;
    Shader arc_shader_;
    
    // Particles
    Mesh particle_mesh_;
    Shader particle_shader_;
    
    // Post-processing
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
    
    // Current state
    AIStateData current_state_;
    AIStateData target_state_;
    float state_transition_ = 1.0f;
    
    // Audio data
    AudioReactiveData audio_data_;
    
    // Animation state
    double time_ = 0.0f;
    float rotation_ = 0.0f;
    float pulse_phase_ = 0.0f;
    
    // Transfer state
    bool transferring_ = false;
    float transfer_progress_ = 0.0f;
    
    // Shader uniforms
    struct CoreUniforms {
        // Time and animation
        float time = 0.0f;
        float delta_time = 0.0f;
        
        // Core appearance
        float core_scale = 1.0f;
        float core_opacity = 1.0f;
        
        // Colors
        float core_color[3] = {1.0f, 0.7f, 0.0f};
        float glow_color[3] = {1.0f, 0.5f, 0.0f};
        float inner_color[3] = {1.0f, 0.9f, 0.5f};
        
        // Animation
        float pulse_speed = 1.0f;
        float pulse_amplitude = 0.1f;
        float rotation_speed = 0.2f;
        float distortion_strength = 0.5f;
        
        // Audio reactivity
        float bass_react = 0.0f;
        float mid_react = 0.0f;
        float treble_react = 0.0f;
        float overall_react = 0.0f;
        
        // Transfer
        float transfer_progress = 0.0f;
        
        // View
        float aspect_ratio = 1.0f;
    } uniforms_;
    
    bool create_framebuffer();
    void destroy_framebuffer();
    void update_uniforms();
    
    // Helper to create shaders
    bool create_shaders();
};

/**
 * @class StartupSequence
 * @brief Manages the AEGIS startup animation
 */
class StartupSequence {
public:
    StartupSequence();
    
    /**
     * @brief Start the startup sequence
     */
    void start();
    
    /**
     * @brief Update sequence (call each frame)
     * @return true if sequence still running
     */
    bool update(float delta_time);
    
    /**
     * @brief Get current progress (0-1)
     */
    float get_progress() const { return progress_; }
    
    /**
     * @brief Get current phase name
     */
    std::string get_phase_name() const;
    
    /**
     * @brief Check if complete
     */
    bool is_complete() const { return complete_; }
    
    /**
     * @brief Get overlay text (for "AEGIS CORE ONLINE")
     */
    std::string get_overlay_text() const;
    
    /**
     * @brief Get overlay opacity
     */
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
    
    // Phase durations
    static constexpr float kBlackDuration = 0.5f;
    static constexpr float kEnergyLineDuration = 0.5f;
    static constexpr float kOrbitalGridDuration = 0.5f;
    static constexpr float kParticleConvergenceDuration = 0.5f;
    static constexpr float kCoreIgnitionDuration = 0.5f;
    static constexpr float kOnlineTextDuration = 1.5f;
    
    void next_phase();
};

} // namespace aegis
