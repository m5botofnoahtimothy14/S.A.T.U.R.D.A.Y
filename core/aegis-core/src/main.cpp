#include <GLFW/glfw3.h>
#include <GL/gl.h>
#include <cmath>
#include <vector>
#include <string>
#include <iostream>
#include <chrono>
#include <thread>
#include <algorithm>

namespace {
    const int WINDOW_WIDTH = 800;
    const int WINDOW_HEIGHT = 600;
    const float PI = 3.14159265359f;
}

struct Vec3 {
    float x, y, z;
    Vec3(float x_ = 0, float y_ = 0, float z_ = 0) : x(x_), y(y_), z(z_) {}
};

struct Color {
    float r, g, b, a;
    Color(float r_ = 1, float g_ = 1, float b_ = 1, float a_ = 1) : r(r_), g(g_), b(b_), a(a_) {}
};

// Simple hash for deterministic noise without RNG state
float hash11(float n) {
    return fmodf(sinf(n) * 43758.5453f, 1.0f);
}

Color mix(const Color& a, const Color& b, float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    return Color(
        a.r + (b.r - a.r) * t,
        a.g + (b.g - a.g) * t,
        a.b + (b.b - a.b) * t,
        a.a + (b.a - a.a) * t
    );
}

void drawGlowDisc(float radius, float innerRadius, int segments, const Color& inner, const Color& outer) {
    glBegin(GL_TRIANGLE_STRIP);
    for (int i = 0; i <= segments; ++i) {
        float angle = 2.0f * PI * i / segments;
        float c = cosf(angle);
        float s = sinf(angle);
        glColor4f(inner.r, inner.g, inner.b, inner.a);
        glVertex2f(innerRadius * c, innerRadius * s);
        glColor4f(outer.r, outer.g, outer.b, outer.a);
        glVertex2f(radius * c, radius * s);
    }
    glEnd();
}

void drawRing(float radius, float thickness, int segments, const Color& color) {
    float inner = radius - thickness * 0.5f;
    float outer = radius + thickness * 0.5f;
    glBegin(GL_TRIANGLE_STRIP);
    glColor4f(color.r, color.g, color.b, color.a);
    for (int i = 0; i <= segments; ++i) {
        float angle = 2.0f * PI * i / segments;
        float c = cosf(angle);
        float s = sinf(angle);
        glVertex2f(inner * c, inner * s);
        glVertex2f(outer * c, outer * s);
    }
    glEnd();
}

void drawRadials(float time) {
    int rays = 120;
    glBegin(GL_LINES);
    for (int i = 0; i < rays; ++i) {
        float baseAngle = 2.0f * PI * i / rays;
        float jitter = (hash11(i * 13.37f + floorf(time * 10.0f)) - 0.5f) * 0.08f;
        float angle = baseAngle + jitter;
        float len = 0.25f + 0.45f * hash11(i * 3.1f + time * 2.0f);
        float fade = 0.35f + 0.65f * hash11(i * 7.77f + time * 1.3f);
        glColor4f(1.0f, 0.75f, 0.25f, 0.08f * fade);
        glVertex2f(0.0f, 0.0f);
        glColor4f(1.0f, 0.55f, 0.05f, 0.0f);
        glVertex2f(len * cosf(angle), len * sinf(angle));
    }
    glEnd();
}

void drawOrbitingFragments(float time, float radius) {
    int fragments = 90;
    glPointSize(3.5f);
    glBegin(GL_POINTS);
    for (int i = 0; i < fragments; ++i) {
        float layer = (i % 3) * 0.03f;
        float angle = 2.0f * PI * hash11(i * 12.989f) + time * (0.6f + 0.2f * layer) + layer * 7.0f;
        float r = radius * (0.65f + 0.35f * hash11(i * 4.2f)) + layer;
        float flicker = 0.5f + 0.5f * sinf(time * 8.0f + i);
        glColor4f(1.0f, 0.8f, 0.35f, 0.4f * flicker);
        glVertex2f(r * cosf(angle), r * sinf(angle));
    }
    glEnd();
}

void drawCoreSpiral(float time, float radius) {
    glBegin(GL_LINE_STRIP);
    int steps = 260;
    for (int i = 0; i <= steps; ++i) {
        float t = static_cast<float>(i) / steps;
        float a = 6.0f * PI * t + time * 1.2f;
        float r = radius * (0.05f + 0.95f * t);
        Color c = mix(Color(1.0f, 0.85f, 0.4f, 0.75f), Color(1.0f, 0.4f, 0.05f, 0.25f), t);
        glColor4f(c.r, c.g, c.b, c.a);
        glVertex2f(r * cosf(a), r * sinf(a));
    }
    glEnd();
}

void drawPulse(float time, float intensity) {
    // Orbital glow layers
    float base = 0.35f + 0.05f * sinf(time * 2.0f);
    float glow = 0.55f + 0.08f * sinf(time * 5.0f);

    Color inner(1.0f, 0.82f, 0.45f, 0.50f * intensity);
    Color mid(1.0f, 0.62f, 0.15f, 0.25f * intensity);
    Color outer(1.0f, 0.45f, 0.05f, 0.08f * intensity);

    glBlendFunc(GL_SRC_ALPHA, GL_ONE); // additive for glow
    drawGlowDisc(base * 1.25f, base * 0.05f, 120, inner, outer);
    drawGlowDisc(glow * 1.15f, glow * 0.08f, 120, mid, outer);

    // Concentric rings
    for (int i = 0; i < 4; ++i) {
        float t = static_cast<float>(i) / 4.0f;
        float r = 0.2f + 0.15f * i + 0.02f * sinf(time * 3.5f + i);
        float alpha = 0.35f * (1.0f - t) * intensity;
        drawRing(r, 0.01f + 0.01f * t, 140, Color(1.0f, 0.75f, 0.25f, alpha));
    }

    // Radial circuitry
    drawRadials(time * 0.8f);

    // Spiral heart
    drawCoreSpiral(time, 0.35f);

    // Floating fragments
    drawOrbitingFragments(time, 0.55f);
}

void printStartupMessage() {
    std::cout << "\n";
    std::cout << "================================================\n";
    std::cout << "  A E G I S   V I S U A L   C O R E\n";
    std::cout << "================================================\n";
    std::cout << "\n";
    
    std::string frames[] = {
        "Initializing AEGIS Core...",
        "Loading neural interfaces...",
        "Activating security protocols...",
        "Establishing connection to HomeBot...",
        "Calibrating voice recognition...",
        "Starting face identification...",
        "AEGIS Online."
    };
    
    for (size_t i = 0; i < sizeof(frames) / sizeof(frames[0]); i++) {
        std::cout << "[" << std::string(i + 1, '#') << std::string(7 - i - 1, ' ') << "] " << frames[i] << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(400));
    }
    
    std::cout << "\nSystem Ready.\n\n";
}

int main() {
    printStartupMessage();
    
    if (!glfwInit()) {
        std::cerr << "Failed to initialize GLFW\n";
        return 1;
    }
    
    GLFWwindow* window = glfwCreateWindow(WINDOW_WIDTH, WINDOW_HEIGHT, "AEGIS Visual Core", nullptr, nullptr);
    if (!window) {
        std::cerr << "Failed to create window\n";
        glfwTerminate();
        return 1;
    }
    
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);
    
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    glOrtho(-1, 1, -1, 1, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();
    
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    
    auto startTime = std::chrono::steady_clock::now();
    float duration = 4.5f;
    
    while (true) {
        auto now = std::chrono::steady_clock::now();
        float elapsed = std::chrono::duration<float>(now - startTime).count();
        
        if (elapsed >= duration) break;
        
        glfwPollEvents();
        
        if (glfwWindowShouldClose(window)) break;
        
        glClearColor(0.02f, 0.03f, 0.08f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        
        // Subtle camera drift for holographic parallax
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();
        float wobble = 2.0f * sinf(elapsed * 0.8f);
        glRotatef(wobble, 0.0f, 0.0f, 1.0f);

        float intensity = std::clamp(elapsed / duration, 0.0f, 1.0f);
        drawPulse(elapsed, intensity);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA); // restore default for next frame
        
        glfwSwapBuffers(window);
        std::this_thread::sleep_for(std::chrono::milliseconds(16));
    }
    
    glfwDestroyWindow(window);
    glfwTerminate();
    
    std::cout << "Visual startup complete.\n";
    return 0;
}
