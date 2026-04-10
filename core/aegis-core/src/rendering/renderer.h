#pragma once

#include <string>
#include <memory>
#include <vector>
#include <array>

#include <GLFW/glfw3.h>
#include <GL/gl.h>

namespace aegis {

class Shader;
class Mesh;

class Renderer {
public:
    Renderer();
    ~Renderer();
    
    Renderer(const Renderer&) = delete;
    Renderer& operator=(const Renderer&) = delete;
    
    bool initialize(int width, int height, const std::string& title);
    
    void shutdown();
    
    void begin_frame();
    
    void end_frame();
    
    bool should_close() const;
    
    void poll_events();
    
    void set_title(const std::string& title);
    void set_size(int width, int height);
    void set_fullscreen(bool fullscreen);
    bool is_fullscreen() const { return fullscreen_; }
    
    int get_width() const { return width_; }
    int get_height() const { return height_; }
    float get_aspect_ratio() const { 
        return static_cast<float>(width_) / static_cast<float>(height_); 
    }
    GLFWwindow* get_window() { return window_; }
    
    double get_time() const;
    
    float get_delta_time() const { return delta_time_; }
    
    void set_clear_color(float r, float g, float b, float a = 1.0f);
    
    void set_vsync(bool enabled);
    
    bool is_initialized() const { return initialized_; }
    
private:
    bool initialized_ = false;
    GLFWwindow* window_ = nullptr;
    
    int width_ = 1280;
    int height_ = 720;
    bool fullscreen_ = false;
    bool vsync_ = true;
    
    double last_time_ = 0.0;
    float delta_time_ = 0.0f;
    
    float clear_color_[4] = {0.0f, 0.0f, 0.0f, 1.0f};
    
    int saved_width_ = 1280;
    int saved_height_ = 1280;
    int saved_x_ = 100;
    int saved_y_ = 100;
};

class Renderer2D {
public:
    Renderer2D();
    ~Renderer2D();
    
    void initialize();
    void shutdown();
    
    void begin();
    void end();
    
    void draw_rect(float x, float y, float width, float height, const float* color);
    void draw_line(float x1, float y1, float x2, float y2, float thickness, const float* color);
    void draw_circle(float cx, float cy, float radius, const float* color, int segments = 32);
    
private:
    bool initialized_ = false;
};

} // namespace aegis
