#include "rendering/renderer.h"
#include "core/logger.h"
#include "core/raii.h"

#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
#pragma comment(lib, "glfw3.lib")

// OpenGL extensions
#include <GL/gl.h>
#include <GL/glew.h>
#pragma comment(lib, "opengl32.lib")

namespace aegis {

// Global GLFW initialization
static bool glfw_initialized = false;

Renderer::Renderer() = default;

Renderer::~Renderer() {
    shutdown();
}

bool Renderer::initialize(int width, int height, const std::string& title) {
    if (initialized_) {
        AEGIS_WARN("Renderer", "Already initialized");
        return true;
    }
    
    width_ = width;
    height_ = height;
    
    // Initialize GLFW
    if (!glfw_initialized) {
        if (!glfwInit()) {
            AEGIS_ERROR("Renderer", "Failed to initialize GLFW");
            return false;
        }
        glfw_initialized = true;
        AEGIS_INFO("Renderer", "GLFW initialized");
    }
    
    // Configure OpenGL context
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 4);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 5);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
    glfwWindowHint(GLFW_SAMPLES, 4); // MSAA 4x
    
    // Create window
    window_ = glfwCreateWindow(width, height, title.c_str(), nullptr, nullptr);
    if (!window_) {
        AEGIS_ERROR("Renderer", "Failed to create window");
        return false;
    }
    
    glfwMakeContextCurrent(window_);
    
    // Initialize GLEW
    glewExperimental = GL_TRUE;
    GLenum err = glewInit();
    if (err != GLEW_OK) {
        AEGIS_ERROR("Renderer", "Failed to initialize GLEW: " + 
                   std::string((const char*)glewGetErrorString(err)));
        return false;
    }
    
    // Clear any errors from GLEW init
    while (glGetError() != GL_NO_ERROR) {}
    
    // Configure OpenGL state
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    
    // Enable MSAA
    glEnable(GL_MULTISAMPLE);
    
    // Set vsync
    glfwSwapInterval(vsync_ ? 1 : 0);
    
    last_time_ = glfwGetTime();
    
    initialized_ = true;
    AEGIS_INFO("Renderer", "OpenGL 4.5+ renderer initialized successfully");
    AEGIS_INFO("Renderer", "OpenGL Version: " + std::string((const char*)glGetString(GL_VERSION)));
    AEGIS_INFO("Renderer", "GPU: " + std::string((const char*)glGetString(GL_RENDERER)));
    
    return true;
}

void Renderer::shutdown() {
    if (!initialized_) return;
    
    if (window_) {
        glfwDestroyWindow(window_);
        window_ = nullptr;
    }
    
    initialized_ = false;
    AEGIS_INFO("Renderer", "Renderer shutdown complete");
}

void Renderer::begin_frame() {
    glClearColor(clear_color_[0], clear_color_[1], clear_color_[2], clear_color_[3]);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    
    double current_time = glfwGetTime();
    delta_time_ = static_cast<float>(current_time - last_time_);
    last_time_ = current_time;
}

void Renderer::end_frame() {
    glfwSwapBuffers(window_);
}

bool Renderer::should_close() const {
    return window_ && glfwWindowShouldClose(window_);
}

void Renderer::poll_events() {
    glfwPollEvents();
}

void Renderer::set_title(const std::string& title) {
    if (window_) {
        glfwSetWindowTitle(window_, title.c_str());
    }
}

void Renderer::set_size(int width, int height) {
    if (window_ && !fullscreen_) {
        width_ = width;
        height_ = height;
        glfwSetWindowSize(window_, width, height);
    }
}

void Renderer::set_fullscreen(bool fullscreen) {
    if (fullscreen == fullscreen_) return;
    
    if (fullscreen) {
        // Save windowed state
        glfwGetWindowPos(window_, &saved_x_, &saved_y_);
        glfwGetWindowSize(window_, &saved_width_, &saved_height_);
        
        // Get primary monitor
        GLFWmonitor* monitor = glfwGetPrimaryMonitor();
        const GLFWvidmode* mode = glfwGetVideoMode(monitor);
        
        glfwSetWindowMonitor(window_, monitor, 0, 0, mode->width, mode->height, 
                            mode->refreshRate);
        width_ = mode->width;
        height_ = mode->height;
    } else {
        glfwSetWindowMonitor(window_, nullptr, saved_x_, saved_y_, 
                            saved_width_, saved_height_, 0);
        width_ = saved_width_;
        height_ = saved_height_;
    }
    
    fullscreen_ = fullscreen;
}

double Renderer::get_time() const {
    return glfwGetTime();
}

void Renderer::set_clear_color(float r, float g, float b, float a) {
    clear_color_[0] = r;
    clear_color_[1] = g;
    clear_color_[2] = b;
    clear_color_[3] = a;
}

void Renderer::set_vsync(bool enabled) {
    vsync_ = enabled;
    glfwSwapInterval(enabled ? 1 : 0);
}

} // namespace aegis
