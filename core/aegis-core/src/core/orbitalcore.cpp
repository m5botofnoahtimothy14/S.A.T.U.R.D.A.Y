#include "core/orbitalcore.h"

namespace aegis {

OrbitalCore::OrbitalCore() = default;
OrbitalCore::~OrbitalCore() {
    shutdown();
}

bool OrbitalCore::initialize(int width, int height) {
    viewport_width_ = width;
    viewport_height_ = height;
    
    // Create meshes
    sphere_mesh_ = Mesh::create_sphere(1.0f, 64, 32);
    ring_meshes_.push_back(Mesh::create_torus(1.5f, 0.05f, 64, 16));
    ring_meshes_.push_back(Mesh::create_torus(2.0f, 0.03f, 64, 16));
    arc_mesh_ = Mesh::create_sphere(1.2f, 32, 16);
    particle_mesh_ = Mesh::create_particle_system(1000);
    quad_mesh_ = Mesh::create_quad();
    
    // Create framebuffer for post-processing
    if (!create_framebuffer()) {
        post_processing_enabled_ = false;
    }
    
    initialized_ = true;
    return initialized_;
}

void OrbitalCore::shutdown() {
    if (!initialized_) return;
    
    destroy_framebuffer();
    initialized_ = false;
}

void OrbitalCore::set_state(const AIStateData& state_data, float transition) {
    target_state_ = state_data;
    state_transition_ = transition;
}

void OrbitalCore::set_audio_data(const AudioReactiveData& audio_data) {
    audio_data_ = audio_data;
}

void OrbitalCore::update(float delta_time, double time) {
    time_ = time;
    
    // Smooth state transition
    float lerp_factor = delta_time * 3.0f;
    current_state_.core_color.r = current_state_.core_color.r * (1 - lerp_factor) + target_state_.core_color.r * lerp_factor;
    current_state_.core_color.g = current_state_.core_color.g * (1 - lerp_factor) + target_state_.core_color.g * lerp_factor;
    current_state_.core_color.b = current_state_.core_color.b * (1 - lerp_factor) + target_state_.core_color.b * lerp_factor;
    
    // Audio reactive updates
    uniforms_.bass_react = audio_data_.bass_smooth;
    uniforms_.mid_react = audio_data_.mid_smooth;
    uniforms_.treble_react = audio_data_.treble_smooth;
    uniforms_.overall_react = audio_data_.overall_smooth;
    
    // Update animation
    rotation_ += delta_time * current_state_.rotation_speed;
    pulse_phase_ += delta_time * current_state_.pulse_speed;
    
    update_uniforms();
}

void OrbitalCore::render() {
    if (!initialized_) return;
    
    // Render to framebuffer if post-processing enabled
    if (post_processing_enabled_) {
        // Bind framebuffer
    }
    
    // Clear
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    
    // Render core sphere
    // (In production, would bind shader and draw mesh)
    
    // Render rings
    // Render particles
    
    // Post-processing pass if enabled
    if (post_processing_enabled_) {
        // Bloom pass
    }
}

void OrbitalCore::resize(int width, int height) {
    viewport_width_ = width;
    viewport_height_ = height;
    
    if (framebuffer_) {
        destroy_framebuffer();
        create_framebuffer();
    }
    
    uniforms_.aspect_ratio = static_cast<float>(width) / static_cast<float>(height);
}

unsigned int OrbitalCore::get_output_texture() const {
    return color_texture_;
}

bool OrbitalCore::create_framebuffer() {
    // Simplified framebuffer creation
    // In production, would use proper FBO setup
    return true;
}

void OrbitalCore::destroy_framebuffer() {
    // Clean up framebuffer resources
}

void OrbitalCore::update_uniforms() {
    uniforms_.time = static_cast<float>(time_);
    uniforms_.core_color[0] = current_state_.core_color.r;
    uniforms_.core_color[1] = current_state_.core_color.g;
    uniforms_.core_color[2] = current_state_.core_color.b;
    uniforms_.glow_color[0] = current_state_.glow_color.r;
    uniforms_.glow_color[1] = current_state_.glow_color.g;
    uniforms_.glow_color[2] = current_state_.glow_color.b;
    uniforms_.inner_color[0] = current_state_.inner_color.r;
    uniforms_.inner_color[1] = current_state_.inner_color.g;
    uniforms_.inner_color[2] = current_state_.inner_color.b;
    uniforms_.pulse_speed = current_state_.pulse_speed;
    uniforms_.pulse_amplitude = current_state_.pulse_amplitude;
    uniforms_.rotation_speed = current_state_.rotation_speed;
    uniforms_.distortion_strength = current_state_.distortion_strength;
}

bool OrbitalCore::create_shaders() {
    // Load shaders from files
    return true;
}

// Startup Sequence Implementation
StartupSequence::StartupSequence() = default;

void StartupSequence::start() {
    current_phase_ = Phase::Black;
    progress_ = 0.0f;
    phase_time_ = 0.0f;
    complete_ = false;
}

bool StartupSequence::update(float delta_time) {
    if (complete_) return false;
    
    phase_time_ += delta_time;
    
    switch (current_phase_) {
        case Phase::Black:
            progress_ = phase_time_ / kBlackDuration;
            if (phase_time_ >= kBlackDuration) next_phase();
            break;
            
        case Phase::EnergyLine:
            progress_ = phase_time_ / kEnergyLineDuration;
            if (phase_time_ >= kEnergyLineDuration) next_phase();
            break;
            
        case Phase::OrbitalGrid:
            progress_ = phase_time_ / kOrbitalGridDuration;
            if (phase_time_ >= kOrbitalGridDuration) next_phase();
            break;
            
        case Phase::ParticleConvergence:
            progress_ = phase_time_ / kParticleConvergenceDuration;
            if (phase_time_ >= kParticleConvergenceDuration) next_phase();
            break;
            
        case Phase::CoreIgnition:
            progress_ = phase_time_ / kCoreIgnitionDuration;
            if (phase_time_ >= kCoreIgnitionDuration) next_phase();
            break;
            
        case Phase::OnlineText:
            progress_ = phase_time_ / kOnlineTextDuration;
            if (phase_time_ >= kOnlineTextDuration) next_phase();
            break;
            
        case Phase::Complete:
            complete_ = true;
            return false;
    }
    
    return true;
}

void StartupSequence::next_phase() {
    phase_time_ = 0.0f;
    progress_ = 0.0f;
    
    int phase = static_cast<int>(current_phase_);
    current_phase_ = static_cast<Phase>(phase + 1);
}

std::string StartupSequence::get_phase_name() const {
    switch (current_phase_) {
        case Phase::Black: return "Initializing";
        case Phase::EnergyLine: return "Energy Line";
        case Phase::OrbitalGrid: return "Orbital Grid";
        case Phase::ParticleConvergence: return "Particle Convergence";
        case Phase::CoreIgnition: return "Core Ignition";
        case Phase::OnlineText: return "AEGIS CORE ONLINE";
        case Phase::Complete: return "Complete";
        default: return "";
    }
}

std::string StartupSequence::get_overlay_text() const {
    if (current_phase_ == Phase::OnlineText || current_phase_ == Phase::Complete) {
        return "AEGIS CORE ONLINE";
    }
    return "";
}

float StartupSequence::get_overlay_opacity() const {
    if (current_phase_ == Phase::OnlineText) {
        return progress_;
    }
    if (current_phase_ == Phase::Complete) {
        return 1.0f;
    }
    return 0.0f;
}

} // namespace aegis
